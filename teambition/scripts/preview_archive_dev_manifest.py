"""Read-only preview for the archive-system development sheet.

Resolves the live category option, sprint, and product-manager choice, then
deduplicates each parent requirement title against all open and closed tasks.
No task is created, modified, or deleted by this script.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teambition_mcp_server as server
from parse_interface_subtasks import parse_breakdown

PROJECT_ID = "60e6912e8eb2da2a576f2abb"
DOCUMENT_NAME = "档案系统-开发清单_林树煌任务_子任务拆解.md"
CATEGORY_FIELD_ID = "5d1b3638ce9f165cd5d980b5"
PRODUCT_MANAGER_FIELD_ID = "69ca2ba47ad8b6f61a76ff2f"
CATEGORY_NAME = "档案系统"
SPRINT_NAME = "档案系统 v1.0"
PRODUCT_MANAGER_NAME = "许媛媛"
EXPECTED_PARENTS = 11
EXPECTED_CHILDREN_PER_PARENT = 15


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def deep_find_choice(value: Any, name: str) -> dict[str, str] | None:
    """Find an exact named option in nested custom-field metadata."""
    if isinstance(value, dict):
        title = value.get("title") or value.get("value") or value.get("name") or value.get("label")
        option_id = value.get("_id") or value.get("id") or value.get("valueId")
        if normalize(title) == name and option_id:
            return {"_id": str(option_id), "title": name}
        for child in value.values():
            found = deep_find_choice(child, name)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = deep_find_choice(child, name)
            if found:
                return found
    return None


def collect_commongroup_options(client: Any) -> dict[str, str]:
    """Map option title -> id from field metadata and from existing tasks."""
    title_to_id: dict[str, str] = {}

    for path in (f"/api/v2/customfields/{CATEGORY_FIELD_ID}", f"/api/customfields/{CATEGORY_FIELD_ID}"):
        response = client.get(path, headers={"X-Tenant-Id": server.ORG_ID})
        if response.status_code != 200:
            continue
        payload = response.json()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                title = node.get("title") or node.get("value") or node.get("name")
                option_id = node.get("_id") or node.get("id")
                if isinstance(title, str) and option_id and len(str(option_id)) == 24:
                    title_to_id.setdefault(normalize(title), str(option_id))
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(payload)
        if title_to_id:
            break

    tasks = server._collect_project_tasks_raw(client, PROJECT_ID, "false", max_pages=30)
    tasks.extend(server._collect_project_tasks_raw(client, PROJECT_ID, "true", max_pages=30))
    for task in tasks:
        for field in task.get("customfields") or []:
            if not isinstance(field, dict) or field.get("_customfieldId") != CATEGORY_FIELD_ID:
                continue
            for item in field.get("value") or []:
                if isinstance(item, dict) and item.get("title") and item.get("_id"):
                    title_to_id.setdefault(normalize(item["title"]), str(item["_id"]))
    return title_to_id


def resolve_sprint_exact(client: Any, name: str) -> tuple[str | None, list[str]]:
    server._refresh_project_sprint_cache(client, PROJECT_ID)
    mapping = server._project_sprint_cache.get(PROJECT_ID, {})
    related = sorted(key for key in mapping if "档案" in key)
    return mapping.get(name), related


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    items = parse_breakdown(root / DOCUMENT_NAME)
    counts = [len(item["subtasks"]) for item in items]
    if len(items) != EXPECTED_PARENTS or any(count != EXPECTED_CHILDREN_PER_PARENT for count in counts):
        raise RuntimeError(f"源文档解析结果不符合预期：{len(items)} 条父任务，子任务数 {counts}")

    server._ensure_logged_in()
    client = server._get_client()

    category_options = collect_commongroup_options(client)
    category_id = category_options.get(CATEGORY_NAME)
    archive_related = {k: v for k, v in category_options.items() if "档案" in k}

    sprint_id, sprint_related = resolve_sprint_exact(client, SPRINT_NAME)

    manager_response = client.get(
        f"/api/v2/customfields/{PRODUCT_MANAGER_FIELD_ID}",
        headers={"X-Tenant-Id": server.ORG_ID},
    )
    if manager_response.status_code != 200:
        manager_response = client.get(
            f"/api/customfields/{PRODUCT_MANAGER_FIELD_ID}",
            headers={"X-Tenant-Id": server.ORG_ID},
        )
    manager_choice = None
    if manager_response.status_code == 200:
        manager_choice = deep_find_choice(manager_response.json(), PRODUCT_MANAGER_NAME)
    manager_member = server._search_member_by_name(client, PRODUCT_MANAGER_NAME)

    all_tasks = server._collect_project_tasks_raw(client, PROJECT_ID, "false", max_pages=30)
    all_tasks.extend(server._collect_project_tasks_raw(client, PROJECT_ID, "true", max_pages=30))
    by_id: dict[str, dict[str, Any]] = {}
    for task in all_tasks:
        task_id = str(task.get("_id") or "")
        if task_id:
            by_id[task_id] = task
    project_tasks = [t for t in by_id.values() if t.get("_projectId") == PROJECT_ID]

    preview: list[dict[str, Any]] = []
    for item in items:
        expected_title = normalize(item["title"])
        matches = [t for t in project_tasks if normalize(t.get("content")) == expected_title]
        entry: dict[str, Any] = {
            "title": item["title"],
            "subtaskCount": len(item["subtasks"]),
            "existingMatches": len(matches),
        }
        if matches:
            details = []
            for match in matches:
                detail_response = client.get(
                    f"/api/tasks/{match['_id']}",
                    headers={"X-Tenant-Id": server.ORG_ID},
                )
                detail = detail_response.json() if detail_response.status_code == 200 else {}
                children = {
                    normalize(child.get("content"))
                    for child in (detail.get("subtasks") or [])
                    if isinstance(child, dict) and child.get("content")
                }
                details.append(
                    {
                        "id": match["_id"],
                        "uniqueId": match.get("uniqueId"),
                        "isDone": match.get("isDone"),
                        "subtaskCount": (detail.get("subtaskCount") or {}).get("total"),
                        "existingChildTitles": sorted(children),
                    }
                )
            entry["matches"] = details
        preview.append(entry)

    summary = {
        "document": DOCUMENT_NAME,
        "parents": len(items),
        "subtasks": sum(counts),
        "perParentCounts": counts,
        "category": {"name": CATEGORY_NAME, "id": category_id, "archiveRelatedOptions": archive_related},
        "sprint": {"name": SPRINT_NAME, "id": sprint_id, "archiveRelatedSprints": sprint_related},
        "productManager": {
            "name": PRODUCT_MANAGER_NAME,
            "metadataChoice": manager_choice,
            "organizationMember": bool(manager_member),
        },
        "dedup": {
            "existingParentCount": sum(1 for entry in preview if entry["existingMatches"]),
            "missingParentCount": sum(1 for entry in preview if not entry["existingMatches"]),
        },
        "items": preview,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()