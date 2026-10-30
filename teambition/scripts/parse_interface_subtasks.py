"""Parse interface task breakdown Markdown into a deterministic creation manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path


PARENT_PREFIX = re.compile(r"^\d+\.\s*")
CHILD_PREFIX = re.compile(r"^\d+\.\d+\s*")


def parse_breakdown(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| 父任务 "):
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3:
            continue

        parent_raw, children_raw, acceptance = cells
        if not re.match(r"^\d+\.\s*", parent_raw):
            continue

        children = [
            CHILD_PREFIX.sub("", child).strip()
            for child in children_raw.split("<br>")
            if child.strip()
        ]
        rows.append(
            {
                "title": PARENT_PREFIX.sub("", parent_raw).strip(),
                "acceptance": acceptance,
                "subtasks": children,
            }
        )

    return rows


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    items = parse_breakdown(root / "接口子任务拆解文档.md")
    print(
        json.dumps(
            {
                "requirements": len(items),
                "subtasks": sum(len(item["subtasks"]) for item in items),
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
