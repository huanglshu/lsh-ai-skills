"""删除旧任务，在WUFN项目创建带完整自定义字段的新任务"""
import sys, os, json
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))

from teambition_mcp_server import (
    _ensure_logged_in, _get_client, _get_project_config,
    _retry_request, ORG_ID, log
)

def main():
    _ensure_logged_in()
    client = _get_client()
    
    project_id = "693907787ad8b6f61a76a0a6"  # 奥飞财经系统 (WUFN)
    
    # 1. 删除旧任务
    old_task_id = "69d4db028e2e9a001c17b922"
    log.info("删除旧任务: %s", old_task_id)
    resp = _retry_request(lambda: client.post(
        f"/api/tasks/{old_task_id}/archive",
        headers={"X-Tenant-Id": ORG_ID}
    ))
    print(f"归档旧任务: {resp.status_code}")
    
    # 2. 计算上线时间 = 当前时间 + 1天(开发人天) + 0.5天 = +1.5天
    now = datetime.utcnow()
    due_date = (now + timedelta(days=1.5)).strftime("%Y-%m-%dT10:00:00.000Z")
    
    # 3. 获取项目配置
    config = _get_project_config(client, project_id)
    
    # 4. 构建任务
    task_title = "付款发票1002(J260200037)已付款无法撤销付款问题"
    task_note = (
        "## 问题描述\n\n"
        "**提出人**：古妙霞\n"
        "**时间**：2026-04-07 16:06\n\n"
        "### 现象\n"
        "预付款发票 J260200037 已经付款，未核销，但无法撤销付款。\n\n"
        "### 补充信息\n"
        "媛媛姐怀疑是付款状态没有写进表里，之前也有遇到过类似情况。\n\n"
        "### 排查方向\n"
        "1. 检查付款状态是否正确写入数据库\n"
        "2. 检查撤销付款的前置条件校验逻辑\n"
        "3. 对比正常可撤销的付款单数据\n\n"
        "### 开发人天\n"
        "1天"
    )
    
    body = {
        "_projectId": project_id,
        "_tasklistId": config["_tasklistId"],
        "_stageId": config["_defaultStageId"],
        "content": task_title,
        "note": task_note,
        "_executorId": "5bea5a57be825b33ab9afacb",  # 李光华（当前登录用户）
        "dueDate": due_date,  # 上线时间
    }
    
    if config.get("_scenariofieldconfigId"):
        body["_scenariofieldconfigId"] = config["_scenariofieldconfigId"]
    if config.get("_defaultTaskflowstatusId"):
        body["_taskflowstatusId"] = config["_defaultTaskflowstatusId"]
    
    # 5. 创建任务
    resp = _retry_request(lambda: client.post(
        "/api/tasks",
        json=body,
        headers={"X-Tenant-Id": ORG_ID}
    ))
    
    if resp.status_code != 200:
        print(f"❌ 创建失败: {resp.status_code}")
        print(resp.text)
        return
    
    task = resp.json()
    task_id = task.get("_id")
    print(f"\n✅ 任务创建成功！ ID: {task_id}")
    print(f"   标题: {task.get('content')}")
    print(f"   dueDate: {due_date}")
    
    # 6. 逐个设置自定义字段（PUT /api/tasks/{id}/customfields）
    import uuid
    fields_to_set = [
        {
            "body": {
                "_customfieldId": "693910667ad8b6f61a76a0fd",
                "type": "lookup",
                "value": [{"_id": "665d864aeddf7ef85e0e4c14", "title": "古妙霞"}]
            },
            "label": "提出人=古妙霞"
        },
        {
            "body": {
                "_customfieldId": "693922107ad8b6f61a76a168",
                "type": "dropDown",
                "value": [{"_id": "693922107ad8b6f61a76a169", "title": "ERP"}]
            },
            "label": "系统=ERP"
        },
        {
            "body": {
                "_customfieldId": "69b21bbf7ad8b6f61a76ebe1",
                "type": "date",
                "value": [{"title": due_date}]
            },
            "label": f"上线时间={due_date}"
        }
    ]
    
    for field in fields_to_set:
        resp2 = _retry_request(lambda body=field["body"]: client.put(
            f"/api/tasks/{task_id}/customfields",
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Tenant-Id": ORG_ID,
                "x-request-id": str(uuid.uuid4()),
            }
        ))
        if resp2.status_code == 200:
            print(f"   ✅ {field['label']}")
        else:
            print(f"   ⚠️ {field['label']}: {resp2.status_code} - {resp2.text[:300]}")

    # 7. 默认把提出者和执行者都添加为参与者
    involvers_to_add = []
    executor_id = "5bea5a57be825b33ab9afacb"  # 李光华
    proposer_involver_id = "665d864abf5f11b187aa5279"  # 古妙霞 (involveMembers ID)
    
    # 执行者通常已是参与者（创建者=执行者时自动加入），但提出者需要手动添加
    involvers_to_add.append(proposer_involver_id)
    
    if involvers_to_add:
        resp3 = _retry_request(lambda: client.put(
            f"/api/tasks/{task_id}/involveMembers",
            json={"addInvolvers": involvers_to_add},
            headers={
                "Content-Type": "application/json",
                "x-request-id": str(uuid.uuid4()),
                "x-timezone": "8",
            }
        ))
        if resp3.status_code == 200:
            involvers = resp3.json().get("involvers", [])
            names = [m.get("name") for m in involvers]
            print(f"   ✅ 参与者={', '.join(names)}")
        else:
            print(f"   ⚠️ 添加参与者: {resp3.status_code} - {resp3.text[:300]}")

if __name__ == "__main__":
    main()
