#!/usr/bin/env python3
"""Plan and apply compact Markdown table layout without regenerating documents."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    import markdown_it
    from markdown_it import MarkdownIt
    from markdown_it.rules_block.table import escapedSplit
except ImportError:
    print("Missing dependency: markdown-it-py 4.x. Select an existing Python environment.", file=sys.stderr)
    raise SystemExit(2)

VERSION = 1
PARSER_MAJOR = markdown_it.__version__.split(".")[0]
if PARSER_MAJOR != "4":
    print("This helper requires markdown-it-py 4.x.", file=sys.stderr)
    raise SystemExit(2)

MD = MarkdownIt("commonmark", {"html": True}).enable("table").enable("strikethrough")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BARE_LINK = re.compile(r"(?i)(?:https?://|www\.)\S+|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
EXTENSION_MARKUP = re.compile(r"==[^=\n]+==|(?<!~)~[^~\n]+~(?!~)|\^[^^\n]+\^|\[\^[^\]]+\]|(?<!\w):[a-z0-9_+-]+:(?!\w)|\${1,2}[^\s$][^$\n]*\${1,2}|\{[.#][^}\n]+\}", re.I)


class LayoutError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def percentages(headers: list[str], rows: list[list[str]]) -> list[str]:
    count = len(headers)
    if not 1 <= count <= 50:
        raise LayoutError("tables with more than 50 columns need manual review")
    empty = [all(not row[i].strip() for row in rows) for i in range(count)]
    weights: list[int] = []
    for i, header in enumerate(headers):
        name = header.strip()
        if empty[i]:
            weights.append(90 if name else 28)
        elif re.search(r"规则|说明|描述|备注|description|remark", name, re.I):
            weights.append(220)
        elif re.search(r"编码|字段名|field|code|level\s*[12]", name, re.I):
            weights.append(200)
        elif re.search(r"样例|示例|example|sample", name, re.I):
            weights.append(180)
        else:
            weights.append(125)
    active = list(range(count))
    values = [0] * count
    minimum = min(500, 9500 // count)
    floors = [150 if empty[i] and not headers[i].strip() else minimum for i in range(count)]
    remaining = 10000
    while active:
        total = sum(weights[i] for i in active)
        below = [i for i in active if remaining * weights[i] / total < floors[i]]
        if below:
            for i in below:
                values[i] = floors[i]
                remaining -= floors[i]
            active = [i for i in active if i not in below]
            continue
        raw = {i: remaining * weights[i] / total for i in active}
        for i in active:
            values[i] = int(raw[i])
        order = sorted(active, key=lambda i: raw[i] - values[i], reverse=True)
        for i in order[:10000 - sum(values)]:
            values[i] += 1
        break
    return [f"{value / 100:.2f}".rstrip("0").rstrip(".") + "%" for value in values]


def minimum_width(count: int) -> int:
    if count <= 5:
        return 480
    if count <= 8:
        return 640
    return max(800, count * 56)


class CellSnapshot(HTMLParser):
    """Retain rendered cell markup while ignoring cell and table attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.cells: list[tuple[str, str]] = []
        self.current: list[str] | None = None
        self.kind = ""
        self.depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.current is None and tag in {"th", "td"}:
            self.current, self.kind, self.depth = [], tag, 0
        elif self.current is not None:
            self.current.append(self.get_starttag_text())
            if tag not in VOID:
                self.depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.current is not None:
            self.current.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if tag == self.kind and self.depth == 0:
            self.cells.append((self.kind, "".join(self.current)))
            self.current = None
        else:
            self.current.append(f"</{tag}>")
            if tag not in VOID:
                self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.handle_data(f"<!--{data}-->")


def snapshot(fragment: str) -> list[tuple[str, str]]:
    parser = CellSnapshot()
    parser.feed(fragment)
    parser.close()
    if parser.current is not None:
        raise LayoutError("unbalanced cell markup")
    return parser.cells


class PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain(fragment: str) -> str:
    parser = PlainText()
    parser.feed(fragment)
    return "".join(parser.parts)


def set_token_style(token: Any, additions: str) -> None:
    existing = token.attrGet("style") or ""
    token.attrSet("style", (existing.rstrip("; ") + "; " if existing else "") + additions)


def raw_cells(line: str) -> list[str]:
    cells = escapedSplit(line.strip())
    if cells and not cells[0]:
        cells.pop(0)
    if cells and not cells[-1]:
        cells.pop()
    return cells


