"""Safely create the contract-system production release work package in Teambition.

The script is restart-safe: it inventories existing exact-title parents before each
write and adds only missing direct children to a verified existing parent.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teambition_mcp_server as server
from parse_interface_subtasks import parse_breakdown

PROJECT_ID = "60e6912e8eb2da2a576f2abb"
TASKLIST_ID = "60e6912f48e0c0004193b9e2"
STAGE_ID = "60e6912f48e0c0004193b9e5"
TASKFLOW_STATUS_ID = "60e6912e48e0c0004193b9bd"
REQUIREMENT_SCENARIO_ID = "60e6912f8eb2da2a576f2ad7"
SUBTASK_SCENARIO_ID = "60e6912f8eb2da2a576f2adf"
EXECUTOR_ID = "5bea5a57be825b33ab9afab5"
CATEGORY_FIELD_ID = "5d1b3638ce9f165cd5d980b5"
CATEGORY_VALUE_ID = "61656f46a8aed20013f088e9"
PRODUCT_MANAGER_FIELD_ID = "69ca2ba47ad8b6f61a76ff2f"
SPRINT_NAME = "甄零合同系统 v1.0"
PRODUCT_MANAGER_NAME = "伍银兰"


def headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Tenant-Id": server.ORG_ID,
        "x-request-id": str(uuid.uuid4()),
    }


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def get_detail(client: Any, task_id: str) -> dict[str, Any]:
    response = client.get(f"/api/tasks/{task_id}", headers={"X-Tenant-Id": server.ORG_ID})
    response.raise_for_status()
    return response.json()


def all_project_tasks(client: Any) -> list[dict[str, Any]]:
    tasks = server._collect_project_tasks_raw(client, PROJECT_ID, "false", max_pages=30)
    tasks.extend(server._collect_project_tasks_raw(client, PROJECT_ID, "true", max_pages=30))
    by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = str(task.get("_id") or "")
        if task_id:
            by_id[task_id] = task
    return list(by_id.values())


def matching_parents(client: Any, title: str) -> list[dict[str, Any]]:
    expected = normalize(title)
    matches = [
        task for task in all_project_tasks(client)
        if normalize(task.get("content")) == expected and task.get("_projectId") == PROJECT_ID
    ]
    return [get_detail(client, str(task["_id"])) for task in matches]


def direct_child_titles(parent: dict[str, Any]) -> set[str]:
    return {
        normalize(child.get("content"))
        for child in (parent.get("subtasks") or [])
        if isinstance(child, dict) and child.get("content")
    }


def find_manager_choice(value: Any) -> dict[str, str] | None:
    """Locate an exact named dropdown option without accepting title-only fallback."""
    if isinstance(value, dict):
        title = value.get("title") or value.get("value") or value.get("name") or value.get("label")
        option_id = value.get("_id") or value.get("id") or value.get("valueId")
        if normalize(title) == PRODUCT_MANAGER_NAME and option_id:
            return {"_id": str(option_id), "title": PRODUCT_MANAGER_NAME}
        for child in value.values():
            found = find_manager_choice(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_manager_choice(child)
            if found:
                return found
    return None


def resolve_manager_choice(client: Any) -> dict[str, str]:
    response = client.get(
        f"/api/v2/customfields/{PRODUCT_MANAGER_FIELD_ID}",
        headers={"X-Tenant-Id": server.ORG_ID},
    )
    if response.status_code != 200:
        response = client.get(
            f"/api/customfields/{PRODUCT_MANAGER_FIELD_ID}",
            headers={"X-Tenant-Id": server.ORG_ID},
        )
    response.raise_for_status()
    choice = find_manager_choice(response.json())
    if choice:
        return choice

    # The page's manager picker may be backed by organization members even when
    # the custom-field metadata has not synchronized its static choice list.
    member = server._search_member_by_name(client, PRODUCT_MANAGER_NAME)
    if not member:
        raise RuntimeError(f"未找到产品经理组织成员：{PRODUCT_MANAGER_NAME}")
    return {"title": PRODUCT_MANAGER_NAME}


def update_field(client: Any, task_id: str, field_id: str, field_type: str, value: list[dict[str, str]]) -> None:
    response = client.put(
        f"/api/tasks/{task_id}/customfields",
        json={"_customfieldId": field_id, "type": field_type, "value": value},
        headers=headers(),
    )
    response.raise_for_status()


def create_parent(client: Any, item: dict[str, Any], sprint_id: str, manager: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        "/api/v2/tasks",
        json={
            "content": item["title"],
            "_projectId": PROJECT_ID,
            "_tasklistId": TASKLIST_ID,
            "_stageId": STAGE_ID,
            "_taskflowstatusId": TASKFLOW_STATUS_ID,
            "_executorId": EXECUTOR_ID,
            "_scenariofieldconfigId": REQUIREMENT_SCENARIO_ID,
            "_sprintId": sprint_id,
            "priority": -10,
            "note": item["acceptance"],
        },
        headers=headers(),
    )
    response.raise_for_status()
    parent = response.json()
    update_field(client, parent["_id"], CATEGORY_FIELD_ID, "commongroup", [{"_id": CATEGORY_VALUE_ID, "title": "合同系统"}])
    update_field(client, parent["_id"], PRODUCT_MANAGER_FIELD_ID, "dropDown", [manager])
    return get_detail(client, parent["_id"])


def create_child(client: Any, parent_id: str, title: str) -> dict[str, Any]:
    response = client.post(
        "/api/tasks",
        json={
            "ancestorIds": [], "objectType": "task", "isDone": False, "isRedo": False,
            "content": title, "note": "", "priority": -10, "involveMembers": [],
            "subtaskCount": {"total": 0, "done": 0},
            "workTime": {"totalTime": 0, "usedTime": 0, "unit": "minute"},
            "_ancestorId": parent_id, "_creatorId": EXECUTOR_ID, "_executorId": EXECUTOR_ID,
            "_projectId": PROJECT_ID, "_organizationId": None, "_tasklistId": TASKLIST_ID,
            "_stageId": STAGE_ID, "_scenariofieldconfigId": SUBTASK_SCENARIO_ID,
            "visible": "members", "_taskflowstatusId": TASKFLOW_STATUS_ID, "isVisible": True,
        },
        headers=headers(),
    )
    response.raise_for_status()
    child = response.json()
    if parent_id not in (child.get("ancestorIds") or []):
        raise RuntimeError(f"子任务未保留父子关系：{child.get('_id')}")
    return child


def verify_parent(parent: dict[str, Any], item: dict[str, Any]) -> None:
    if normalize(parent.get("content")) != normalize(item["title"]):
        raise RuntimeError(f"父需求标题校验失败：{item['title']}")
    if normalize(parent.get("note")) != normalize(item["acceptance"]):
        raise RuntimeError(f"父需求验收备注不一致：{item['title']}")
    expected = {normalize(title) for title in item["subtasks"]}
    actual = direct_child_titles(parent)
    if actual != expected:
        raise RuntimeError(f"子任务集合校验失败：{item['title']}；缺失={sorted(expected - actual)}；额外={sorted(actual - expected)}")
    if (parent.get("subtaskCount") or {}).get("total") != len(expected):
        raise RuntimeError(f"子任务数量校验失败：{item['title']}")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    items = parse_breakdown(root / "甄零合同系统-生产上线准备总体工作包.md")
    expected_counts = [7, 8, 6, 7, 9]
    if len(items) != 5 or [len(item["subtasks"]) for item in items] != expected_counts:
        raise RuntimeError("源文档解析结果不符合预期 5 条父需求 / 37 条子任务")

    server._ensure_logged_in()
    client = server._get_client()
    sprint_id = server._resolve_sprint_id_by_name(client, PROJECT_ID, SPRINT_NAME)
    if not sprint_id:
        raise RuntimeError(f"未找到迭代：{SPRINT_NAME}")
    manager = resolve_manager_choice(client)

    report: list[dict[str, Any]] = []
    for item in items:
        parents = matching_parents(client, item["title"])
        if len(parents) > 1:
            raise RuntimeError(f"发现多个同名父需求，停止创建：{item['title']}")
        created_parent = False
        if parents:
            parent = parents[0]
            if normalize(parent.get("note")) != normalize(item["acceptance"]):
                raise RuntimeError(f"已存在同名父需求但验收备注不一致：{item['title']} ({parent.get('_id')})")
        else:
            parent = create_parent(client, item, sprint_id, manager)
            created_parent = True

        parent_id = str(parent["_id"])
        existing_children = direct_child_titles(parent)
        expected_children = [normalize(title) for title in item["subtasks"]]
        if len(existing_children) != len(parent.get("subtasks") or []):
            raise RuntimeError(f"已存在父需求包含重复子任务标题，停止创建：{item['title']}")
        missing = [title for title in item["subtasks"] if normalize(title) not in existing_children]
        created_children = []
        for child_title in missing:
            # Re-read immediately before every create to avoid duplicate POSTs during concurrent changes.
            latest = get_detail(client, parent_id)
            if normalize(child_title) in direct_child_titles(latest):
                continue
            created_children.append(create_child(client, parent_id, child_title))

        verified = get_detail(client, parent_id)
        verify_parent(verified, item)
        record = {
            "title": item["title"], "id": parent_id, "uniqueId": verified.get("uniqueId"),
            "createdParent": created_parent, "createdChildren": len(created_children),
            "subtaskCount": (verified.get("subtaskCount") or {}).get("total"),
        }
        report.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    print(json.dumps({"status": "success", "requirements": len(report), "subtasks": sum(x["subtaskCount"] for x in report), "items": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
