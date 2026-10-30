# Agent Skills 技能库

本仓库收集多个可独立使用的 Agent Skill。每个一级目录都是一个技能包，
以目录中的 `SKILL.md` 作为完整说明和使用入口。

本 README 只提供中文索引。执行具体任务前，应阅读对应技能的 `SKILL.md`，
再按需加载其 `scripts/`、`references/` 或 `assets/` 资源。

## 使用方式

1. 根据任务在下方技能清单中选择最匹配的条目。
2. 打开对应的 `SKILL.md`，确认触发条件、依赖和操作限制。
3. 在技能目录内运行脚本，并使用文档要求的相对路径。
4. 涉及远程系统、真实浏览器、账号凭据或删除操作时，先确认目标和授权范围。

仓库没有统一的安装包或根级测试命令。不同技能的 Python、Node.js 和外部工具
依赖需按各自的 `SKILL.md` 准备。

## 技能清单

### 技能创建与代码审查

| 技能名称 | 中文描述 | 典型使用场景 |
| --- | --- | --- |
| [`skill-creator`](./skill-creator/SKILL.md) | 创建、修改、测试和优化 Agent Skill，并支持评估、基准比较和触发描述优化。 | 新建技能、完善现有技能、设计测试案例、评估技能效果。 |
| [`find-skills`](./find-skills/SKILL.md) | 检索并安装开放的 Agent Skills，帮助判断是否有现成技能可解决问题。 | 查找某类技能、扩展代理能力、安装社区技能。 |
| [`code-review-skill`](./code-review-skill/SKILL.md) | 提供多语言、多框架的代码审查指南，覆盖架构、性能、安全、质量和常见缺陷。 | PR 审查、安全审计、架构评审、性能检查、制定审查规范。 |
| [`git-staged-summary-zh`](./git-staged-summary-zh/SKILL.md) | 汇总已暂存、未暂存和未跟踪的 Git 变更，生成中文概述、提交信息建议和风险提示。 | 总结工作区改动、生成中文 commit message、检查待提交内容。 |

### 设计与前端

| 技能名称 | 中文描述 | 典型使用场景 |
| --- | --- | --- |
| [`design`](./design/SKILL.md) | 综合设计入口，覆盖品牌、设计令牌、UI、Logo、企业视觉识别、演示文稿、横幅、图标和社媒图片。 | 不确定应使用哪个具体设计技能时，先按该入口进行任务分流。 |
| [`design-system`](./design-system/SKILL.md) | 建立设计令牌体系、组件规范、CSS 变量、间距和排版尺度，并支持品牌一致的演示文稿。 | 设计系统搭建、Tailwind 主题、组件状态定义、设计到代码交付。 |
| [`ui-styling`](./ui-styling/SKILL.md) | 使用 shadcn/ui、Radix UI 和 Tailwind CSS 创建可访问、响应式的用户界面与视觉设计。 | 构建 React 界面、主题和暗色模式、无障碍组件、响应式布局。 |
| [`brand`](./brand/SKILL.md) | 管理品牌语调、视觉识别、信息框架、资产规范和品牌一致性。 | 品牌指南、营销内容语调、品牌审查、配色和字体规范。 |
| [`banner-design`](./banner-design/SKILL.md) | 设计社媒、广告、网站头图、活动和印刷横幅，支持多种艺术方向。 | Facebook、LinkedIn、YouTube 等平台横幅；网站 Hero；广告素材。 |
| [`slides`](./slides/SKILL.md) | 创建结合 Chart.js 图表、设计令牌、响应式布局和文案策略的 HTML 演示文稿。 | 营销演示、数据驱动幻灯片、路演材料、策略型演示。 |

### 文档与转换

| 技能名称 | 中文描述 | 典型使用场景 |
| --- | --- | --- |
| [`convert-to-pdf`](./convert-to-pdf/SKILL.md) | 将 XPS、Word、Excel、PowerPoint、WPS 和 MHTML/MHT 等文件转换为 PDF。 | Office/WPS 文档转 PDF、网页归档转 PDF、交付格式转换。 |
| [`markdown-converter`](./markdown-converter/SKILL.md) | 使用 MarkItDown 将 PDF、Office、HTML、数据文件、OCR 结果、音频、ZIP 和 YouTube 内容转换为 Markdown。 | 资料转 Markdown、知识库整理、批量内容提取。 |

### OA 集成

| 技能名称 | 中文描述 | 典型使用场景 |
| --- | --- | --- |
| [`oa-data-dictionary-query`](./oa-data-dictionary-query/SKILL.md) | 查询 OA 数据字典，返回数据库表的字段名、类型、长度和说明。 | 查询表结构、确认字段定义、根据表名检索数据字典。 |
| [`weaver-oa-form-js-sdk`](./weaver-oa-form-js-sdk/SKILL.md) | 编写和排查泛微 OA 表单 JS，覆盖 `WfForm` API、事件、字段联动、明细表和移动端逻辑。 | 流程表单代码块开发、字段权限控制、提交校验、明细行逻辑。 |

### 项目协作与浏览器自动化

| 技能名称 | 中文描述 | 典型使用场景 |
| --- | --- | --- |
| [`teambition`](./teambition/SKILL.md) | 操作 Teambition 私有化部署的项目和任务，支持认证、查询、创建、编辑和删除。 | 查询项目、创建需求或任务、更新任务、添加参与者。 |
| [`playwright`](./playwright/SKILL.md) | 通过 `playwright-cli` 操作真实浏览器，支持导航、表单、快照、截图、数据提取和交互调试。 | 网页操作自动化、界面流程验证、页面检查和视觉证据采集。 |

## 资源结构

技能不一定具有所有子目录，常见结构如下：

```text
<skill-name>/
├── SKILL.md       # 必需的技能说明和触发信息
├── scripts/       # 确定性脚本或重复性操作
├── references/    # 按需加载的专业参考资料
└── assets/        # 模板、样例、图片及其他输入资源
```

`oa-data-dictionary-query/assets/` 包含大量 HTML 数据字典文件。应按表名先定位
映射和目标文件，不要批量读取或改写整个资源目录。

## 注意事项

- 每个技能是独立边界，默认只修改任务涉及的技能目录。
- 不把真实账号、密码、Cookie、令牌或 `.env` 内容写入文档、示例或提交。
- `teambition/` 包含敏感配置；仅运行非破坏性检查，远程写操作必须获得明确授权。
- 不要批量运行 `teambition/scripts/test_*.py`，其中部分脚本会访问真实环境或变更任务。
- 生成文档、演示或设计物后，应检查实际渲染结果和关键响应式状态。
- 详细工作规范见 [AGENTS.md](./AGENTS.md) 和
  [AGENTS.zh-CN.md](./AGENTS.zh-CN.md)。
