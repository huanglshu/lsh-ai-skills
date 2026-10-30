"""查询 WUFN 项目的自定义字段配置"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID, log

def main():
    _ensure_logged_in()
    client = _get_client()
    
    project_id = "693907787ad8b6f61a76a0a6"  # WUFN
    
    # 1. 查询 scenariofieldconfig 详情
    resp = _retry_request(lambda: client.get(
        f"/api/v2/projects/{project_id}/scenariofieldconfigs",
        headers={"X-Tenant-Id": ORG_ID}
    ))
    configs = resp.json()
    print("=== Scenario Field Configs ===")
    for cfg in configs:
        print(f"  ID: {cfg.get('_id')}")
        print(f"  objectType: {cfg.get('objectType')}")
        cf = cfg.get("customfields", [])
        print(f"  customfields ({len(cf)} items):")
        for field in cf:
            print(f"    - _id: {field.get('_id')}")
            print(f"      fieldType: {field.get('fieldType')}")
            print(f"      name: {field.get('name', field.get('label', ''))}")
            choices = field.get("choices", [])
            if choices:
                print(f"      choices: {json.dumps(choices[:5], ensure_ascii=False)}")
        print()

    # 2. 查询已有任务的自定义字段值作为参考
    resp2 = _retry_request(lambda: client.get(
        "/api/v2/tasks",
        params={"_projectId": project_id, "isDone": "false", "pageSize": "2"},
        headers={"X-Tenant-Id": ORG_ID}
    ))
    tasks = resp2.json()
    if isinstance(tasks, dict):
        tasks = tasks.get("result", [])
    
    print("\n=== Existing Tasks (sample) ===")
    for t in tasks[:2]:
        print(f"\n  Task: {t.get('content')}")
        print(f"  _id: {t.get('_id')}")
        print(f"  _executorId: {t.get('_executorId')}")
        print(f"  dueDate: {t.get('dueDate')}")
        print(f"  startDate: {t.get('startDate')}")
        cfs = t.get("customfields", [])
        if cfs:
            print(f"  customfields ({len(cfs)} items):")
            for cf in cfs:
                print(f"    - _id: {cf.get('_id')}")
                print(f"      type: {cf.get('type')}")
                val = cf.get("value", cf.get("values"))
                print(f"      value: {json.dumps(val, ensure_ascii=False) if val else 'None'}")

if __name__ == "__main__":
    main()