def format_markdown_table(tokens: list[Any], source_lines: list[str], env: dict[str, Any]) -> str:
    opening = tokens[0]
    if opening.level != 0:
        raise LayoutError("nested Markdown table")
    head_end = next(i for i, token in enumerate(tokens) if token.type == "thead_close")
    columns = sum(token.type == "th_open" for token in tokens[:head_end])
    for index in range(opening.map[0] + 2, opening.map[1]):
        if len(raw_cells(source_lines[index])) > columns:
            raise LayoutError("row has more cells than the header")
    for token in tokens:
        if token.type != "inline":
            continue
        if re.search(r"\[\^[^\]\r\n]+\]", token.content):
            raise LayoutError("footnote references may have renderer-dependent semantics")
        for child in token.children or []:
            if child.type == "text" and BARE_LINK.search(child.content):
                raise LayoutError("bare URL or email may depend on renderer autolinking")
            if child.type == "text" and EXTENSION_MARKUP.search(child.content):
                raise LayoutError("inline extension may have renderer-dependent semantics")
            if child.type == "html_inline" and not re.fullmatch(r"<(?:br|wbr)\s*/?>", child.content.strip(), re.I):
                raise LayoutError("inline HTML may have renderer-dependent semantics")
    before = MD.renderer.render(tokens, MD.options, env)
    original_cells = snapshot(before)
    if len(original_cells) % columns:
        raise LayoutError("unexpected table structure")
    values = [plain(value) for _, value in original_cells]
    headers = values[:columns]
    rows = [values[i:i + columns] for i in range(columns, len(values), columns)]
    widths = percentages(headers, rows)
    for token in tokens:
        if token.type == "table_open":
            token.attrSet("class", "dense wide-table")
            set_token_style(token, f"min-width: {minimum_width(columns)}px; table-layout: fixed; width: 100%")
        elif token.type == "th_open":
            set_token_style(token, "padding: 4px; white-space: normal; overflow-wrap: anywhere; word-break: break-word")
        elif token.type == "td_open":
            set_token_style(token, "padding: 4px; overflow-wrap: anywhere; word-break: break-word; vertical-align: top")
    rendered = MD.renderer.render(tokens, MD.options, env)
    group = "<colgroup>" + "".join(f'<col style="width: {width}">' for width in widths) + "</colgroup>\n"
    rendered, count = re.subn(r"^(<table\b[^>]*>\n)", lambda m: m.group(1) + group, rendered, count=1)
    if count != 1 or snapshot(rendered) != original_cells:
        raise LayoutError("rendered cell verification failed")
    return '<div class="table-container" style="width: 100%; max-width: 100%; overflow-x: auto">\n' + rendered + "</div>"


@dataclass
class Node:
    tag: str
    start: int
    tag_end: int
    attrs: dict[str, str | None]
    parent: Node | None
    children: list[Node] = field(default_factory=list)
    text: list[str] = field(default_factory=list)
    end: int | None = None


