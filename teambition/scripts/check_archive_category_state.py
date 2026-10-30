"""Read-only inspection of the archive category option state after manual correction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teambition_mcp_server as server

PROJECT_ID = "60e6912e8eb2da2a576f2abb"
CATEGORY_FIELD_ID = "5d1b3638ce9f165cd5d980b5"
PARENT_ID = "6acc5adc300105002b67dc97"


def main() -> None:
    server._ensure_logged_in()
    client = server._get_client()

    response = client.get(f"/api/tasks/{PARENT_ID}", headers={"X-Tenant-Id": server.ORG_ID})
    detail = response.json()
    print("== 父任务当前自定义字段 ==")
    for field in detail.get("customfields") or []:
        if not isinstance(field, dict):
            continue
        values = [
            {"_id": v.get("_id"), "title": v.get("title")}
            for v in field.get("value") or []
            if isinstance(v, dict)
        ]
        print(json.dumps({
            "_customfieldId": field.get("_customfieldId"),
            "type": field.get("type"),
            "values": values,
        }, ensure_ascii=False))

    tasks = server._collect_project_tasks_raw(client, PROJECT_ID, "false", max_pages=30)
    tasks.extend(server._collect_project_tasks_raw(client, PROJECT_ID, "true", max_pages=30))
    pairs: dict[str, dict[str, object]] = {}
    for task in tasks:
        for field in task.get("customfields") or []:
            if not isinstance(field, dict) or field.get("_customfieldId") != CATEGORY_FIELD_ID:
                continue
            for item in field.get("value") or []:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "")
                if "档案" not in title:
                    continue
                key = f"{item.get('_id')} | {title}"
                entry = pairs.setdefault(key, {"count": 0, "taskIds": []})
                entry["count"] = int(entry["count"]) + 1
                if len(entry["taskIds"]) < 3:
                    entry["taskIds"].append(task.get("_id"))

    print("== 项目内「档案」相关分类选项（按任务扫描）==")
    print(json.dumps(pairs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()