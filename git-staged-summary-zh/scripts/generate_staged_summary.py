#!/usr/bin/env python3
"""Generate standardized Chinese descriptions for Git changes."""

from __future__ import annotations

import argparse
import subprocess
import sys
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".adoc", ".txt"}
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".scala",
    ".vue",
    ".sql",
    ".sh",
    ".ps1",
}
CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".xml",
    ".gradle",
    ".properties",
    ".lock",
}
GENERIC_SCOPE_NAMES = {"src", "lib", "app", "server", "client", "backend", "frontend"}


@dataclass
class FileChange:
    status: str
    path: str
    old_path: str | None = None
    added: int | None = 0
    deleted: int | None = 0
    binary: bool = False
    kind: str = "other"
    symbols: list[str] = field(default_factory=list)

    @property
    def abs_delta(self) -> int:
        if self.binary or self.added is None or self.deleted is None:
            return 0
        return self.added + self.deleted


def run_git(repo: Path, *args: str, allow_diff: bool = False) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0 and not (allow_diff and result.returncode == 1):
        message = result.stderr.strip() or "git command failed"
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    return result.stdout


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def diff_options(staged: bool) -> list[str]:
    return ["--cached"] if staged else []


def parse_name_status(repo: Path, staged: bool) -> list[FileChange]:
    output = run_git(repo, "diff", *diff_options(staged), "--name-status", "-z", "-M", "-C", "--", ":/")
    changes: list[FileChange] = []
    fields = iter(output.split("\0"))
    for status_raw in fields:
        if not status_raw:
            break
        status = status_raw[0] if status_raw else "M"
        path = normalize_path(next(fields))
        if status in {"R", "C"}:
            old_path = path
            new_path = normalize_path(next(fields))
            changes.append(FileChange(status=status, path=new_path, old_path=old_path))
        else:
            changes.append(FileChange(status=status, path=path))
    return changes


def parse_numstat_output(output: str) -> dict[str, tuple[int | None, int | None, bool]]:
    stat_map: dict[str, tuple[int | None, int | None, bool]] = {}
    fields = iter(output.split("\0"))
    for raw in fields:
        if not raw:
            break
        parts = raw.split("\t", 2)
        if len(parts) != 3:
            continue
        add_s, del_s, path_field = parts
        if not path_field:
            next(fields)
            path_field = next(fields)
        path = normalize_path(path_field)
        if add_s == "-" or del_s == "-":
            stat_map[path] = (None, None, True)
            continue
        try:
            stat_map[path] = (int(add_s), int(del_s), False)
        except ValueError:
            stat_map[path] = (None, None, True)
    return stat_map


def parse_numstat(repo: Path, staged: bool) -> dict[str, tuple[int | None, int | None, bool]]:
    output = run_git(repo, "diff", *diff_options(staged), "--numstat", "-z", "-M", "-C", "--", ":/")
    return parse_numstat_output(output)


DECLARATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\+\s*def\s+([A-Za-z_]\w*)\s*\("), "{name}()"),
    (re.compile(r"^\+\s*class\s+([A-Za-z_]\w*)\b"), "{name}"),
    (re.compile(r"^\+\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$]\w*)\s*\("), "{name}()"),
    (re.compile(r"^\+\s*(?:const|let|var)\s+([A-Za-z_$]\w*)\s*=\s*(?:async\s*)?\("), "{name}()"),
    (re.compile(r"^\+\s*(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z_<>\[\],?]+\s+([A-Za-z_]\w*)\s*\("), "{name}()"),
]


def normalize_symbol(raw: str) -> str:
    value = raw.strip()
    value = re.sub(r"\s+", " ", value)
    return value[:80]