class MarkupTree(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.offsets = [0]
        for match in re.finditer("\n", source):
            self.offsets.append(match.end())
        self.root = Node("", 0, 0, {}, None)
        self.stack = [self.root]
        self.invalid = False

    def source_offset(self) -> int:
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def add(self, tag: str, attrs: list[tuple[str, str | None]], push: bool) -> None:
        start = self.source_offset()
        end = start + len(self.get_starttag_text())
        if len({key for key, _ in attrs}) != len(attrs):
            self.invalid = True
        node = Node(tag, start, end, dict(attrs), self.stack[-1])
        self.stack[-1].children.append(node)
        if push and tag not in VOID:
            self.stack.append(node)
        else:
            node.end = end

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.add(tag, attrs, True)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.add(tag, attrs, False)

    def handle_endtag(self, tag: str) -> None:
        if len(self.stack) == 1 or self.stack[-1].tag != tag:
            self.invalid = True
            return
        node = self.stack.pop()
        end = self.source.find(">", self.source_offset())
        if end < 0:
            self.invalid = True
        else:
            node.end = end + 1

    def handle_data(self, data: str) -> None:
        for node in self.stack[1:]:
            node.text.append(data)


def walk(node: Node) -> list[Node]:
    return [node] + [child for item in node.children for child in walk(item)]


def styles(node: Node) -> dict[str, str]:
    value = node.attrs.get("style")
    if not isinstance(value, str) or any(character in value for character in "{}()"):
        raise LayoutError("unsupported or missing inline style")
    result: dict[str, str] = {}
    for declaration in value.split(";"):
        if not declaration.strip():
            continue
        key, separator, val = declaration.partition(":")
        key = key.strip().lower()
        if not separator or not key or key in result:
            raise LayoutError("complex inline style")
        result[key] = val.strip()
    return result


def styled_tag(source: str, node: Node, overrides: dict[str, str]) -> str:
    properties = styles(node)
    properties.update(overrides)
    tag = source[node.start:node.tag_end]
    index = 1
    while index < len(tag) and not tag[index].isspace() and tag[index] not in "/>":
        index += 1
    value_span: tuple[int, int] | None = None
    while index < len(tag):
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag) or tag[index] in "/>":
            break
        start = index
        while index < len(tag) and not tag[index].isspace() and tag[index] not in "=/>":
            index += 1
        name = tag[start:index].lower()
        if not name:
            raise LayoutError("unsupported HTML attribute")
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag) or tag[index] != "=":
            continue
        index += 1
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag):
            raise LayoutError("missing HTML attribute value")
        if tag[index] in "\"'":
            quote = tag[index]
            value_start = index + 1
            value_end = tag.find(quote, value_start)
            if value_end < 0:
                raise LayoutError("unclosed HTML attribute")
            index = value_end + 1
        else:
            value_start = index
            while index < len(tag) and not tag[index].isspace() and tag[index] not in ">":
                index += 1
            value_end = index
            if name == "style":
                raise LayoutError("unquoted style attribute")
        if name == "style":
            value_span = (value_start, value_end)
            break
    if value_span is None:
        raise LayoutError("missing style attribute")
    rendered = "; ".join(f"{key}: {value}" for key, value in properties.items())
    return tag[:value_span[0]] + html.escape(rendered, quote=True) + tag[value_span[1]:]


