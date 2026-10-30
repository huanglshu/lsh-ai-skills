"""Create trademark archive interface requirements and subtasks from the breakdown document."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teambition_mcp_server as server
from parse_interface_subtasks import parse_breakdown


PROJECT_ID = "60e6912e8eb2da2a576f2abb"
TASKLIST_ID = "60e6912f48e0c0004193b9e2"
STAGE_ID = "60e6912f48e0c0004193b9e5"
TASKFLOW_STATUS_ID = "60e6912e48e0c0004193b9bd"
REQUIREMENT_SCENARIO_ID = "60e6912f8eb2da2a576f2ad7"
SUBTASK_SCENARIO_ID = "60e6912f8eb2da2a576f2adf"
SPRINT_ID = "69c498ff798759002a583dc2"
EXECUTOR_ID = "5bea5a57be825b33ab9afab5"
CATEGORY_FIELD_ID = "5d1b3638ce9f165cd5d980b5"
CATEGORY_VALUE_ID = "6165701aa8aed20013f088ea"
PROPOSER_FIELD_ID = "60e2782a8eb2da2a576efc39"
PROPOSER_VALUE_ID = "618e131a8eb2da2a5770bccd"
PRODUCT_MANAGER_FIELD_ID = "69ca2ba47ad8b6f61a76ff2f"


def headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Tenant-Id": server.ORG_ID,
        "x-request-id": str(uuid.uuid4()),
    }


def create_requirement(client, item: dict[str, object]) -> dict:
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
            "_sprintId": SPRINT_ID,
            "priority": -10,
            "note": item["acceptance"],
        },
        headers=headers(),
    )
    response.raise_for_status()
    requirement = response.json()

    field_updates = [
        {
            "_customfieldId": CATEGORY_FIELD_ID,
            "type": "commongroup",
            "value": [{"_id": CATEGORY_VALUE_ID, "title": "知识产权"}],
        },
        {
            "_customfieldId": PROPOSER_FIELD_ID,
            "type": "dropDown",
            "value": [{"_id": PROPOSER_VALUE_ID, "title": "周梦婷"}],
        },
        {
            "_customfieldId": PRODUCT_MANAGER_FIELD_ID,
            "type": "dropDown",
            "value": [{"title": "周梦婷"}],
        },
    ]
    for field_update in field_updates:
        response = client.put(
            f"/api/tasks/{requirement['_id']}/customfields",
            json=field_update,
            headers=headers(),
        )
        response.raise_for_status()
    return requirement


def create_subtask(client, parent_id: str, content: str) -> dict:
    response = client.post(
        "/api/tasks",
        json={
            "ancestorIds": [],
            "objectType": "task",
            "isDone": False,
            "isRedo": False,
            "content": content,
            "note": "",
            "priority": -10,
            "involveMembers": [],
            "subtaskCount": {"total": 0, "done": 0},
            "workTime": {"totalTime": 0, "usedTime": 0, "unit": "minute"},
            "_ancestorId": parent_id,
            "_creatorId": EXECUTOR_ID,
            "_executorId": EXECUTOR_ID,
            "_projectId": PROJECT_ID,
            "_organizationId": None,
            "_tasklistId": TASKLIST_ID,
            "_stageId": STAGE_ID,
            "_scenariofieldconfigId": SUBTASK_SCENARIO_ID,
            "visible": "members",
            "_taskflowstatusId": TASKFLOW_STATUS_ID,
            "isVisible": True,
        },
        headers=headers(),
    )
    response.raise_for_status()
    subtask = response.json()
    if parent_id not in subtask.get("ancestorIds", []):
        raise RuntimeError(f"Subtask did not retain parent relation: {subtask['_id']}")
    return subtask


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    items = parse_breakdown(root / "开放平台商标档案接口子任务拆解文档.md")
    server.login()
    client = server._get_client()
    report = []

    for source_index, item in enumerate(items):
        requirement = create_requirement(client, item)
        subtasks = [
            create_subtask(client, requirement["_id"], content)
            for content in item["subtasks"]
        ]
        detail_response = client.get(
            f"/api/tasks/{requirement['_id']}",
            headers={"X-Tenant-Id": server.ORG_ID},
        )
        detail_response.raise_for_status()
        actual_count = (detail_response.json().get("subtaskCount") or {}).get("total")
        if actual_count != len(subtasks):
            raise RuntimeError(
                f"{item['title']} subtask count mismatch: {actual_count} != {len(subtasks)}"
            )
        record = {
            "sourceIndex": source_index,
            "title": item["title"],
            "uniqueId": requirement.get("uniqueId"),
            "subtaskCount": actual_count,
        }
        report.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    print(
        json.dumps(
            {
                "status": "success",
                "requirementsCreated": len(report),
                "subtasksCreated": sum(item["subtaskCount"] for item in report),
                "items": report,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
