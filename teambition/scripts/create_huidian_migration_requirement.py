"""Create the Huidian 24-26 contract migration requirement and its subtasks in Teambition.

Restart-safe: reuses the exact-title dedup and parent/child verification helpers
from create_production_release_work_package.py, so reruns only add missing items.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teambition_mcp_server as server
from parse_interface_subtasks import parse_breakdown
from create_production_release_work_package import (
    PROJECT_ID,
    SPRINT_NAME,
    create_child,
    create_parent,
    direct_child_titles,
    get_detail,
    matching_parents,
    normalize,
    resolve_manager_choice,
    verify_parent,
)

DOCUMENT_NAME = "甄零合同系统-慧点合同数据迁移子任务拆解.md"
EXPECTED_CHILDREN = 14


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    items = parse_breakdown(root / DOCUMENT_NAME)
    if len(items) != 1 or len(items[0]["subtasks"]) != EXPECTED_CHILDREN:
        raise RuntimeError(
            f"源文档解析结果不符合预期：{len(items)} 条父需求 / "
            f"{[len(item['subtasks']) for item in items]} 条子任务"
        )

    server._ensure_logged_in()
    client = server._get_client()
    sprint_id = server._resolve_sprint_id_by_name(client, PROJECT_ID, SPRINT_NAME)
    if not sprint_id:
        raise RuntimeError(f"未找到迭代：{SPRINT_NAME}")
    manager = resolve_manager_choice(client)

    report: list[dict[str, object]] = []
    for item in items:
        parents = matching_parents(client, item["title"])
        if len(parents) > 1:
            raise RuntimeError(f"发现多个同名父需求，停止创建：{item['title']}")

        created_parent = False
        if parents:
            parent = parents[0]
            if normalize(parent.get("note")) != normalize(item["acceptance"]):
                raise RuntimeError(
                    f"已存在同名父需求但验收备注不一致：{item['title']} ({parent.get('_id')})"
                )
        else:
            parent = create_parent(client, item, sprint_id, manager)
            created_parent = True

        parent_id = str(parent["_id"])
        existing_children = direct_child_titles(parent)
        created_children: list[dict[str, object]] = []
        for child_title in item["subtasks"]:
            if normalize(child_title) in existing_children:
                continue
            # Re-read immediately before every create to avoid duplicate POSTs.
            latest = get_detail(client, parent_id)
            if normalize(child_title) in direct_child_titles(latest):
                continue
            created_children.append(create_child(client, parent_id, child_title))

        verified = get_detail(client, parent_id)
        verify_parent(verified, item)
        record = {
            "title": item["title"],
            "id": parent_id,
            "uniqueId": verified.get("uniqueId"),
            "createdParent": created_parent,
            "createdChildren": len(created_children),
            "subtaskCount": (verified.get("subtaskCount") or {}).get("total"),
        }
        report.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    print(
        json.dumps(
            {
                "status": "success",
                "requirements": len(report),
                "subtasks": sum(int(x["subtaskCount"]) for x in report),
                "items": report,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()