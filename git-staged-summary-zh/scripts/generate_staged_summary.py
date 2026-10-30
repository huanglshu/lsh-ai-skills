#!/usr/bin/env python3
"""Generate standardized Chinese descriptions for staged git changes."""

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


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "git command failed"
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    return result.stdout


def normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def parse_name_status(repo: Path) -> list[FileChange]:
    output = run_git(repo, "diff", "--cached", "--name-status", "-M", "-C")
    changes: list[FileChange] = []
    for raw in output.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        status_raw = parts[0].strip()
        status = status_raw[0] if status_raw else "M"
        if status in {"R", "C"} and len(parts) >= 3:
            old_path = normalize_path(parts[1])
            new_path = normalize_path(parts[2])
            changes.append(FileChange(status=status, path=new_path, old_path=old_path))
        elif len(parts) >= 2:
            changes.append(FileChange(status=status, path=normalize_path(parts[1])))
    return changes


def resolve_rename_path(path_field: str) -> str:
    text = path_field.strip()
    if " => " not in text:
        return normalize_path(text)
    if "{" in text and "}" in text:
        before, rest = text.split("{", 1)
        inner, after = rest.split("}", 1)
        if " => " in inner:
            _, new_part = inner.split(" => ", 1)
            return normalize_path(before + new_part + after)
    return normalize_path(text.split(" => ", 1)[1])


def parse_numstat(repo: Path) -> dict[str, tuple[int | None, int | None, bool]]:
    output = run_git(repo, "diff", "--cached", "--numstat", "-M", "-C")
    stat_map: dict[str, tuple[int | None, int | None, bool]] = {}
    for raw in output.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t", 2)
        if len(parts) != 3:
            continue
        add_s, del_s, path_field = parts
        path = resolve_rename_path(path_field)
        if add_s == "-" or del_s == "-":
            stat_map[path] = (None, None, True)
            continue
        try:
            stat_map[path] = (int(add_s), int(del_s), False)
        except ValueError:
            stat_map[path] = (None, None, True)
    return stat_map


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


def parse_symbols(repo: Path, max_symbols_per_file: int = 3) -> dict[str, list[str]]:
    diff = run_git(repo, "diff", "--cached", "-M", "-C", "--unified=0", "--no-color")
    symbols: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    current_path: str | None = None

    for line in diff.splitlines():
        if line.startswith("diff --git "):
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


def generate_report(changes: list[FileChange], max_files: int) -> str:
    if not changes:
        return "未检测到暂存区变更，工作区也没有可暂存的变更。"

    change_type = infer_change_type(changes)
    display_scope, scope = pick_scope(changes)
    overview = short_overview(change_type, display_scope)
    commit_line = suggested_commit(change_type, scope, display_scope)

    status_counter = Counter(item.status for item in changes)
    total_add = sum(item.added or 0 for item in changes if not item.binary)
    total_del = sum(item.deleted or 0 for item in changes if not item.binary)
    binary_count = sum(1 for item in changes if item.binary)

    binary_suffix = f"，二进制文件 {binary_count} 个" if binary_count else ""
    file_details = "\n".join(summarize_files(changes, max_files=max_files))
    risk_text = "\n".join(build_risks(changes))

    return (
        "# 暂存区变更中文描述\n\n"
        "## 一句话概述\n"
        f"{overview}\n\n"
        "## 建议提交信息\n"
        f"`{commit_line}`\n\n"
        "## 详细说明\n"
        f"- 变更类型：`{change_type}`\n"
        f"- 影响文件：{len(changes)} 个（新增 {status_counter['A']}，修改 {status_counter['M']}，删除 {status_counter['D']}，重命名 {status_counter['R']}，复制 {status_counter['C']}）\n"
        f"- 行数统计：+{total_add} / -{total_del}{binary_suffix}\n"
        "- 主要改动：\n"
        f"{file_details}\n\n"
        "## 风险与回归建议\n"
        f"{risk_text}\n"
    )


def enrich_changes(repo: Path, changes: list[FileChange]) -> list[FileChange]:
    stat_map = parse_numstat(repo)
    symbol_map = parse_symbols(repo)
    for item in changes:
        stats = stat_map.get(item.path)
        if stats:
            item.added, item.deleted, item.binary = stats
        item.kind = classify_file_kind(item.path)
        item.symbols = symbol_map.get(item.path, [])
    return changes


def validate_repo(repo: Path) -> None:
    run_git(repo, "rev-parse", "--is-inside-work-tree")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="提取当前项目暂存区（staged）变更并生成规范中文描述。"
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
        validate_repo(repo)
        changes = parse_name_status(repo)
        if not changes:
            print("暂存区为空，正在暂存仓库内的所有变更（git add -A）。", file=sys.stderr)
            run_git(repo, "add", "-A", "--", ":/")
            changes = parse_name_status(repo)
        enrich_changes(repo, changes)
        report = generate_report(changes, max_files=args.max_files)
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
