import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import teambition_mcp_server as s

os.environ["TB_DEFAULT_PROPOSER_BY_PROJECT_JSON"] = json.dumps(
    [
        {
            "project_name": "协同系统",
            "name": "李斯浩",
            "executorname": "登录用户",
            "proposer_custom_field_name": {
                "提出人": "name",
                "备注": "根据任务内容扩展，包括问题的现象，问题的分析，问题的验证等",
                "迭代": "泛微OA_2026",
                "需求分类": "泛微OA与企微",
                "参与者": "name和executorname",
            },
        }
    ],
    ensure_ascii=False,
)

# Reload mapping from env for this process.
s.DEFAULT_PROPOSER_BY_PROJECT, s.DEFAULT_PROPOSER_BY_PROJECT_NAME = s._load_default_proposer_by_project()

project_id = "60e6912e8eb2da2a576f2abb"

raw = s.create_task(
    project_id=project_id,
    content=f"【规则回填测试】协同系统-{int(time.time())}",
    note="验证 proposer_custom_field_name 规则字段回填",
    priority=0,
)
print("create_result=", raw)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(1)

task_id = data.get("_id")
if not task_id:
    raise SystemExit(2)

s._ensure_logged_in()
client = s._get_client()
detail = s._retry_request(
    lambda: client.get(f"/api/tasks/{task_id}", headers={"X-Tenant-Id": s.ORG_ID})
).json()

wanted_ids = {"60e2782a8eb2da2a576efc39", "5d1b3638ce9f165cd5d980b5"}
customfields = [
    cf
    for cf in detail.get("customfields", [])
    if cf.get("_customfieldId") in wanted_ids
]

print("task_id=", task_id)
print("sprint=", detail.get("sprint"))
print("customfields=", json.dumps(customfields, ensure_ascii=False))
