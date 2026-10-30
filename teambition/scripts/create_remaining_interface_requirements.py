"""Create the remaining interface requirements and their subtasks in Teambition."""

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
SPRINT_ID = "6a6c3d30543ed2001d8b78c5"
EXECUTOR_ID = "5bea5a57be825b33ab9afab5"
CONTRACT_CATEGORY_FIELD_ID = "5d1b3638ce9f165cd5d980b5"
CONTRACT_CATEGORY_VALUE_ID = "61656f46a8aed20013f088e9"


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

    response = client.put(
        f"/api/tasks/{requirement['_id']}/customfields",
        json={
            "_customfieldId": CONTRACT_CATEGORY_FIELD_ID,
            "type": "commongroup",
            "value": [
                {"_id": CONTRACT_CATEGORY_VALUE_ID, "title": "合同系统"}
            ],
        },
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
    items = parse_breakdown(root / "接口子任务拆解文档.md")
    remaining = items[2:]

    server.login()
    client = server._get_client()
    report = []

    for index, item in enumerate(remaining, start=3):
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
        detail = detail_response.json()
        actual_count = (detail.get("subtaskCount") or {}).get("total")
        expected_count = len(subtasks)
        if actual_count != expected_count:
            raise RuntimeError(
                f"{item['title']} subtask count mismatch: {actual_count} != {expected_count}"
            )

        record = {
            "sourceIndex": index,
            "title": item["title"],
            "requirementId": requirement["_id"],
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
