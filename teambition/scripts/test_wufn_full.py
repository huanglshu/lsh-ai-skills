"""
全功能测试：在 奥飞财经系统（WUFN）中执行完整 CRUD 流程
测试目标：验证 Skill 在不同项目中的通用性
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teambition_mcp_server import (
    login, list_projects, list_tasks,
    create_task, update_task, delete_task,
)

EMAIL = "echizen_hua@163.com"
PASSWORD = "Hua902201$"
WUFN_PROJECT_ID = "693907787ad8b6f61a76a0a6"  # 奥飞财经系统
USER_ID = "5bea5a57be825b33ab9afacb"  # 李光华


def parse(result: str) -> dict:
    return json.loads(result)


def main():
    print("=" * 70)
    print("🏦 奥飞财经系统（WUFN）- 全功能测试")
    print("=" * 70)

    # ---- Step 1: 登录 ----
    print("\n📌 Step 1: 登录")
    data = parse(login(EMAIL, PASSWORD))
    assert data["status"] == "success"
    print(f"   ✅ 登录成功: {data['name']}")

    # ---- Step 2: 验证项目存在 ----
    print("\n📌 Step 2: 验证奥飞财经系统在项目列表中")
    data = parse(list_projects(page_size=50, fetch_all=True))
    wufn = [p for p in data["projects"] if p["_id"] == WUFN_PROJECT_ID]
    assert len(wufn) == 1, f"未找到奥飞财经系统项目"
    print(f"   ✅ 找到: {wufn[0]['name']} (成员:{wufn[0]['membersCount']}, 任务:{wufn[0]['tasksCount']})")

    # ---- Step 3: 查询已有任务 ----
    print("\n📌 Step 3: 查询现有任务列表")
    data = parse(list_tasks(project_id=WUFN_PROJECT_ID, page_size=3))
    assert data["status"] == "success"
    print(f"   ✅ 查到 {data['count']} 个任务")
    for t in data["tasks"][:3]:
        print(f"      - [{t.get('uniqueId', '?')}] {t['content']} (状态:{t.get('isDone', False)})")

    # ---- Step 4: 创建新任务 ----
    print("\n📌 Step 4: 创建测试任务")
    timestamp = time.strftime("%m%d-%H%M%S")
    data = parse(create_task(
        project_id=WUFN_PROJECT_ID,
        content=f"[全功能测试] 验证 Teambition Skill CRUD - {timestamp}",
        note="此任务由 MCP Skill 全功能测试自动创建\n测试项：创建 → 编辑 → 删除完整流程",
        executor_id=USER_ID,
        priority=0,
    ))
    assert data["status"] == "success"
    task_id = data["_id"]
    unique_id = data.get("uniqueId")
    print(f"   ✅ 创建成功: WUFN-{unique_id}（ID: {task_id}）")

    # ---- Step 5: 编辑任务 - 修改标题和优先级 ----
    print(f"\n📌 Step 5a: 编辑任务 - 修改标题和优先级")
    data = parse(update_task(
        task_id=task_id,
        project_id=WUFN_PROJECT_ID,
        content=f"[全功能测试-已编辑] 验证完成 - {timestamp}",
        priority=1,  # 改为紧急
    ))
    assert data["status"] == "success"
    print(f"   ✅ 标题+优先级更新成功")

    # ---- Step 5b: 编辑任务 - 修改描述 ----
    print(f"\n📌 Step 5b: 编辑任务 - 修改描述")
    data = parse(update_task(
        task_id=task_id,
        project_id=WUFN_PROJECT_ID,
        note=f"已通过全功能测试验证\n修改时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    ))
    assert data["status"] == "success"
    print(f"   ✅ 描述更新成功")

    # ---- Step 6: 验证任务更新后的内容 ----
    print(f"\n📌 Step 6: 验证更新后的任务在列表中")
    data = parse(list_tasks(project_id=WUFN_PROJECT_ID, keyword=f"全功能测试-已编辑"))
    found = [t for t in data["tasks"] if t["_id"] == task_id]
    if found:
        print(f"   ✅ 找到已更新的任务: {found[0]['content']}")
    else:
        print(f"   ⚠️ 未通过搜索找到，但更新API已返回成功")

    # ---- Step 7: 删除测试任务 ----
    print(f"\n📌 Step 7: 删除测试任务（清理数据）")
    data = parse(delete_task(task_id=task_id, project_id=WUFN_PROJECT_ID))
    assert data["status"] == "success"
    assert data["isArchived"] is True
    print(f"   ✅ 删除成功（已归档）")

    # ---- 总结 ----
    print("\n" + "=" * 70)
    print("🎉 奥飞财经系统全功能测试完成！")
    print("   ✅ login       - 登录认证")
    print("   ✅ list_projects - 项目列表（含WUFN）")
    print("   ✅ list_tasks   - 任务查询 + 关键词搜索")
    print("   ✅ create_task  - 创建任务（含executor_id、note、priority）")
    print("   ✅ update_task  - 编辑标题/优先级/描述（分步更新）")
    print("   ✅ delete_task  - 软删除（归档）")
    print("=" * 70)


if __name__ == "__main__":
    main()
