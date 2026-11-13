# skills

一些常见的 Skills，按目录独立维护和分享。

## 技能列表

| Skill | 用途 | 文档 |
|---|---|---|
| `module-callgraph` | 基于当前源码梳理跨模块调用、模块职责和业务流程，生成 Mermaid 图 | [模块调用关系图](skills/module-callgraph/SKILL.md) |
| `review-design` | 编写或更新供人工审核的开发设计，串联需求、架构、流程、接口、数据及验收 | [人工审核开发设计](skills/review-design/SKILL.md) |

## 仓库结构

```text
skills/
├── module-callgraph/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/transattach-example.md
│   └── scripts/inventory_sources.py
└── review-design/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── assets/development-design.schema.json
    ├── assets/development-design.blank.json
    ├── assets/development-design-template.md
    ├── assets/development-design-feature-template.md
    ├── references/filling-guide.md
    ├── references/data-contract.md
    ├── scripts/design_document.py
    ├── scripts/requirements.txt
    └── tests/test_design_document.py
```

## 安装到 Codex

在 Codex 中输入：

```text
使用 $skill-installer 安装 https://github.com/LinkenLeeLeeLee/skills/tree/main/skills/module-callgraph
使用 $skill-installer 安装 https://github.com/LinkenLeeLeeLee/skills/tree/main/skills/review-design
```

也可以克隆本仓库，再将所需的 `skills/<skill-name>` 目录复制或软链接到 `~/.agents/skills/<skill-name>`。如果新技能未显示，重启 Codex。

`review-design` 在绘制架构调用关系图时使用 `module-callgraph`，建议同时安装。未安装时会按相同约定绘图，并说明未调用该 Skill。

安装器安装的副本不会随本仓库的 `git pull` 自动更新；克隆并使用软链接时，可通过 `git pull` 同步更新。

## 使用示例

### module-callgraph

```text
使用 $module-callgraph 梳理当前工作区中指定业务入口的跨模块调用关系，
按实际工程结构标注类、函数或组件归属，绘制 Mermaid 图，并提供源码证据。
```

技能按目标工程识别语言和模块边界，可用于 Gradle、Maven、JavaScript／TypeScript workspace 等工程。TransAttach 参考实例是可选的历史示例，不要求存在 `saas-service`。

附带的源码候选清单脚本仅适用于 `src/main` 下的 Java/Groovy + Gradle 工程，依赖 Python 3、ripgrep（`rg`）和 Git：

```sh
python3 skills/module-callgraph/scripts/inventory_sources.py /path/to/repository 'BusinessService|BusinessClient'
```

脚本只查找候选文件和模块归属，不自动证明调用关系。其他工程直接使用源码搜索或已有语言工具；脚本返回零候选或 `unresolved` 不能证明没有调用。参考实例不代表使用者当前工程的实现。

### review-design

```text
使用 $review-design，基于本次需求和当前源码生成开发设计人工审核稿，
区分现状、已确认决定、设计建议与待确认项，列出审核关注点及验收方式。
```

支持目录预览、完整设计和既有设计的增量更新。Skill 根据需求、源码和工程约定决定内容，[Schema](skills/review-design/assets/development-design.schema.json)固定数据结构，[空白 JSON](skills/review-design/assets/development-design.blank.json)承载本次设计，[开发设计模板](skills/review-design/assets/development-design-template.md)生成固定九章的人工审核视图。JSON 与 Markdown 成对交付，修订先更新 JSON，再生成 Markdown。

区域区分待填写、已填写、不适用和待确认；送审校验拒绝待填写。普通数字编号通过区域定位，脚本检查结构化引用的目标，不代替业务审核、需求覆盖判断或 Mermaid 渲染。有架构修改时提供核心模块调用关系图，复杂关键流程按适用范围提供时序图。

生成工具要求 Python 3.9+，校验和生成使用 `jsonschema`；依赖、初始化、草稿／送审和覆盖选项见[数据与生成约定](skills/review-design/references/data-contract.md)。

该 Skill 负责设计文档，不代替代码 Review 或产品审批，也不因生成文档自动修改业务代码、执行部署或新增等待批准的流程。审核记录和验证状态必须有真实依据。
