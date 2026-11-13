"""Validate design JSON and render its fixed Markdown review view."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
from review_view import ReviewView


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'JSON 字段重复：{key}')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'JSON 不允许非有限数值：{value}')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=reject_duplicates,
                      parse_constant=reject_constant)


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


def location(path):
    return '.'.join(str(part) for part in path) or '$'


def has_heading(text):
    """Headings inside a fenced code example do not alter document structure."""
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not line.strip().strip(run[0]):
                fence = None
            continue
        if fence is None and (re.match(r'^\s{0,3}#{1,6}(?:\s|$)', line)
                              or re.match(r'^\s{0,3}(?:={3,}|-{3,})\s*$', line)):
            return True
    if fence is not None:
        raise ValueError('说明中的代码围栏未闭合')
    return False


def validate(data, schema, draft=False):
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ValueError('缺少 jsonschema；请在所用 Python 环境安装 scripts/requirements.txt') from exc
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(data),
                    key=lambda error: location(error.absolute_path))
    if errors:
        raise ValueError('\n'.join(f'{location(error.absolute_path)}: {error.message}'
                                   for error in errors))

    problems = []
    targets = {}
    for path, value in walk(data):
        if not isinstance(value, dict):
            continue
        if '状态' in value:
            if not draft and value['状态'] == '待填写':
                problems.append(f'{location(path)}: 送审数据仍为待填写')
            try:
                if has_heading(value['说明']):
                    problems.append(f'{location(path)}: 说明不得新增标题')
            except ValueError as exc:
                problems.append(f'{location(path)}: {exc}')
        if 'Mermaid' in value and ('```' in value['Mermaid'] or '~~~' in value['Mermaid']):
            problems.append(f'{location(path)}: Mermaid 字段只保存源码，不含围栏')
        rows = value.get('记录')
        if rows is not None:
            ids = [row['编号'] for row in rows]
            if ids != list(range(1, len(rows) + 1)):
                problems.append(f'{location(path)}: 编号须从 1 连续递增且不重复')
            targets[location(path)] = set(ids)
    features = data['功能点设计']['功能']
    ids = [feature['编号'] for feature in features]
    if ids != list(range(1, len(features) + 1)):
        problems.append('功能点设计: 功能编号须从 1 连续递增且不重复')
    targets['功能点设计'] = set(ids)
    for path, value in walk(data):
        if isinstance(value, dict) and set(value) == {'区域', '编号'}:
            if value['编号'] not in targets.get(value['区域'], set()):
                problems.append(f'{location(path)}: 引用不存在：{value["区域"]} 第 {value["编号"]} 项')

    reference_targets = {
        '关联需求': {'需求改动点.功能改动清单'},
        '对应功能': {'功能点设计'},
        '契约编号': {f'API接口设计.接口清单与兼容性.{name}'
                     for name in ('HTTP API', '跨模块 Client', '事件与异步契约')},
        '关联需求及章节': {'需求改动点.功能改动清单'},
    }
    for path, value in walk(data):
        if path and path[-1] in reference_targets:
            for ref in value:
                if ref['区域'] not in reference_targets[path[-1]]:
                    problems.append(f'{location(path)}: 引用区域与字段含义不符')
    # A review draft may contain unresolved decisions, but not missing identity/baseline.
    if not draft:
        for key in ('标题',):
            if not data[key].strip():
                problems.append(f'{key}: 送审时不得为空')
        for key, value in data['文档信息'].items():
            if not value.strip():
                problems.append(f'文档信息.{key}: 送审时不得为空')
    if problems:
        raise ValueError('\n'.join(problems))


def render(data, schema):
    return ReviewView(data, schema, ASSETS).render()


def write_output(path, content, overwrite=False):
    """Publish a complete UTF-8 file; refuse accidental replacement by default."""
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        raise ValueError('输出不能写入 Skill 资源目录，请选择设计交付目录')
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as output:
            temp_path = Path(output.name)
            output.write(content)
        if overwrite:
            os.replace(temp_path, path)
        else:
            os.link(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='复制待填充的空白 JSON；不覆盖现有文件')
    init.add_argument('output', type=Path)
    for name in ('validate', 'render'):
        command = commands.add_parser(name)
        command.add_argument('input', type=Path)
        command.add_argument('--draft', action='store_true', help='允许保留待填写区域')
        if name == 'render':
            command.add_argument('output', type=Path)
            command.add_argument('--overwrite', action='store_true', help='替换已有生成文档')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            write_output(args.output, (ASSETS / 'development-design.blank.json').read_text(encoding='utf-8'))
            print(f'已创建空白设计数据：{args.output}')
            return 0
        data = read_json(args.input)
        schema = read_json(ASSETS / 'development-design.schema.json')
        validate(data, schema, args.draft)
        if args.command == 'render':
            if args.output.resolve() == args.input.resolve():
                raise ValueError('生成文档不能覆盖源 JSON')
            write_output(args.output, render(data, schema), args.overwrite)
            print(f'已生成审核文档：{args.output}')
        else:
            print('设计数据结构与引用校验通过；不代表设计、人工审核或运行验证通过。')
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
