"""Render the review view without changing or approving the source design."""

import hashlib
import html
import re


TOKEN = re.compile(r'\{\{([^{}]+)\}\}')
CHAPTER_NUMERALS = ('一', '二', '三', '四', '五', '六', '七', '八', '九')
FEATURE_SECTIONS = ('入口、参与者与前置条件', '主流程与输入输出', '状态流转与操作矩阵',
                    '关键时序图', '异常、并发与幂等', '审计与外部副作用')
SHORT_NAMES = {
    '需求改动点.功能改动清单': '需求',
    '需求改动点.业务规则': '规则',
    '需求改动点.对象范围与权限边界': '对象边界',
    '架构设计.模块职责与调用关系.职责清单': '职责',
    '架构设计.核心对象与数据关系.对象清单': '模型',
    'API接口设计.接口清单与兼容性.HTTP API': 'HTTP',
    'API接口设计.接口清单与兼容性.跨模块 Client': 'Client',
    'API接口设计.接口清单与兼容性.事件与异步契约': '事件',
    'API接口设计.请求与响应': '接口字段',
    'API接口设计.错误、操作资格与幂等结果': '错误契约',
    '数据库变更.表及实体变更总览': '数据对象',
    '数据库变更.字段设计': '数据字段',
    '数据库变更.索引、约束与查询': '索引与查询',
    '测试与验收.单元测试设计': '单元测试',
    '测试与验收.集成测试设计': '集成测试',
    '测试与验收.业务验收设计': '验收',
    '参考资料': '资料',
}


def at_path(data, path):
    for key in path.split('.'):
        data = data[key]
    return data


def anchor(path, number):
    region = hashlib.sha256(path.encode('utf-8')).hexdigest()[:12]
    return f'review-{region}-{number}'


