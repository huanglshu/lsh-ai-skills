"""Create archive-system development requirements in Teambition (restart-safe).

Only the parents named on the command line are processed. Reuses the exact-title
dedup pattern from create_production_release_work_package.py: an existing parent
is verified and only missing children are added.

The 档案系统 category value must reference the project's real option id; a
generated id is accepted by the API but is not part of the project option set, so
the task then shows up as 未分类需求 in the UI. The option id is resolved from
existing tasks and verified on read-back (title and option id must both match).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teambition_mcp_server as server
from parse_interface_subtasks import parse_breakdown
from preview_archive_dev_manifest import (
    collect_commongroup_options,
    deep_find_choice,
    normalize,
    resolve_sprint_exact,
)

PROJECT_ID = "60e6912e8eb2da2a576f2abb"
TASKLIST_ID = "60e6912f48e0c0004193b9e2"
STAGE_ID = "60e6912f48e0c0004193b9e5"
TASKFLOW_STATUS_ID = "60e6912e48e0c0004193b9bd"
REQUIREMENT_SCENARIO_ID = "60e6912f8eb2da2a576f2ad7"
SUBTASK_SCENARIO_ID = "60e6912f8eb2da2a576f2adf"
EXECUTOR_ID = "5bea5a57be825b33ab9afab5"
CATEGORY_FIELD_ID = "5d1b3638ce9f165cd5d980b5"
CATEGORY_NAME = "档案系统"
# 项目内「档案系统」分类选项的真实 ID（用户确认）。写入必须引用它，
# 否则任务在 UI 中会显示为「未分类需求」。
EXPECTED_CATEGORY_ID = "69a163e4faa5ef001ad19248"
PRODUCT_MANAGER_FIELD_ID = "69ca2ba47ad8b6f61a76ff2f"
SPRINT_NAME = "档案系统 v1.0"
EXPECTED_SPRINT_ID = "6acc537d54964c0024715104"
PRODUCT_MANAGER_NAME = "许媛媛"
DOCUMENT_NAME = "档案系统-开发清单_林树煌任务_子任务拆解.md"
EXPECTED_PARENTS = 11
EXPECTED_CHILDREN = 15


def headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Tenant-Id": server.ORG_ID,
        "x-request-id": str(uuid.uuid4()),
    }


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
    return [t for t in by_id.values() if t.get("_projectId") == PROJECT_ID]


def matching_parents(client: Any, title: str) -> list[dict[str, Any]]:
    expected = normalize(title)
    matches = [task for task in all_project_tasks(client) if normalize(task.get("content")) == expected]
    return [get_detail(client, str(task["_id"])) for task in matches]


def direct_child_titles(parent: dict[str, Any]) -> set[str]:
    return {
        normalize(child.get("content"))
        for child in (parent.get("subtasks") or [])
        if isinstance(child, dict) and child.get("content")
    }


def read_field(client: Any, task_id: str, field_id: str) -> list[dict[str, Any]]:
    detail = get_detail(client, task_id)
    for field in detail.get("customfields") or []:
        if not isinstance(field, dict) or field.get("_customfieldId") != field_id:
            continue
        return [
            {"_id": item.get("_id"), "title": item.get("title")}
            for item in field.get("value") or []
            if isinstance(item, dict)
        ]
    return []


def set_field(client: Any, task_id: str, field_id: str, field_type: str, value: list[dict[str, Any]]) -> Any:
    return client.put(
        f"/api/tasks/{task_id}/customfields",
        json={"_customfieldId": field_id, "type": field_type, "value": value},
        headers=headers(),
    )


def resolve_manager(client: Any) -> dict[str, str]:
    for path in (
        f"/api/v2/customfields/{PRODUCT_MANAGER_FIELD_ID}",
        f"/api/customfields/{PRODUCT_MANAGER_FIELD_ID}",
    ):
        response = client.get(path, headers={"X-Tenant-Id": server.ORG_ID})
        if response.status_code == 200:
            choice = deep_find_choice(response.json(), PRODUCT_MANAGER_NAME)
            if choice:
                return choice
    member = server._search_member_by_name(client, PRODUCT_MANAGER_NAME)
    if not member:
        raise RuntimeError(f"未找到产品经理：{PRODUCT_MANAGER_NAME}")
    return {"title": PRODUCT_MANAGER_NAME}


def resolve_category(client: Any) -> list[dict[str, str]] | None:
    if EXPECTED_CATEGORY_ID:
        return [{"_id": EXPECTED_CATEGORY_ID, "title": CATEGORY_NAME}]
    options = collect_commongroup_options(client)
    option_id = options.get(CATEGORY_NAME)
    if option_id:
        return [{"_id": option_id, "title": CATEGORY_NAME}]
    return None


def ensure_category(
    client: Any,
    task_id: str,
    preferred: list[dict[str, str]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attempts: list[tuple[str, list[dict[str, str]]]] = []
    if preferred:
        attempts.append(("resolved-id", preferred))
    attempts.append(("title-only", [{"title": CATEGORY_NAME}]))

    diagnostics: list[dict[str, Any]] = []
    for label, values in attempts:
        response = set_field(client, task_id, CATEGORY_FIELD_ID, "commongroup", values)
        current = read_field(client, task_id, CATEGORY_FIELD_ID)
        titles = [normalize(item.get("title")) for item in current]
        ids = [str(item.get("_id") or "") for item in current]
        if response.status_code < 400 and titles == [CATEGORY_NAME] and ids == [EXPECTED_CATEGORY_ID]:
            return current, {"attempt": label, "status": response.status_code, "readBack": current}
        diagnostics.append(
            {
                "attempt": label,
                "status": response.status_code,
                "bodyHead": response.text[:200] if response.status_code >= 400 else "",
                "readBack": current,
            }
        )
    raise RuntimeError(f"分类「{CATEGORY_NAME}」写入失败：{json.dumps(diagnostics, ensure_ascii=False)}")


def ensure_manager(client: Any, task_id: str, manager: dict[str, str]) -> list[dict[str, Any]]:
    for label, values in (("resolved", [manager]), ("title-only", [{"title": PRODUCT_MANAGER_NAME}])):
        response = set_field(client, task_id, PRODUCT_MANAGER_FIELD_ID, "dropDown", values)
        current = read_field(client, task_id, PRODUCT_MANAGER_FIELD_ID)
        titles = [normalize(item.get("title")) for item in current]
        if response.status_code < 400 and titles == [PRODUCT_MANAGER_NAME]:
            return current
    raise RuntimeError(f"产品经理「{PRODUCT_MANAGER_NAME}」写入失败")


def create_parent(
    client: Any,
    item: dict[str, Any],
    sprint_id: str,
    manager: dict[str, str],
    category_pref: list[dict[str, str]] | None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
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
    parent_id = str(parent["_id"])

    category_values, category_record = ensure_category(client, parent_id, category_pref)
    manager_values = ensure_manager(client, parent_id, manager)
    detail = get_detail(client, parent_id)
    return detail, category_record, manager_values


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


def verify_parent(
    client: Any,
    parent: dict[str, Any],
    item: dict[str, Any],
    sprint_id: str,
) -> dict[str, Any]:
    if normalize(parent.get("content")) != normalize(item["title"]):
        raise RuntimeError(f"父需求标题校验失败：{item['title']}")
    if normalize(parent.get("note")) != normalize(item["acceptance"]):
        raise RuntimeError(f"父需求验收备注不一致：{item['title']}")

    sprint = parent.get("sprint") if isinstance(parent.get("sprint"), dict) else {}
    actual_sprint_id = parent.get("_sprintId") or sprint.get("_id")
    if actual_sprint_id != sprint_id:
        raise RuntimeError(f"迭代校验失败：{item['title']} -> {actual_sprint_id}")

    expected = {normalize(title) for title in item["subtasks"]}
    actual = direct_child_titles(parent)
    if actual != expected:
        raise RuntimeError(
            f"子任务集合校验失败：{item['title']}；缺失={sorted(expected - actual)}；额外={sorted(actual - expected)}"
        )
    if (parent.get("subtaskCount") or {}).get("total") != len(expected):
        raise RuntimeError(f"子任务数量校验失败：{item['title']}")

    parent_id = str(parent["_id"])
    category = read_field(client, parent_id, CATEGORY_FIELD_ID)
    if [normalize(v.get("title")) for v in category] != [CATEGORY_NAME]:
        raise RuntimeError(f"分类校验失败：{item['title']} -> {category}")
    if [str(v.get("_id") or "") for v in category] != [EXPECTED_CATEGORY_ID]:
        raise RuntimeError(
            f"分类选项 ID 与项目既有选项不一致（UI 会显示为「未分类需求」）：{item['title']} -> {category}"
        )
    manager = read_field(client, parent_id, PRODUCT_MANAGER_FIELD_ID)
    if [normalize(v.get("title")) for v in manager] != [PRODUCT_MANAGER_NAME]:
        raise RuntimeError(f"产品经理校验失败：{item['title']} -> {manager}")

    return {
        "category": category,
        "productManager": manager,
        "sprintId": actual_sprint_id,
        "subtaskCount": (parent.get("subtaskCount") or {}).get("total"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="创建档案系统开发需求（可重入）")
    parser.add_argument("parents", nargs="+", help="要处理的父任务标题（与拆解文档一致）")
    parser.add_argument("--dry-run", action="store_true", help="只检查与解析，不写入")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    items = parse_breakdown(root / DOCUMENT_NAME)
    if len(items) != EXPECTED_PARENTS or any(len(item["subtasks"]) != EXPECTED_CHILDREN for item in items):
        raise RuntimeError("源文档解析结果不符合预期：应为 11 条父任务 × 15 条子任务")
    by_title = {normalize(item["title"]): item for item in items}
    targets = []
    for title in args.parents:
        key = normalize(title)
        if key not in by_title:
            raise RuntimeError(f"拆解文档中不存在父任务：{title}")
        targets.append(by_title[key])

    server._ensure_logged_in()
    client = server._get_client()

    sprint_id, sprint_related = resolve_sprint_exact(client, SPRINT_NAME)
    if sprint_id != EXPECTED_SPRINT_ID:
        raise RuntimeError(f"迭代解析异常：{sprint_id}（关联={sprint_related}）")
    manager = resolve_manager(client)
    category_pref = resolve_category(client)

    context = {
        "sprintId": sprint_id,
        "manager": manager,
        "categoryPreferred": category_pref,
        "targets": [item["title"] for item in targets],
    }
    print(json.dumps({"context": context}, ensure_ascii=False), flush=True)
    if args.dry_run:
        print(json.dumps({"status": "dry-run", "context": context}, ensure_ascii=False))
        return

    report: list[dict[str, Any]] = []
    learned_category = category_pref
    for item in targets:
        parents = matching_parents(client, item["title"])
        if len(parents) > 1:
            raise RuntimeError(f"发现多个同名父需求，停止创建：{item['title']}")

        created_parent = False
        category_record: dict[str, Any] | None = None
        if parents:
            parent = parents[0]
            if normalize(parent.get("note")) != normalize(item["acceptance"]):
                raise RuntimeError(f"已存在同名父需求但验收备注不一致：{item['title']} ({parent.get('_id')})")
        else:
            parent, category_record, _ = create_parent(client, item, sprint_id, manager, learned_category)
            created_parent = True
            current = read_field(client, str(parent["_id"]), CATEGORY_FIELD_ID)
            if current and current[0].get("_id"):
                learned_category = [{"_id": current[0]["_id"], "title": CATEGORY_NAME}]

        parent_id = str(parent["_id"])
        existing_children = direct_child_titles(parent)
        created_children = []
        for child_title in item["subtasks"]:
            if normalize(child_title) in existing_children:
                continue
            latest = get_detail(client, parent_id)
            if normalize(child_title) in direct_child_titles(latest):
                continue
            created_children.append(create_child(client, parent_id, child_title))

        verified = get_detail(client, parent_id)
        checks = verify_parent(client, verified, item, sprint_id)
        record = {
            "title": item["title"],
            "id": parent_id,
            "uniqueId": verified.get("uniqueId"),
            "createdParent": created_parent,
            "createdChildren": len(created_children),
            "categoryRecord": category_record,
            "checks": checks,
        }
        report.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    print(
        json.dumps(
            {
                "status": "success",
                "requirements": len(report),
                "subtasks": sum(int(x["checks"]["subtaskCount"]) for x in report),
                "items": report,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()