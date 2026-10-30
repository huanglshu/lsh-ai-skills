---
name: git-staged-summary-zh
description: 自动总结 Git 仓库已暂存、未暂存和未跟踪的变更，生成中文概述、建议 commit message、详细变更和风险建议。用户要求总结 Git 改动、工作区变更、暂存区变更、未暂存内容或生成中文提交说明时使用。
---

# Git 变更中文描述生成

用于将整个 Git 仓库的改动转换为中文变更说明。默认包含已暂存、已跟踪但未暂存的改动，以及未被 Git 忽略的未跟踪文件；不会执行 `git add` 或修改暂存区。

## 快速执行

在目标仓库目录执行：

```powershell
python <skill-dir>\scripts\generate_staged_summary.py --repo .
```

默认输出到终端。若要写入文件：

```powershell
python <skill-dir>\scripts\generate_staged_summary.py --repo . --output .\staged-summary.md
```

可选参数：

- `--max-files`：最多展示的文件明细数，默认 `8`
- `--output`：输出文件路径；不传则打印到标准输出
- `--staged-only`：仅总结已暂存的变更

## 标准流程

1. 在目标项目中运行 `generate_staged_summary.py`，无需事先执行 `git add`。如果用户明确只要求总结暂存区，添加 `--staged-only`。
2. 按已暂存、未暂存和未跟踪文件分别检查输出；同一文件两种状态的改动会分别列出。
3. 按需微调建议提交信息。实际执行 `git commit` 前，仍需将希望提交的改动暂存；默认建议提交信息涵盖全部列出的改动，并非仅代表当前暂存区。

## 输出结构

脚本输出固定四段：

1. 一句话概述：本次变更的核心动作（新增/修复/重构/文档/测试/杂项）。
2. 建议提交信息：`type(scope): subject` 形式的中文 commit message。
3. 详细说明：变更类型、文件数量、行数统计、主要文件清单（含新增/删除行数）。
4. 风险与回归建议：基于改动类型自动给出验证建议。

## 识别规则（摘要）

- 分析暂存区 `git diff --cached`、已跟踪文件的工作区改动 `git diff`，以及 `git ls-files --others --exclude-standard` 返回的未跟踪文件
- 排除被 Git 忽略的未跟踪文件；已跟踪文件即使匹配忽略规则仍会正常分析
- 分析过程不修改暂存区或工作区；指定 `--output` 时会写入输出文件
- 自动识别文件类型：源码、测试、文档、配置、其他
- 优先从目录和改动模式推断 `type`：`feat/fix/refactor/docs/test/chore`
- 尝试从 diff 中抽取函数/类/方法标识，补充“主要改动”描述
- 二进制文件单独计数并在风险建议中提示

## 失败与边界处理

- 若目录不是 Git 仓库，脚本会报错退出。
- 若指定范围内无变更，输出明确提示。
- 若变更文件过多，仅展示前 `--max-files` 个，其余以计数省略。
