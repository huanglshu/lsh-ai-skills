"""查询完整的任务自定义字段结构"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID

def main():
    _ensure_logged_in()
    client = _get_client()
    
    # 直接获取一个完整的任务详情
    task_id = "69390eea798759002a4591e3"
    resp = _retry_request(lambda: client.get(
        f"/api/tasks/{task_id}",
        headers={"X-Tenant-Id": ORG_ID}
    ))
    task = resp.json()
    
    # 输出 customfields 完整结构
    cfs = task.get("customfields", [])
    print(f"=== Task Customfields ({len(cfs)}) ===")
    for i, cf in enumerate(cfs):
        print(f"\n--- Field {i+1} ---")
        print(json.dumps(cf, ensure_ascii=False, indent=2))
    
    # 输出 note
    print(f"\n=== Note ===")
    print(task.get("note", "None"))
    
    # 输出 dueDate
    print(f"\n=== dueDate: {task.get('dueDate')} ===")
    
    # 查询 scenario customfields 定义
    sfc_id = task.get("_scenariofieldconfigId")
    print(f"\n=== _scenariofieldconfigId: {sfc_id} ===")
    
    if sfc_id:
        resp2 = _retry_request(lambda: client.get(
            f"/api/scenariofieldconfigs/{sfc_id}",
            headers={"X-Tenant-Id": ORG_ID}
        ))
        sfc = resp2.json()
        print(json.dumps(sfc, ensure_ascii=False, indent=2)[:3000])

if __name__ == "__main__":
    main()
