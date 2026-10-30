"""在奥飞财经系统(WUFN)项目创建付款发票问题任务，并删除WDIS项目中的错误任务"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from teambition_mcp_server import (
    _ensure_logged_in, _get_client, _get_project_config,
    _retry_request, ORG_ID, log
)

def main():
    _ensure_logged_in()
    client = _get_client()
    
    # 1. 删除 WDIS 项目中的错误任务
    wrong_task_id = "69d4d20936449c002326769e"
    log.info("归档 WDIS 项目的错误任务: %s", wrong_task_id)
    resp = _retry_request(lambda: client.post(
        f"/api/tasks/{wrong_task_id}/archive",
        headers={"X-Tenant-Id": ORG_ID}
    ))
    if resp.status_code == 200:
        print(f"✅ 已归档 WDIS 中的错误任务: {wrong_task_id}")
    else:
        print(f"⚠️ 归档失败: {resp.status_code} - {resp.text}")
    
    # 2. 在奥飞财经系统(WUFN)项目创建新任务
    project_id = "693907787ad8b6f61a76a0a6"  # 奥飞财经系统 (WUFN)
    config = _get_project_config(client, project_id)
    
    task_title = "【BUG】付款发票1002(J260200037)已付款无法撤销付款问题"
    task_note = (
        "## 问题描述\n\n"
        "**提出人**：古妙霞\n"
        "**时间**：4/7 16:06\n\n"
        "### 现象\n"
        "预付款发票 J260200037 已经付款，未核销，但无法撤销付款。\n\n"
        "### 补充信息\n"
        "媛媛姐怀疑是付款状态没有写进去表里，之前也有遇到过类似情况。\n\n"
        "### 排查方向\n"
        "1. 检查付款状态是否正确写入数据库\n"
        "2. 检查撤销付款的前置条件校验逻辑\n"
        "3. 对比正常可撤销的付款单数据"
    )
    
    body = {
        "_projectId": project_id,
        "_tasklistId": config["_tasklistId"],
        "_stageId": config["_defaultStageId"],
        "content": task_title,
        "note": task_note,
        "_executorId": "5bea5a57be825b33ab9afacb",  # 李光华
    }
    
    if config.get("_scenariofieldconfigId"):
        body["_scenariofieldconfigId"] = config["_scenariofieldconfigId"]
    if config.get("_defaultTaskflowstatusId"):
        body["_taskflowstatusId"] = config["_defaultTaskflowstatusId"]
    
    resp = _retry_request(lambda: client.post(
        "/api/tasks",
        json=body,
        headers={"X-Tenant-Id": ORG_ID}
    ))
    
    if resp.status_code == 200:
        data = resp.json()
        task_id = data.get("_id", "")
        title = data.get("content", "")
        print(f"\n✅ 任务创建成功！")
        print(f"   ID: {task_id}")
        print(f"   标题: {title}")
        print(f"   项目: 奥飞财经系统 (WUFN)")
    else:
        print(f"\n❌ 创建失败: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    main()
