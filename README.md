# skills

一些常见的 Skills，按目录独立维护和分享。

## 技能列表

| Skill | 用途 | 文档 |
|---|---|---|
| `module-callgraph` | 基于当前源码梳理跨模块调用、模块职责和业务流程，生成 Mermaid 图 | [模块调用关系图](skills/module-callgraph/SKILL.md) |

## 仓库结构

```text
skills/
└── module-callgraph/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── references/transattach-example.md
    └── scripts/inventory_sources.py
```

## 安装到 Codex

在 Codex 中输入：

```text
使用 $skill-installer 安装 https://github.com/LinkenLeeLeeLee/skills/tree/main/skills/module-callgraph
```

也可以克隆本仓库，再将 `skills/module-callgraph` 目录复制或软链接到 `~/.agents/skills/module-callgraph`。如果新技能未显示，重启 Codex。

安装器安装的副本不会随本仓库的 `git pull` 自动更新；克隆并使用软链接时，可通过 `git pull` 同步更新。

## 使用示例

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
