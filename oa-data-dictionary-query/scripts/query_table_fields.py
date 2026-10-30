#!/usr/bin/env python3
"""
OA 数据字典表字段查询脚本

用法:
  python scripts/query_table_fields.py meeting
  python scripts/query_table_fields.py hrmresource --json
"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAPPING_RELATIVE_CANDIDATES = (
    Path("assets/数据字典/table_mapping.md"),
)

DATA_ROOT_RELATIVE_CANDIDATES = (
    Path("assets/数据字典"),
)

HEADER_HINTS = (
    "字段",
    "field",
    "列名",
    "名称",
    "类型",
    "长度",
    "说明",
    "备注",
    "注释",
    "默认",
    "可空",
    "nullable",
)


def normalize_table_name(table_name: str) -> str:
    return table_name.strip().lower()


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"无法识别文件编码: {path}")


def resolve_mapping_file(base_dir: Path) -> Optional[Path]:
    for rel_path in MAPPING_RELATIVE_CANDIDATES:
        mapping_path = base_dir / rel_path
        if mapping_path.exists():
            return mapping_path
    return None


def parse_mapping(mapping_text: str) -> Dict[str, Dict[str, str]]:
    module = ""
    mapping: Dict[str, Dict[str, str]] = {}

    module_pattern = re.compile(r"^\s*####\s+(.+?)\s*$")
    item_pattern = re.compile(r"^\s*-\s*`([^`]+)`\s*→\s*(.+?)\s*$")

    for line in mapping_text.splitlines():
        module_match = module_pattern.match(line)
        if module_match:
            module = module_match.group(1).strip()
            continue

        item_match = item_pattern.match(line)
        if item_match:
            table = normalize_table_name(item_match.group(1))
            filename = item_match.group(2).strip()
            mapping[table] = {"module": module, "filename": filename}

    return mapping


def find_suggestions(table_name: str, all_tables: List[str]) -> List[str]:
    prefix_matches = [name for name in all_tables if name.startswith(table_name)]
    contains_matches = [name for name in all_tables if table_name in name and name not in prefix_matches]
    close_matches = difflib.get_close_matches(table_name, all_tables, n=10, cutoff=0.5)

    merged: List[str] = []
    for group in (prefix_matches, contains_matches, close_matches):
        for name in group:
            if name not in merged:
                merged.append(name)
            if len(merged) >= 10:
                return merged
    return merged


def resolve_html_path(base_dir: Path, module: str, filename: str) -> Tuple[Optional[Path], List[Path]]:
    candidates: List[Path] = []
    for root in DATA_ROOT_RELATIVE_CANDIDATES:
        candidates.append(base_dir / root / module / filename)

    for path in candidates:
        if path.exists():
            return path, candidates
    return None, candidates


def clean_cell_text(raw_cell_html: str) -> str:
    value = re.sub(r"(?is)<br\s*/?>", "\n", raw_cell_html)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    return " ".join(value.split())


def extract_tables(html_text: str) -> List[List[List[str]]]:
    cleaned = re.sub(r"(?is)<script\b.*?</script>", "", html_text)
    cleaned = re.sub(r"(?is)<style\b.*?</style>", "", cleaned)

    table_blocks = re.findall(r"(?is)<table\b.*?</table>", cleaned)
    tables: List[List[List[str]]] = []

    for table_html in table_blocks:
        row_blocks = re.findall(r"(?is)<tr\b.*?</tr>", table_html)
        rows: List[List[str]] = []
        for row_html in row_blocks:
            cell_blocks = re.findall(r"(?is)<t[dh]\b.*?</t[dh]>", row_html)
            cells = [clean_cell_text(cell_html) for cell_html in cell_blocks]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)

    return tables


def score_header(header_row: List[str]) -> int:
    score = 0
    for cell in header_row:
        normalized = cell.lower()
        if any(hint in normalized for hint in HEADER_HINTS):
            score += 2
        if len(cell) <= 30:
            score += 1
    if len(header_row) >= 3:
        score += 2
    return score


def pick_field_table(tables: List[List[List[str]]]) -> Optional[List[List[str]]]:
    if not tables:
        return None
    best = max(tables, key=lambda t: score_header(t[0]) if t else -1)
    return best


def rows_to_records(rows: List[List[str]]) -> List[Dict[str, str]]:
    if not rows:
        return []

    header_index = 0
    best_score = -1
    for idx, row in enumerate(rows):
        row_score = score_header(row)
        if row_score > best_score:
            best_score = row_score
            header_index = idx

    if best_score >= 4:
        header = rows[header_index]
        data_rows = rows[header_index + 1 :]
    else:
        max_cols = max(len(r) for r in rows)
        header = [f"列{i + 1}" for i in range(max_cols)]
        data_rows = rows

    records: List[Dict[str, str]] = []
    for row in data_rows:
        normalized_row = row + [""] * (len(header) - len(row))
        normalized_row = normalized_row[: len(header)]
        if not any(normalized_row):
            continue
        record = {header[i]: normalized_row[i] for i in range(len(header))}
        records.append(record)

    return records


def print_markdown_table(records: List[Dict[str, str]]) -> None:
    if not records:
        print("未提取到字段记录。")
        return

    headers = list(records[0].keys())
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for record in records:
        row = [record.get(h, "").replace("|", "\\|") for h in headers]
        print("| " + " | ".join(row) + " |")


def main() -> int:
    parser = argparse.ArgumentParser(description="查询 OA 数据字典表字段信息")
    parser.add_argument("table_name", help="数据库表名")
    parser.add_argument(
        "--base-dir",
        default=str(Path(__file__).resolve().parents[1]),
        help="技能根目录（默认脚本上两级目录）",
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON 格式输出")
    parser.add_argument("--max-rows", type=int, default=200, help="最大返回字段行数")
    args = parser.parse_args()

    requested = args.table_name
    table_name = normalize_table_name(requested)
    base_dir = Path(args.base_dir).resolve()

    mapping_file = resolve_mapping_file(base_dir)
    if not mapping_file:
        print("未找到映射文件：assets/数据字典/table_mapping.md")
        return 2

    mapping_text = read_text_with_fallback(mapping_file)
    mapping = parse_mapping(mapping_text)

    item = mapping.get(table_name)
    if not item:
        all_tables = sorted(mapping.keys())
        suggestions = find_suggestions(table_name, all_tables)
        print(f"未找到表 {table_name} 的数据字典信息，请确认表名是否正确。")
        if suggestions:
            print("\n你可能想查：")
            for name in suggestions:
                print(f"- {name}")
        return 3

    module = item["module"]
    filename = item["filename"]
    html_path, candidate_paths = resolve_html_path(base_dir, module, filename)

    if not html_path:
        print(f"数据字典文件不存在：{candidate_paths[0]}")
        if len(candidate_paths) > 1:
            print("已尝试其他候选路径：")
            for path in candidate_paths[1:]:
                print(f"- {path}")
        return 4

    html_text = read_text_with_fallback(html_path)
    tables = extract_tables(html_text)
    selected = pick_field_table(tables)
    records = rows_to_records(selected or [])
    records = records[: max(args.max_rows, 0)]

    result = {
        "input_table_name": requested,
        "normalized_table_name": table_name,
        "module": module,
        "mapping_file": str(mapping_file),
        "html_file": str(html_path),
        "record_count": len(records),
        "fields": records,
    }

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"输入表名: {requested}")
    print(f"标准化表名: {table_name}")
    print(f"所属模块: {module}")
    print(f"映射文件: {mapping_file}")
    print(f"命中文件: {html_path}")
    print(f"字段记录数: {len(records)}\n")
    print_markdown_table(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