def symbols_from_diff(diff: str, fixed_path: str | None = None, max_symbols_per_file: int = 3) -> dict[str, list[str]]:
    symbols: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    current_path: str | None = fixed_path

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if fixed_path is not None:
                continue
            match = re.match(r"^diff --git a/(.+) b/(.+)$", line)
            if match:
                left = normalize_path(match.group(1))
                right = normalize_path(match.group(2))
                current_path = right if right != "/dev/null" else left
            else:
                current_path = None
            continue

        if not current_path:
            continue

        if line.startswith("@@"):
            match = re.match(r"^@@.*@@\s*(.*)$", line)
            if match:
                context = normalize_symbol(match.group(1))
                if context and context not in seen[current_path]:
                    seen[current_path].add(context)
                    symbols[current_path].append(context)
            continue

        if line.startswith("+") and not line.startswith("+++"):
            for pattern, template in DECLARATION_PATTERNS:
                matched = pattern.search(line)
                if not matched:
                    continue
                symbol = template.format(name=matched.group(1))
                if symbol not in seen[current_path]:
                    seen[current_path].add(symbol)
                    symbols[current_path].append(symbol)
                break

        if len(symbols[current_path]) >= max_symbols_per_file:
            symbols[current_path] = symbols[current_path][:max_symbols_per_file]
    return symbols


def parse_symbols(repo: Path, staged: bool) -> dict[str, list[str]]:
    diff = run_git(repo, "diff", *diff_options(staged), "-M", "-C", "--unified=0",
                   "--no-color", "--no-ext-diff", "--no-textconv", "--", ":/")
    return symbols_from_diff(diff)


def classify_file_kind(path: str) -> str:
    normalized = normalize_path(path).lower()
    suffix = Path(normalized).suffix
    parts = normalized.split("/")
    file_name = parts[-1]

    if suffix in DOC_EXTENSIONS or file_name in {"readme", "readme.md", "changelog.md"} or "docs/" in normalized:
        return "docs"
    if (
        "/test/" in normalized
        or "/tests/" in normalized
        or "/spec/" in normalized
        or file_name.startswith("test_")
        or file_name.endswith("_test.py")
        or file_name.endswith(".spec.ts")
        or file_name.endswith(".spec.js")
    ):
        return "test"
    if suffix in CONFIG_EXTENSIONS or file_name in {
        "package.json",
        "pnpm-lock.yaml",
        "requirements.txt",
        "pom.xml",
        "build.gradle",
    }:
        return "config"
    if suffix in SOURCE_EXTENSIONS:
        return "source"
    return "other"


def infer_change_type(changes: list[FileChange]) -> str:
    if not changes:
        return "chore"

    kinds = {item.kind for item in changes}
    if kinds == {"docs"}:
        return "docs"
    if kinds == {"test"}:
        return "test"

    scores = Counter()
    for item in changes:
        path_lower = item.path.lower()
        if item.kind == "docs":
            scores["docs"] += 3
        elif item.kind == "test":
            scores["test"] += 3
        elif item.kind == "config":
            scores["chore"] += 2
        elif item.kind == "source":
            if item.status == "A":
                scores["feat"] += 3
            elif item.status == "M":
                scores["refactor"] += 2
                scores["fix"] += 1
            elif item.status in {"R", "C", "D"}:
                scores["refactor"] += 2
        else:
            scores["chore"] += 1

        if any(token in path_lower for token in ("fix", "bug", "error", "hotfix", "issue")):
            scores["fix"] += 2

    priority = ["feat", "fix", "refactor", "test", "docs", "chore"]
    best = max(priority, key=lambda key: (scores[key], -priority.index(key)))
    return best if scores[best] > 0 else "chore"


def pick_scope(changes: list[FileChange]) -> tuple[str, str]:
    scopes = []
    for item in changes:
        if item.kind not in {"source", "config"}:
            continue
        parts = item.path.split("/")
        if not parts:
            continue
        candidate = parts[0]
        if candidate in GENERIC_SCOPE_NAMES and len(parts) >= 2:
            candidate = parts[1]
        if "." in candidate:
            candidate = Path(candidate).stem or candidate
        if candidate:
            scopes.append(candidate)
    display_scope = scopes[0] if scopes else "核心模块"

    raw = display_scope.lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-_")
    if not normalized:
        normalized = "core"
    return display_scope, normalized


