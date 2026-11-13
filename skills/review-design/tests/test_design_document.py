"""Core contract and rendering cases; run only after the requested review."""

import copy
import importlib.util
from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location('design_document', ROOT / 'scripts/design_document.py')
design = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(design)


class DesignDocumentTest(unittest.TestCase):
    def setUp(self):
        self.schema = design.read_json(ROOT / 'assets/development-design.schema.json')
        self.blank = design.read_json(ROOT / 'assets/development-design.blank.json')

    def review_data(self):
        data = copy.deepcopy(self.blank)
        data['标题'] = '示例设计'
        for key, value in data['文档信息'].items():
            if not value:
                data['文档信息'][key] = '本测试的明确基线'
        for _, node in design.walk(data):
            if isinstance(node, dict) and '状态' in node:
                node['状态'] = '不适用'
                node['说明'] = '本场景无此项变更'
        return data

    def test_draft_is_not_a_review_document_and_missing_structure_is_rejected(self):
        design.validate(self.blank, self.schema, draft=True)
        with self.assertRaisesRegex(ValueError, '待填写'):
            design.validate(self.blank, self.schema)
        del self.blank['测试与验收']['集成测试设计']
        with self.assertRaises(ValueError):
            design.validate(self.blank, self.schema, draft=True)

    def test_status_requires_reason_or_explicit_unresolved_question(self):
        data = self.review_data()
        node = data['背景与目标']['业务背景与现状问题']
        node['说明'] = '  '
        with self.assertRaises(ValueError):
            design.validate(data, self.schema)
        node.update({'状态': '待确认', '说明': ''})
        with self.assertRaises(ValueError):
            design.validate(data, self.schema)
        node['待确认问题'] = [{'问题': '确认适用版本', '影响': '影响读取范围', '关闭条件': '需求方明确版本范围'}]
        design.validate(data, self.schema)
        self.assertIn('确认适用版本', design.render(data, self.schema))

    def test_unknown_fields_and_duplicate_json_keys_are_rejected(self):
        data = self.review_data()
        data['额外章节'] = {}
        with self.assertRaises(ValueError):
            design.validate(data, self.schema)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'duplicate.json'
            path.write_text('{"a": 1, "a": 2}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '重复'):
                design.read_json(path)

    def test_references_must_exist_and_match_the_field_meaning(self):
        data = self.review_data()
        rules = data['需求改动点']['业务规则']
        rules['状态'] = '已填写'
        rules['记录'] = [{
            '编号': 1,
            '关联需求': [{'区域': '需求改动点.功能改动清单', '编号': 1}],
            '规则名称': '状态规则', '适用条件': '提交时', '规则内容': '已完成不能提交',
            '不满足时的业务结果': '拒绝', '确认状态': '建议',
        }]
        with self.assertRaisesRegex(ValueError, '引用不存在'):
            design.validate(data, self.schema)
        requirements = data['需求改动点']['功能改动清单']
        requirements['状态'] = '已填写'
        requirements['记录'] = [{
            '编号': 1, '功能／场景': '提交', '变更类型': '调整',
            '当前行为及依据': '测试材料', '目标行为': '拒绝重复提交', '确认状态': '建议',
        }]
        design.validate(data, self.schema)
        rules['记录'][0]['关联需求'][0]['区域'] = '需求改动点.业务规则'
        with self.assertRaisesRegex(ValueError, '字段含义不符'):
            design.validate(data, self.schema)
        rules['记录'][0]['编号'] = 2
        with self.assertRaisesRegex(ValueError, '连续递增'):
            design.validate(data, self.schema)

    def test_feature_repetition_and_data_cannot_change_table_or_heading_structure(self):
        data = self.review_data()
        collection = data['功能点设计']
        collection['状态'] = '已填写'
        schema = self.schema['properties']['功能点设计']['properties']['功能']['items']
        for number in (1, 2):
            feature = {'编号': number, '名称': f'功能 {number} | <script>\n{{标题}}',
                       '方案定位': '本例只演示结构，不代表已确认', '关联需求': []}
            for key, node_schema in schema['properties'].items():
                if key in feature:
                    continue
                block = {'状态': '不适用', '说明': '本功能无此步骤', '待确认问题': []}
                if '记录' in node_schema['properties']:
                    block['记录'] = []
                if 'Mermaid' in node_schema['properties']:
                    block['Mermaid'] = ''
                feature[key] = block
            collection['功能'].append(feature)
        design.validate(data, self.schema)
        document = design.render(data, self.schema)
        self.assertNotIn('#### 4.2.6', document)
        self.assertNotIn('本功能无此步骤', document)
        self.assertEqual(collection['功能'][1]['审计与外部副作用']['说明'], '本功能无此步骤')
        self.assertEqual(document.count('\n## '), 9)
        self.assertIn('&#124; &lt;script&gt;<br/>{{标题}}', document)
        self.assertNotIn('<script>', document)
        collection['功能'][0]['异常、并发与幂等']['说明'] = '## 注入章节'
        with self.assertRaisesRegex(ValueError, '新增标题'):
            design.validate(data, self.schema)

    def test_review_view_keeps_unresolved_questions_without_empty_tables(self):
        data = self.review_data()
        node = data['背景与目标']['业务背景与现状问题']
        node.update({'状态': '待确认', '说明': '既定边界保持不变。', '待确认问题': [
            {'问题': '是否增加独立阻断？', '影响': '改变提交结果', '关闭条件': '需求方确认'}]})
        document = design.render(data, self.schema)
        self.assertIn('是否增加独立阻断？', document)
        self.assertIn('改变提交结果', document)
        self.assertIn('需求方确认', document)
        self.assertNotIn('填写状态：已填写', document)
        lines = document.splitlines()
        for index, line in enumerate(lines):
            if line.startswith('| ---'):
                self.assertTrue(lines[index + 1].startswith('|'), '审核稿不能输出空表')

    def test_feature_grouping_keeps_decisions_visible_and_all_contract_details(self):
        data = self.review_data()
        collection = data['功能点设计']
        collection['状态'] = '已填写'
        feature = {'编号': 1, '名称': '保存选择', '方案定位': '保留待定边界', '关联需求': []}
        schema = self.schema['properties']['功能点设计']['properties']['功能']['items']
        for key, node_schema in schema['properties'].items():
            if key in feature:
                continue
            block = {'状态': '不适用', '说明': '无此项', '待确认问题': []}
            if '记录' in node_schema['properties']:
                block['记录'] = []
            if 'Mermaid' in node_schema['properties']:
                block['Mermaid'] = ''
            feature[key] = block
        feature['主流程与输入输出'].update({'状态': '已填写', '说明': '先授权，再保存。', '记录': [
            {'编号': 1, '处理与规则引用': '保存业务规则', '输入及来源': '服务端加载的可信版本',
             '输出／写入': '规则关联', '事务及失败处理': '写入失败整体回滚',
             '负责模块／层': '产品应用层', '组件／方法': 'saveSelection'}]})
        operation = {'编号': 1, '当前状态': '未启用', '动作': '启用', '条件／角色': '产品可编辑',
                     '目标状态': '已启用', '副作用': '同步条件状态', '重复请求结果': '不重复创建实例'}
        feature['状态流转与操作矩阵'].update({'状态': '已填写', '说明': '按可编辑性决定操作。', '记录': [operation]})
        question = {'问题': '是否允许变更上下文？', '影响': '改变规则范围', '关闭条件': '需求方确认限制'}
        feature['关键时序图'].update({'状态': '待确认', '说明': '保存时序。', '待确认问题': [question],
                                    'Mermaid': 'sequenceDiagram\n    A->>B: save'})
        feature['异常、并发与幂等'].update({'状态': '待确认', '说明': '并发冲突拒绝覆盖。',
                                         '待确认问题': [copy.deepcopy(question)]})
        collection['功能'] = [feature]
        original = copy.deepcopy(data)

        document = design.render(data, self.schema)
        feature_text = document.split('### 4.1 保存选择', 1)[1].split('<a id="section-5"></a>', 1)[0]
        visible, details = feature_text.split('<details>', 1)
        for text in question.values():
            self.assertEqual(visible.count(text), 1)
            self.assertNotIn(text, details)
        self.assertIn('并发冲突拒绝覆盖。', visible)
        for key, value in operation.items():
            if key != '编号':
                self.assertIn(value, visible)
        for text in ('服务端加载的可信版本', '规则关联', '写入失败整体回滚', '产品应用层', 'saveSelection', 'A->>B: save'):
            self.assertIn(text, details)
        for number in range(1, 7):
            self.assertEqual(feature_text.count(f'id="section-4-1-{number}"'), 1)
        self.assertEqual(data, original)

    def test_reference_navigation_and_grouped_fields_preserve_applicability(self):
        data = self.review_data()
        api = data['API接口设计']['接口清单与兼容性']['HTTP API']
        columns = self.schema['properties']['API接口设计']['properties']['接口清单与兼容性']['properties']['HTTP API']['properties']['记录']['items']['properties']
        api.update({'状态': '已填写', '记录': []})
        for number, purpose in ((1, '创建规则'), (2, '更新规则')):
            row = {key: '已有契约' for key in columns}
            row.update({'编号': number, '变更方式': '复用', '用途': purpose, '对应功能': []})
            api['记录'].append(row)
        fields = data['API接口设计']['请求与响应']
        both = [{'区域': 'API接口设计.接口清单与兼容性.HTTP API', '编号': n} for n in (1, 2)]
        fields.update({'状态': '已填写', '记录': [
            {'编号': 1, '契约编号': both, '方向／模型': '请求／RuleCmd', '字段路径': 'name',
             '类型／格式': 'String', '必填／可空': '必填', '来源／语义': '用户输入', '校验／兼容规则': '最长 300'},
            {'编号': 2, '契约编号': both[1:], '方向／模型': '请求／RuleCmd', '字段路径': 'ver',
             '类型／格式': 'Integer', '必填／可空': '更新必填', '来源／语义': '所读版本', '校验／兼容规则': '冲突拒绝'}]})
        document = design.render(data, self.schema)
        self.assertIn('更新必填', document)
        self.assertIn('最长 300', document)
        self.assertIn('冲突拒绝', document)
        ver_row = next(line for line in document.splitlines() if '| ver |' in line)
        self.assertIn('适用：', ver_row)
        self.assertIn('更新规则', ver_row)
        self.assertNotIn('创建规则', ver_row)
        self.assertNotIn('API接口设计.接口清单与兼容性.HTTP API 第', document)
        import re
        targets = set(re.findall(r'<a id="([^"]+)"', document))
        links = set(re.findall(r'\]\(#([^)]+)\)', document))
        self.assertTrue(links)
        self.assertTrue(links <= targets)

    def test_existing_output_is_preserved_without_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'design.md'
            design.write_output(path, 'original')
            with self.assertRaises(FileExistsError):
                design.write_output(path, 'replacement')
            self.assertEqual(path.read_text(encoding='utf-8'), 'original')
            design.write_output(path, 'replacement', overwrite=True)
            self.assertEqual(path.read_text(encoding='utf-8'), 'replacement')
        with self.assertRaisesRegex(ValueError, 'Skill 资源目录'):
            design.write_output(ROOT / 'assets/should-not-write.md', 'content')

    def test_directory_targets_include_compact_sections_but_exclude_code_examples(self):
        from review_view import add_section_navigation, render_directory
        body = ('## 一、需求背景\n\n### 1.1 背景\n\n'
                '```markdown\n## 99. 示例标题\n## 九、示例章节\n```\n\n'
                '~~~markdown\n### 99.1 另一个示例\n~~~\n\n'
                '## 2. 旧式编号\n\n'
                '## 四、核心流程\n\n### 4.1 保存 [草稿]\n\n'
                '**4.1.3 状态流转与操作矩阵：** 本功能不涉及状态变化。\n')
        content, entries = add_section_navigation(body)
        directory = render_directory(entries)
        self.assertIn('](#section-1)', directory)
        self.assertIn('[一、需求背景](#section-1)', directory)
        self.assertIn('[二、旧式编号](#section-2)', directory)
        self.assertIn('[四、核心流程](#section-4)', directory)
        self.assertIn('](#section-4-1)', directory)
        self.assertNotIn('](#section-9)', directory)
        self.assertNotIn('](#section-1-1)', directory)
        self.assertNotIn('](#section-4-1-3)', directory)
        self.assertIn('<a id="section-4-1-3"></a>', content)
        self.assertIn('保存 \\[草稿\\]', directory)
        self.assertNotIn('99', directory)
        self.assertIn('## 99. 示例标题', content)
        self.assertIn('[返回目录](#review-directory)', content)
        import re
        targets = re.findall(r'<a id="([^"]+)"', directory + content)
        links = set(re.findall(r'\]\(#([^)]+)\)', directory + content))
        self.assertEqual(len(targets), len(set(targets)))
        self.assertTrue(links <= set(targets))

    def test_directory_does_not_interpret_literal_placeholders_in_design_content(self):
        data = self.review_data()
        data['标题'] = '保留 {{目录}} 和 {{标题}} 字面值'
        document = design.render(data, self.schema)
        self.assertIn('保留 {{目录}} 和 {{标题}} 字面值', document)
        self.assertIn('审核目录', document)
        self.assertIn('](#section-9)', document)


if __name__ == '__main__':
    unittest.main()
