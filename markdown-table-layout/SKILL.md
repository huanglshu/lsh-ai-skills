---
name: markdown-table-layout
description: 优化 Markdown 文档中的宽表格、列宽、自动换行和横向滚动。用户要求表格更紧凑、表头不竖排、桌面尽量显示全部列，或批量检查并调整 Markdown 表格排版时使用。
---

# Markdown 表格排版

以当前工作副本为准，只调整用户指定文件或目录中的表格排版。不要从 Git 版本、原始导出或旧模板重新生成文档，也不要删除空列、推断缺失字段、修改正文或操作 Git 暂存区。

## 工作流程

1. 确认文件范围和实际渲染环境。保留已有标题、行列、单元格、链接、代码、附件引用及用户手工修改。HTML 样式是否生效取决于目标渲染器；不要为不支持 HTML 的渲染器强行转换。
2. 优先让桌面内容区在约 850–900px 宽时显示全部列；按内容分配比例列宽、缩小内边距、允许长字段和表头换行。窄屏使用表格容器横向滚动，避免把整页撑宽；不要把长内容截断或默认隐藏。
3. 对普通 GFM 表格和本技能管理的 `wide-table` HTML 表格，使用 [scripts/compact_tables.py](scripts/compact_tables.py)。需要 Python 3.10+ 和 `markdown-it-py` 4.x；缺依赖时先选择现有解释器或向用户说明，不要静默安装或联网。默认仅处理四列及以上表格，目录默认不递归；用户要求时可调整 `--min-columns` 或加 `--recursive`。
4. 先生成计划，再应用。计划只含路径、哈希和统计，不含文档正文；输出文件必须是不存在的路径，宜使用系统临时目录。只应用当前任务自己生成的计划，不要应用来源不明的计划。计划完成后文件若有变化，重新计划。脚本检查写入前的哈希，但无法保证与不遵守文件锁的其他程序同时写入时完全无竞争；批量写入失败时如实报告已完成的文件。

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$formatter = Join-Path $codexHome "skills\markdown-table-layout\scripts\compact_tables.py"
$plan = Join-Path ([IO.Path]::GetTempPath()) ("markdown-table-" + [guid]::NewGuid().ToString("N") + ".json")
python -X utf8 $formatter plan "C:\work\docs" --recursive --output $plan
```

命令也接受单个或多个 `.md` 文件。确认计划成功并检查输出后，才运行：

```powershell
python -X utf8 $formatter apply --plan $plan
```

不要覆盖已有计划文件；为每次任务选择新的临时文件名。

5. 检查输出中的 `skipped`：嵌套表格、含合并单元格或不受支持的 HTML 表格、带裸网址或扩展语法等可能因渲染器差异改变语义的表格，脚本会跳过。保留源文件并按目标渲染器谨慎处理，不要为了消除提示而丢弃内容。
6. 先逐格核对表头、数据和行内格式，再用实际或尽可能接近的目标渲染器检查桌面和手机：有内容的列不要逐字竖排，文字无溢出，桌面尽量不滚动，窄屏可滚动。不要把用户文档发送到外部网站；本地预览应禁用脚本、远程资源和外链加载。不能验证实际渲染时，明确说明局限。

报告修改文件与表格数量、跳过原因、内容校验及实际渲染验证结果。仅当用户另行要求时才发布到 Wiki 或其他远端。