def short_overview(change_type: str, display_scope: str) -> str:
    if display_scope and display_scope != "核心模块":
        target = f"{display_scope}模块相关内容"
    else:
        target = "项目核心代码"
    verbs = {
        "feat": "新增",
        "fix": "修复",
        "refactor": "重构",
        "docs": "更新",
        "test": "补充",
        "chore": "调整",
    }
    return f"{verbs.get(change_type, '调整')}{target}"


def suggested_commit(change_type: str, scope: str, display_scope: str) -> str:
    templates = {
        "feat": "新增{}相关实现",
        "fix": "修复{}中的问题",
        "refactor": "重构{}相关代码结构",
        "docs": "更新{}文档说明",
        "test": "补充{}测试覆盖",
        "chore": "调整{}工程配置",
    }
    subject_scope = display_scope if display_scope != "核心模块" else "核心模块"
    subject = templates.get(change_type, templates["chore"]).format(subject_scope)
    return f"{change_type}({scope}): {subject}"


def summarize_files(changes: list[FileChange], max_files: int) -> list[str]:
    status_text = {"A": "新增", "M": "修改", "D": "删除", "R": "重命名", "C": "复制"}
    summary_lines: list[str] = []
    ranked = sorted(changes, key=lambda item: (item.abs_delta, item.path), reverse=True)
    for index, item in enumerate(ranked):
        if index >= max_files:
            break
        delta = "二进制变更" if item.binary else f"+{item.added}/-{item.deleted}"
        symbol_text = ""
        if item.symbols:
            symbol_text = "，涉及 " + "、".join(f"`{symbol}`" for symbol in item.symbols[:2])
        if item.status in {"R", "C"} and item.old_path:
            action = f"{item.old_path} -> {item.path}"
            line = f"- `{item.path}`（{status_text.get(item.status, item.status)}，{delta}）：{action}{symbol_text}。"
        else:
            line = f"- `{item.path}`（{status_text.get(item.status, item.status)}，{delta}）{symbol_text}。"
        summary_lines.append(line)
    if len(changes) > max_files:
        summary_lines.append(f"- 其余 {len(changes) - max_files} 个文件已省略，可按需展开查看。")
    return summary_lines


def build_risks(changes: list[FileChange]) -> list[str]:
    risks: list[str] = []
    has_source = any(item.kind == "source" for item in changes)
    has_test = any(item.kind == "test" for item in changes)
    has_config = any(item.kind == "config" for item in changes)
    has_binary = any(item.binary for item in changes)

    total_add = sum(item.added or 0 for item in changes if not item.binary)
    total_del = sum(item.deleted or 0 for item in changes if not item.binary)

    if has_config:
        risks.append("包含配置或依赖变更，建议在目标环境执行一次完整构建/启动验证。")
    if has_source and not has_test:
        risks.append("未检测到测试文件同步变更，建议补充关键路径回归用例。")
    if total_del > 80 and total_del > total_add * 1.5:
        risks.append("删除代码量较大，建议重点关注兼容性与回滚预案。")
    if has_binary:
        risks.append("包含二进制文件变更，建议校验文件来源与版本一致性。")
    if not risks:
        risks.append("本次以局部调整为主，建议执行常规 smoke test 验证。")
    return [f"- {item}" for item in risks]