def format_html_block(source: str, min_columns: int) -> tuple[str, int, list[str]]:
    tree = MarkupTree(source)
    tree.feed(source)
    tree.close()
    tables = [node for node in walk(tree.root) if node.tag == "table"]
    if not tables:
        return source, 0, []
    if tree.invalid or len(tree.stack) != 1:
        return source, 0, ["unbalanced HTML block"]
    edits: list[tuple[int, int, str]] = []
    skipped: list[str] = []
    formatted = 0
    for table in tables:
        classes = str(table.attrs.get("class") or "").split()
        if "wide-table" not in classes:
            skipped.append("unmanaged HTML table")
            continue
        try:
            if table.end is None or any(node is not table and node.tag == "table" for node in walk(table)):
                raise LayoutError("nested or unclosed HTML table")
            group = next((node for node in table.children if node.tag == "colgroup"), None)
            cols = [node for node in (group.children if group else []) if node.tag == "col"]
            if not cols:
                raise LayoutError("missing colgroup")
            if len(cols) < min_columns:
                continue
            cells = [node for node in walk(table) if node.tag in {"th", "td"}]
            if any("colspan" in cell.attrs or "rowspan" in cell.attrs for cell in cells):
                raise LayoutError("merged HTML cells")
            rows = [node for node in walk(table) if node.tag == "tr"]
            matrix = [[cell for cell in row.children if cell.tag in {"th", "td"}] for row in rows]
            if not matrix or any(len(row) != len(cols) for row in matrix):
                raise LayoutError("irregular HTML rows")
            headers = ["".join(cell.text) for cell in matrix[0]]
            data = [["".join(cell.text) for cell in row] for row in matrix[1:]]
            table_style = styles(table)
            col_styles = [styles(col) for col in cols]
            current = [style.get("width", "") for style in col_styles]
            if any(not re.fullmatch(r"\d+(?:\.\d+)?(?:px|%)", width) for width in current):
                raise LayoutError("unsupported column width")
            wrapper = table.parent and table.parent.tag == "div" and "table-container" in str(table.parent.attrs.get("class") or "").split()
            cell_styles = [styles(cell) for cell in cells]
            floor = min(500, 9500 // len(cols)) / 100
            compact = (
                wrapper and all(width.endswith("%") for width in current)
                and abs(sum(float(width[:-1]) for width in current) - 100) < 0.02
                and all(
                    float(current[i][:-1]) >= floor - 0.01
                    for i in range(len(cols))
                    if headers[i].strip() or any(row[i].strip() for row in data)
                )
                and table_style.get("table-layout") == "fixed"
                and table_style.get("width") == "100%"
                and re.fullmatch(r"\d+px", table_style.get("min-width", "")) is not None
                and int(table_style["min-width"][:-2]) <= minimum_width(len(cols))
                and all(
                    style.get("padding") == "4px"
                    and style.get("overflow-wrap") == "anywhere"
                    and style.get("word-break") == "break-word"
                    and (cell.tag != "th" or style.get("white-space") == "normal")
                    for cell, style in zip(cells, cell_styles)
                )
            )
            if compact:
                continue
            widths = percentages(headers, data)
            local: list[tuple[int, int, str]] = []
            local.append((table.start, table.tag_end, styled_tag(source, table, {
                "min-width": f"{minimum_width(len(cols))}px", "table-layout": "fixed", "width": "100%"
            })))
            for col, width in zip(cols, widths):
                local.append((col.start, col.tag_end, styled_tag(source, col, {"width": width})))
            for cell in cells:
                overrides = {"padding": "4px", "overflow-wrap": "anywhere", "word-break": "break-word"}
                if cell.tag == "th":
                    overrides["white-space"] = "normal"
                else:
                    overrides["vertical-align"] = "top"
                local.append((cell.start, cell.tag_end, styled_tag(source, cell, overrides)))
            if not wrapper:
                newline = "\r\n" if "\r\n" in source else "\r" if "\r" in source and "\n" not in source else "\n"
                local.append((table.start, table.start, '<div class="table-container" style="width: 100%; max-width: 100%; overflow-x: auto">' + newline))
                local.append((table.end, table.end, newline + "</div>"))
            edits.extend(local)
            formatted += 1
        except LayoutError as exc:
            skipped.append(str(exc))
    result = source
    for start, end, replacement in sorted(edits, key=lambda item: (item[0], item[1]), reverse=True):
        result = result[:start] + replacement + result[end:]
    if snapshot(source) != snapshot(result):
        raise LayoutError("HTML cell verification failed")
    return result, formatted, skipped


def transform(text: str, min_columns: int) -> tuple[str, int, list[dict[str, Any]]]:
    env: dict[str, Any] = {}
    tokens = MD.parse(text, env)
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits: list[tuple[int, int, str]] = []
    skipped: list[dict[str, Any]] = []
    formatted = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "table_open":
            end = index + 1
            while end < len(tokens) and tokens[end].type != "table_close":
                end += 1
            if end == len(tokens) or not token.map:
                raise LayoutError("unclosed Markdown table")
            part = tokens[index:end + 1]
            columns = sum(item.type == "th_open" for item in part)
            if columns >= min_columns:
                start_at, end_at = offsets[token.map[0]], offsets[token.map[1]]
                old = text[start_at:end_at]
                try:
                    replacement = format_markdown_table(part, lines, env)
                    newline = "\r\n" if "\r\n" in old else "\r" if "\r" in old and "\n" not in old else "\n"
                    replacement = replacement.replace("\n", newline)
                    if old.endswith(("\r", "\n")):
                        replacement += newline
                    edits.append((start_at, end_at, replacement))
                    formatted += 1
                except LayoutError as exc:
                    skipped.append({"line": token.map[0] + 1, "reason": str(exc)})
            index = end
        elif token.type == "html_block" and token.map and "<table" in token.content.lower():
            start_at, end_at = offsets[token.map[0]], offsets[token.map[1]]
            old = text[start_at:end_at]
            new, count, reasons = format_html_block(old, min_columns)
            if new != old:
                edits.append((start_at, end_at, new))
                formatted += count
            skipped.extend({"line": token.map[0] + 1, "reason": reason} for reason in reasons)
        index += 1
    result = text
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result, formatted, skipped


def files_for(inputs: list[str], recursive: bool) -> list[Path]:
    result: dict[str, Path] = {}
    for item in inputs:
        path = Path(item).expanduser().absolute()
        if path.is_symlink():
            raise LayoutError(f"symlink input is not supported: {path}")
        if path.is_file():
            if path.suffix.lower() != ".md":
                raise LayoutError(f"not a Markdown file: {path}")
            candidates = [path]
        elif path.is_dir():
            candidates = []
            if recursive:
                for root, directories, files in os.walk(path, followlinks=False):
                    directories[:] = [d for d in directories if not d.startswith(".") and not (Path(root) / d).is_symlink()]
                    candidates.extend(Path(root) / name for name in files if name.lower().endswith(".md"))
            else:
                candidates = [child for child in path.iterdir() if child.suffix.lower() == ".md" and child.is_file()]
        else:
            raise LayoutError(f"input does not exist: {path}")
        for candidate in candidates:
            if candidate.is_symlink():
                continue
            resolved = candidate.resolve(strict=True)
            result[os.path.normcase(str(resolved))] = resolved
    return sorted(result.values(), key=lambda path: os.path.normcase(str(path)))


def plan(args: argparse.Namespace) -> dict[str, Any]:
    if not 2 <= args.min_columns <= 50:
        raise LayoutError("--min-columns must be between 2 and 50")
    files = files_for(args.inputs, args.recursive)
    entries, skipped, tables = [], [], 0
    for path in files:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append({"path": str(path), "reason": "not UTF-8"})
            continue
        result, count, reasons = transform(text, args.min_columns)
        skipped.extend({"path": str(path), **reason} for reason in reasons)
        if result != text:
            entries.append({"path": str(path), "source_sha256": sha(raw), "result_sha256": sha(result.encode("utf-8")), "tables": count})
            tables += count
    data = {"version": VERSION, "parser_major": PARSER_MAJOR, "min_columns": args.min_columns, "entries": entries, "skipped": skipped}
    output = Path(args.output).expanduser().absolute()
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError as exc:
        raise LayoutError(f"plan already exists; choose a new path: {output}") from exc
    return {"plan": str(output), "scanned": len(files), "files": len(entries), "tables": tables, "skipped": skipped}


def apply(args: argparse.Namespace) -> dict[str, Any]:
    data = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != VERSION or data.get("parser_major") != PARSER_MAJOR:
        raise LayoutError("invalid or incompatible plan")
    columns = data.get("min_columns")
    entries = data.get("entries")
    if not isinstance(columns, int) or not 2 <= columns <= 50 or not isinstance(entries, list):
        raise LayoutError("invalid plan contents")
    prepared: list[tuple[Path, str, bytes]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise LayoutError("invalid plan entry")
        path = Path(entry["path"])
        if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.suffix.lower() != ".md":
            raise LayoutError(f"invalid or missing Markdown file: {path}")
        identity = os.path.normcase(str(path.resolve(strict=True)))
        if identity in seen:
            raise LayoutError(f"duplicate plan entry: {path}")
        seen.add(identity)
        raw = path.read_bytes()
        if sha(raw) != entry.get("source_sha256"):
            raise LayoutError(f"source changed since planning: {path}")
        text = raw.decode("utf-8")
        result, _, _ = transform(text, columns)
        result_bytes = result.encode("utf-8")
        if sha(result_bytes) != entry.get("result_sha256"):
            raise LayoutError(f"planned result changed; create a new plan: {path}")
        prepared.append((path, entry["source_sha256"], result_bytes))
    written: list[str] = []
    try:
        for path, expected, result in prepared:
            if path.is_symlink() or sha(path.read_bytes()) != expected:
                raise LayoutError(f"source changed immediately before writing: {path}")
            mode = stat.S_IMODE(path.stat().st_mode)
            fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(result)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, mode)
                if path.is_symlink() or sha(path.read_bytes()) != expected:
                    raise LayoutError(f"source changed immediately before replacement: {path}")
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            written.append(str(path))
    except (OSError, LayoutError) as exc:
        raise LayoutError(f"{exc}; already updated: {json.dumps(written, ensure_ascii=False)}") from exc
    return {"files": len(written), "tables": sum(entry.get("tables", 0) for entry in entries), "updated": written, "skipped": data.get("skipped", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan", help="Read files and create a plan without changing documents.")
    planner.add_argument("inputs", nargs="+", help="Markdown files or directories.")
    planner.add_argument("--output", required=True, help="New plan file; existing files are never overwritten.")
    planner.add_argument("--recursive", action="store_true", help="Include non-hidden subdirectories.")
    planner.add_argument("--min-columns", type=int, default=4)
    executor = commands.add_parser("apply", help="Apply a plan after checking the source hashes.")
    executor.add_argument("--plan", required=True)
    args = parser.parse_args()
    try:
        result = plan(args) if args.command == "plan" else apply(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (LayoutError, OSError, ValueError, UnicodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