def text_cell(value):
    return (html.escape(str(value), quote=False).replace('|', '&#124;')
            .replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>'))


class Inline(str):
    """Already escaped text and links composed only by this renderer."""


def substitute(template, resolve):
    # Source content is inserted once; literal {{...}} is never evaluated again.
    return TOKEN.sub(lambda match: resolve(match.group(1)), template)


def add_section_navigation(document):
    """Index numbered sections, including compact N.A. sections, outside fences."""
    output, entries = [], []
    fence = None
    for line in document.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not line.strip().strip(run[0]):
                fence = None
            output.append(line)
            continue
        heading = compact = None
        if fence is None:
            heading = (re.match(r'^#{2,4}\s+(\d+(?:\.\d+)*)(?:\.)?\s+(.+)$', line)
                       or re.match(r'^##\s+([一二三四五六七八九])、\s*(.+)$', line))
            compact = re.match(r'^\*\*(4\.\d+\.\d+)\s+(.+?)：\*\*', line)
        match = heading or compact
        if match:
            number, title = match.groups()
            if number in CHAPTER_NUMERALS:
                number = str(CHAPTER_NUMERALS.index(number) + 1)
            target = 'section-' + number.replace('.', '-')
            entries.append((number, title, target))
            output.extend([f'<a id="{target}"></a>', ''])
        output.append(line)
        if heading and '.' not in heading.group(1):
            output.extend(['', '[返回目录](#review-directory)'])
    return '\n'.join(output).rstrip() + '\n', entries


def render_directory(entries):
    def label(number, title):
        title = title.replace('<br/>', ' ')
        prefix = (CHAPTER_NUMERALS[int(number) - 1] + '、'
                  if number.isdigit() and 1 <= int(number) <= len(CHAPTER_NUMERALS)
                  else number + ' ')
        return re.sub(r'([\\`*_\[\]])', r'\\\1', prefix + title)
    review_entries = [(number, title, target) for number, title, target in entries
                      if '.' not in number or (number.startswith('4.') and number.count('.') == 1)]
    links = [('    ' if '.' in number else '') + f'- [{label(number, title)}](#{target})'
             for number, title, target in review_entries]
    return '<a id="review-directory"></a>\n\n**审核目录**\n\n' + '\n'.join(links) + '\n\n'


class ReviewView:
    def __init__(self, data, schema, assets):
        self.data = data
        self.schema = schema
        self.assets = assets
        self.labels = {}
        for path in schema['$defs']['reference']['properties']['区域']['enum']:
            block = at_path(data, path)
            for row in block.get('功能', block.get('记录', [])):
                number = row['编号']
                if path == '功能点设计':
                    label = f'4.{number} {row["名称"]}'
                else:
                    label = f'{SHORT_NAMES.get(path, path.split(".")[-1])} {number}'
                    if path.endswith('HTTP API'):
                        label += f' · {row["用途"]}'
                self.labels[(path, number)] = label

    def cell(self, value):
        if isinstance(value, Inline):
            return str(value)
        if isinstance(value, list):
            return '、'.join(self.cell(item) for item in value)
        if isinstance(value, dict):
            path, number = value['区域'], value['编号']
            label = self.labels.get((path, number), f'{path.split(".")[-1]} {number}')
            label = text_cell(label).replace('[', '\\[').replace(']', '\\]')
            return f'[{label}](#{anchor(path, number)})'
        return text_cell(value)

    def table(self, columns, rows, path=None):
        if not rows:
            return ''
        lines = ['| ' + ' | '.join(text_cell(column) for column in columns) + ' |',
                 '| ' + ' | '.join('---' for _ in columns) + ' |']
        for row in rows:
            values = [self.cell(row[column]) for column in columns]
            if path and '编号' in row:
                values[0] = f'<a id="{anchor(path, row["编号"])}"></a>' + values[0]
            lines.append('| ' + ' | '.join(values) + ' |')
        return '\n'.join(lines)

    def status_text(self, block, include_questions=True):
        parts = []
        if block['状态'] == '待填写':
            parts.append('> 草稿：本区域尚待填写。')
        if block['说明'].strip():
            parts.append(block['说明'])
        if include_questions and block['待确认问题']:
            parts.append('**待确认事项：**')
            for question in block['待确认问题']:
                parts.append(f'- **{self.cell(question["问题"])}** '
                             f'影响：{self.cell(question["影响"])} '
                             f'关闭条件：{self.cell(question["关闭条件"])}')
        return '\n\n'.join(parts)

    def steps(self, rows):
        parts = []
        for row in rows:
            parts.append(f'{row["编号"]}. **{self.cell(row["处理与规则引用"])}**\n\n'
                         f'   输入：{self.cell(row["输入及来源"])}；输出：{self.cell(row["输出／写入"])}<br/>\n'
                         f'   实现：{self.cell(row["负责模块／层"])} · {self.cell(row["组件／方法"])}<br/>\n'
                         f'   边界：{self.cell(row["事务及失败处理"])}')
        return '\n\n'.join(parts)

    def state_operations(self, rows, path):
        display = [
            {'编号': row['编号'],
             '操作与条件': row['动作'] + '\n条件：' + row['条件／角色'],
             '状态变化': row['当前状态'] + ' → ' + row['目标状态'],
             '处理结果': row['副作用'] + '\n重复请求：' + row['重复请求结果']}
            for row in rows]
        return self.table(['编号', '操作与条件', '状态变化', '处理结果'], display, path)

    def review_points(self, rows):
        return '\n\n'.join(
            f'{row["编号"]}. **{self.cell(row["类型"])}：** {self.cell(row["关注点"])}'
            + (f'（{self.cell(row["关联内容"])}）' if row['关联内容'] else '')
            for row in rows)

    def grouped_fields(self, rows, path):
        api = path == 'API接口设计.请求与响应'
        key = '方向／模型' if api else '表／实体'
        groups = {}
        for row in rows:
            groups.setdefault(row[key], []).append(row)
        parts = []
        for name, members in groups.items():
            parts.append(f'**{self.cell(name)}**')
            contracts = []
            if api:
                for row in members:
                    for ref in row['契约编号']:
                        if ref not in contracts:
                            contracts.append(ref)
                parts.append('适用接口：' + self.cell(contracts))
            display = []
            for row in members:
                if api:
                    detail = self.cell(row['来源／语义']) + '<br/>' + self.cell(row['校验／兼容规则'])
                    if row['契约编号'] != contracts:
                        detail += '<br/>适用：' + self.cell(row['契约编号'])
                    display.append({'编号': row['编号'], '字段': row['字段路径'],
                                    '类型与必填条件': row['类型／格式'] + '\n' + row['必填／可空'],
                                    '含义与限制': Inline(detail)})
                else:
                    display.append({'编号': row['编号'], '字段': row['字段'],
                                    '类型与空值': row['数据库类型／长度'] + '\n' + row['非空／默认值'],
                                    '含义与修改规则': row['业务语义／来源'] + '\n' + row['可变性与历史处理'],
                                    '模型映射': row['关联模型字段']})
            parts.append(self.table(list(display[0]), display, path))
        return '\n\n'.join(parts)

    def block(self, block, schema, path):
        parts = [self.status_text(block)]
        rows = block.get('记录', [])
        if rows:
            if path == '审核关注点':
                parts.append(self.review_points(rows))
            elif path.endswith('.主流程与输入输出'):
                parts.append(self.steps(rows))
            elif path in ('API接口设计.请求与响应', '数据库变更.字段设计'):
                parts.append(self.grouped_fields(rows, path))
            elif path == 'API接口设计.接口清单与兼容性.HTTP API':
                display = [{'编号': row['编号'], '变更方式': row['变更方式'],
                            '方法与路径': row['方法与路径'], '用途': row['用途']}
                           for row in rows]
                parts.append(self.table(['编号', '变更方式', '方法与路径', '用途'], display, path))
            else:
                columns = list(schema['properties']['记录']['items']['properties'])
                parts.append(self.table(columns, rows, path))
        if block.get('Mermaid', '').strip():
            parts.append('```mermaid\n' + block['Mermaid'].strip() + '\n```')
        return '\n\n'.join(part for part in parts if part)

    def feature_navigation(self, features):
        rows = []
        acceptance = self.data['测试与验收']['业务验收设计']['记录']
        for feature in features:
            requirements = feature['关联需求']
            checks = [{'区域': '测试与验收.业务验收设计', '编号': row['编号']}
                      for row in acceptance
                      if any(ref in row['关联需求及章节'] for ref in requirements)]
            rows.append({'功能': {'区域': '功能点设计', '编号': feature['编号']},
                         '关联需求': requirements, '业务验收': checks})
        return self.table(['功能', '关联需求', '业务验收'], rows)

    def feature_sections(self, feature):
        def section_anchor(key):
            number = FEATURE_SECTIONS.index(key) + 1
            return f'<a id="section-4-{feature["编号"]}-{number}"></a>'

        def narrative(key):
            block = feature[key]
            return self.status_text(block, include_questions=False) if block['状态'] != '不适用' else ''

        def group(title, parts, visible):
            body = '\n\n'.join(part for part in parts if part)
            return f'**{title}**\n\n{body}' if visible else body

        entry_key = '入口、参与者与前置条件'
        entry = [section_anchor(entry_key), narrative(entry_key),
                 '**方案状态：** ' + self.cell(feature['方案定位'])]
        if feature['关联需求']:
            entry.append('关联需求：' + self.cell(feature['关联需求']))

        main_key = '主流程与输入输出'
        main = feature['主流程与输入输出']
        flow = [section_anchor(main_key), narrative(main_key)]

        state_key = '状态流转与操作矩阵'
        state = feature[state_key]
        rules = [section_anchor(state_key), narrative(state_key)]
        if state['状态'] != '不适用':
            rules.append(self.state_operations(state['记录'], f'功能点设计.{feature["编号"]}.{state_key}'))
        for key, label in [('异常、并发与幂等', '异常处理'), ('审计与外部副作用', '后续影响')]:
            rules.append(section_anchor(key))
            content = narrative(key)
            if content:
                rules.append(f'**{label}：** {content}')

        questions = []
        for key in FEATURE_SECTIONS:
            for question in feature[key]['待确认问题']:
                if question not in questions:
                    questions.append(question)
        if questions:
            rules.append(self.status_text({'状态': '已填写', '说明': '', '待确认问题': questions}))

        sequence_key = '关键时序图'
        sequence = feature[sequence_key]
        technical = []
        sequence_parts = [section_anchor(sequence_key)]
        if sequence['状态'] != '不适用':
            sequence_parts.extend(['**执行时序**', narrative(sequence_key)])
            if sequence['Mermaid'].strip():
                sequence_parts.append('```mermaid\n' + sequence['Mermaid'].strip() + '\n```')
            technical.append('\n\n'.join(part for part in sequence_parts if part))
        if main['状态'] != '不适用' and main['记录']:
            technical.append('**实现步骤**\n\n' + self.steps(main['记录']))
        details = '' if sequence['状态'] != '不适用' else section_anchor(sequence_key)
        if technical:
            details += '\n\n<details>\n<summary>实现细节</summary>\n\n' + '\n\n'.join(technical) + '\n\n</details>'
        has_rules = questions or any(feature[key]['状态'] != '不适用' for key in
                                    (state_key, '异常、并发与幂等', '审计与外部副作用'))
        return {
            '功能说明': group('功能说明', entry, True),
            '处理流程': group('处理流程', flow, main['状态'] != '不适用'),
            '规则约束': group('规则约束', rules, has_rules),
            '实现细节': details.strip(),
        }

    def features(self):
        template = (self.assets / 'development-design-feature-template.md').read_text(encoding='utf-8')
        collection = self.data['功能点设计']
        parts = [self.status_text(collection), self.feature_navigation(collection['功能'])]
        for feature in collection['功能']:
            sections = self.feature_sections(feature)
            def resolve(key):
                if key in sections:
                    return sections[key]
                return self.cell(feature[key])
            parts.append(f'<a id="{anchor("功能点设计", feature["编号"])}"></a>\n\n'
                         + substitute(template, resolve).rstrip())
        return '\n\n'.join(part for part in parts if part)

    def render(self):
        def resolve(key):
            reference = key.startswith('参考:')
            if reference:
                key = key.removeprefix('参考:')
            if key == '文档信息':
                rows = [{'文档信息': label, '内容': value} for label, value in self.data[key].items()]
                rows.append({'文档信息': '版本', '内容': f'设计 {self.data["design_revision"]}；Schema {self.data["schema_version"]}'})
                return self.table(['文档信息', '内容'], rows)
            if key == '功能点设计':
                return self.features()
            value = at_path(self.data, key)
            node_schema = self.schema
            for part in key.split('.'):
                node_schema = node_schema['properties'][part]
            if reference:
                if value['状态'] == '不适用':
                    return ''
                return f'**{key.split(".")[-1]}**\n\n' + self.block(value, node_schema, key)
            return self.block(value, node_schema, key) if isinstance(value, dict) else self.cell(value)
        template = (self.assets / 'development-design-template.md').read_text(encoding='utf-8')
        # Split the template-owned slot before substitution: source {{目录}} stays literal.
        before, after = template.split('{{目录}}')
        header = substitute(before, resolve)
        body, entries = add_section_navigation(substitute(after, resolve))
        return header + render_directory(entries) + body.lstrip('\n')