def generate_report(groups: list[tuple[str, list[FileChange]]], max_files: int, staged_only: bool) -> str:
    changes = [item for _, group in groups for item in group]
    if not changes:
        return "未检测到暂存区变更。" if staged_only else "未检测到 Git 变更。"

    change_type = infer_change_type(changes)
    display_scope, scope = pick_scope(changes)
    overview = short_overview(change_type, display_scope)
    commit_line = suggested_commit(change_type, scope, display_scope)

    status_counter = Counter(item.status for item in changes)
    total_add = sum(item.added or 0 for item in changes if not item.binary)
    total_del = sum(item.deleted or 0 for item in changes if not item.binary)
    binary_count = sum(1 for item in changes if item.binary)

    binary_suffix = f"，二进制文件 {binary_count} 个" if binary_count else ""
    details = []
    remaining = max_files
    for label, group in groups:
        if not group:
            continue
        details.append(f"### {label}")
        if remaining:
            shown = min(remaining, len(group))
            details.extend(summarize_files(group, max_files=shown)[:shown])
            remaining -= shown
        else:
            details.append("- 此类变更的文件明细已省略。")
    omitted = max(0, len(changes) - max_files)
    if omitted:
        details.append(f"- 共省略 {omitted} 条变更明细，可增大 `--max-files` 查看。")
    file_details = "\n".join(details)
    risk_text = "\n".join(build_risks(changes))

    return (
        "# Git 变更中文描述\n\n"
        "## 一句话概述\n"
        f"{overview}\n\n"
        "## 建议提交信息\n"
        f"`{commit_line}`\n\n"
        + ("" if staged_only else "此建议涵盖下列全部变更；提交前需暂存希望提交的内容。\n\n")
        +
        "## 详细说明\n"
        f"- 变更类型：`{change_type}`\n"
        f"- 变更条目：{len(changes)} 条（新增 {status_counter['A']}，修改 {status_counter['M']}，删除 {status_counter['D']}，重命名 {status_counter['R']}，复制 {status_counter['C']}）；同一文件的已暂存和未暂存改动分别计数。\n"
        f"- 行数统计：+{total_add} / -{total_del}{binary_suffix}\n"
        "- 主要改动：\n"
        f"{file_details}\n\n"
        "## 风险与回归建议\n"
        f"{risk_text}\n"
    )


def enrich_changes(repo: Path, changes: list[FileChange], staged: bool) -> list[FileChange]:
    if not changes:
        return changes
    stat_map = parse_numstat(repo, staged)
    symbol_map = parse_symbols(repo, staged)
    for item in changes:
        stats = stat_map.get(item.path)
        if stats:
            item.added, item.deleted, item.binary = stats
        item.kind = classify_file_kind(item.path)
        item.symbols = symbol_map.get(item.path, [])
    return changes


def untracked_changes(repo: Path) -> list[FileChange]:
    paths = run_git(repo, "ls-files", "--others", "--exclude-standard", "-z", "--", ":/").split("\0")
    changes = []
    for path in filter(None, paths):
        item = FileChange(status="A", path=normalize_path(path))
        stats_output = run_git(repo, "diff", "--no-index", "--numstat", "-z",
                               "--", "/dev/null", path, allow_diff=True)
        stats = parse_numstat_output(stats_output)
        if stats:
            item.added, item.deleted, item.binary = next(iter(stats.values()))
        item.kind = classify_file_kind(item.path)
        if not item.binary:
            diff = run_git(repo, "diff", "--no-index", "--unified=0", "--no-color",
                           "--no-ext-diff", "--no-textconv", "--", "/dev/null", path,
                           allow_diff=True)
            item.symbols = symbols_from_diff(diff, fixed_path=item.path).get(item.path, [])
        changes.append(item)
    return changes


def validate_repo(repo: Path) -> Path:
    return Path(run_git(repo, "rev-parse", "--show-toplevel").rstrip("\n")).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="提取当前项目已暂存、未暂存和未跟踪的变更并生成中文描述。"
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="目标 Git 仓库路径，默认当前目录。",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=8,
        help="最多展示的文件明细数量，默认 8。",
    )
    parser.add_argument(
        "--output",
        default="",
        help="输出文件路径；为空时打印到标准输出。",
    )
    parser.add_argument(
        "--staged-only",
        action="store_true",
        help="仅总结已暂存的变更。",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    repo = Path(args.repo).resolve()

    if args.max_files < 1:
        print("--max-files 必须大于等于 1。", file=sys.stderr)
        return 2

    try:
        repo = validate_repo(repo)
        staged = enrich_changes(repo, parse_name_status(repo, staged=True), staged=True)
        groups = [("已暂存变更", staged)]
        if not args.staged_only:
            unstaged = enrich_changes(repo, parse_name_status(repo, staged=False), staged=False)
            groups.extend([("未暂存变更", unstaged), ("未跟踪文件", untracked_changes(repo))])
        report = generate_report(groups, max_files=args.max_files, staged_only=args.staged_only)
    except Exception as exc:  # noqa: BLE001
        print(f"生成失败：{exc}", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"已生成描述文件：{output_path}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
