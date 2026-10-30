---
name: git-staged-summary-zh
description: 自动提取当前 Git 仓库暂存区（staged）代码变更并生成结构化中文描述（概述、建议 commit message、详细变更和风险建议）。当用户提到“总结暂存区变更”“根据 git add 内容生成提交说明”“生成中文提交描述”“为 staged diff 写 commit 文案”等场景时使用。
---

# Git 暂存区中文描述生成

用于把暂存区改动自动转换为统一格式的中文变更说明，减少手工整理提交描述的成本。暂存区为空时，会自动暂存整个仓库的变更。

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

## 标准流程

1. 如需仅总结指定文件，先在目标项目中执行 `git add`。
2. 运行 `generate_staged_summary.py`。若暂存区为空，脚本先执行 `git add -A -- :/`，暂存整个仓库的新增、修改和删除，再提取 `git diff --cached`；若已有暂存内容，则不会额外暂存文件。
3. 直接使用输出中的“建议提交信息”作为 commit message，或按需微调。

## 输出结构

脚本输出固定四段：

1. 一句话概述：本次变更的核心动作（新增/修复/重构/文档/测试/杂项）。
2. 建议提交信息：`type(scope): subject` 形式的中文 commit message。
3. 详细说明：变更类型、文件数量、行数统计、主要文件清单（含新增/删除行数）。
4. 风险与回归建议：基于改动类型自动给出验证建议。

## 识别规则（摘要）

- 分析暂存区：`git diff --cached`；暂存区为空时先自动暂存整个仓库的变更
- 自动识别文件类型：源码、测试、文档、配置、其他
- 优先从目录和改动模式推断 `type`：`feat/fix/refactor/docs/test/chore`
- 尝试从 diff 中抽取函数/类/方法标识，补充“主要改动”描述
- 二进制文件单独计数并在风险建议中提示

## 失败与边界处理

- 若目录不是 Git 仓库，脚本会报错退出。
- 若自动暂存后仍无变更，输出明确提示“未检测到暂存区变更”。
- 若自动暂存失败，脚本会报错退出。
- 若变更文件过多，仅展示前 `--max-files` 个，其余以计数省略。
