"""Read-only status check for the first archive-dev parent requirement.

Reports whether 项目代码底座搭建 already exists (with its current fields and
children), the live 档案系统 category option if discoverable, and a few
endpoint probes for enumerating commongroup options. Creates nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teambition_mcp_server as server
from preview_archive_dev_manifest import (
    CATEGORY_FIELD_ID,
    CATEGORY_NAME,
    PRODUCT_MANAGER_FIELD_ID,
    PRODUCT_MANAGER_NAME,
    PROJECT_ID,
    SPRINT_NAME,
    collect_commongroup_options,
    deep_find_choice,
    normalize,
    resolve_sprint_exact,
)

PARENT_TITLE = "项目代码底座搭建"


def field_values(task: dict[str, Any], field_id: str) -> list[dict[str, Any]]:
    for field in task.get("customfields") or []:
        if not isinstance(field, dict) or field.get("_customfieldId") != field_id:
            continue
        values = []
        for item in field.get("value") or []:
            if isinstance(item, dict):
                values.append({"_id": item.get("_id"), "title": item.get("title")})
        return values
    return []


def main() -> None:
    server._ensure_logged_in()
    client = server._get_client()

    options = collect_commongroup_options(client)
    archive_options = {k: v for k, v in options.items() if "档案" in k}

    sprint_id, sprint_related = resolve_sprint_exact(client, SPRINT_NAME)

    manager_choice = None
    for path in (
        f"/api/v2/customfields/{PRODUCT_MANAGER_FIELD_ID}",
        f"/api/customfields/{PRODUCT_MANAGER_FIELD_ID}",
    ):
        response = client.get(path, headers={"X-Tenant-Id": server.ORG_ID})
        if response.status_code == 200:
            manager_choice = deep_find_choice(response.json(), PRODUCT_MANAGER_NAME)
            if manager_choice:
                break

    tasks = server._collect_project_tasks_raw(client, PROJECT_ID, "false", max_pages=30)
    tasks.extend(server._collect_project_tasks_raw(client, PROJECT_ID, "true", max_pages=30))
    by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = str(task.get("_id") or "")
        if task_id:
            by_id[task_id] = task

    matches = [
        t
        for t in by_id.values()
        if t.get("_projectId") == PROJECT_ID and normalize(t.get("content")) == PARENT_TITLE
    ]

    details = []
    for match in matches:
        response = client.get(f"/api/tasks/{match['_id']}", headers={"X-Tenant-Id": server.ORG_ID})
        detail = response.json() if response.status_code == 200 else {}
        sprint = detail.get("sprint") if isinstance(detail.get("sprint"), dict) else {}
        details.append(
            {
                "id": match["_id"],
                "uniqueId": match.get("uniqueId"),
                "isDone": match.get("isDone"),
                "sprintId": detail.get("_sprintId") or sprint.get("_id"),
                "sprintName": sprint.get("name"),
                "noteHead": (detail.get("note") or "")[:80],
                "category": field_values(detail, CATEGORY_FIELD_ID),
                "productManager": field_values(detail, PRODUCT_MANAGER_FIELD_ID),
                "subtaskCount": (detail.get("subtaskCount") or {}).get("total"),
                "subtaskTitles": [
                    {"id": child.get("_id"), "title": child.get("content")}
                    for child in detail.get("subtasks") or []
                    if isinstance(child, dict)
                ],
            }
        )

    probes: dict[str, Any] = {}
    probe_specs = {
        "project_customfield": f"/api/projects/{PROJECT_ID}/customfields/{CATEGORY_FIELD_ID}",
        "v2_choices": f"/api/v2/customfields/{CATEGORY_FIELD_ID}/choices?projectId={PROJECT_ID}",
        "v1_choices": f"/api/customfields/{CATEGORY_FIELD_ID}/choices?projectId={PROJECT_ID}",
        "v2_commongroups": f"/api/v2/commongroups?projectId={PROJECT_ID}&customfieldId={CATEGORY_FIELD_ID}",
        "project_commongroups": f"/api/projects/{PROJECT_ID}/commongroups",
    }
    for name, path in probe_specs.items():
        try:
            response = client.get(path, headers={"X-Tenant-Id": server.ORG_ID})
            entry: dict[str, Any] = {"status": response.status_code}
            if response.status_code == 200:
                entry["bodyHead"] = response.text[:300]
            probes[name] = entry
        except Exception as exc:  # noqa: BLE001
            probes[name] = {"status": "error", "error": str(exc)[:150]}

    print(
        json.dumps(
            {
                "parentTitle": PARENT_TITLE,
                "existingMatches": len(details),
                "matches": details,
                "category": {
                    "name": CATEGORY_NAME,
                    "id": options.get(CATEGORY_NAME),
                    "archiveRelated": archive_options,
                },
                "sprint": {"name": SPRINT_NAME, "id": sprint_id, "related": sprint_related},
                "managerMetadataChoice": manager_choice,
                "probes": probes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()