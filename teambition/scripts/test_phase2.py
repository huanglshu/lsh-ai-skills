"""
Phase 2 测试：create_task, update_task, delete_task
前置条件：Phase 1 的 login 和 list_tasks 已通过测试
"""

import json
import sys
import os

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teambition_mcp_server import login, list_tasks, create_task, update_task, delete_task

# 测试用常量
EMAIL = "echizen_hua@163.com"
PASSWORD = "Hua902201$"
PROJECT_ID = "65efbd2d7ad8b6f61a7516a1"  # 奥飞业务中台系统


def test_login():
    """登录（前置步骤）"""
    print("=" * 50)
    print("[前置] 登录...")
    result = login(EMAIL, PASSWORD)
    data = json.loads(result)
    assert data["status"] == "success", f"登录失败: {result}"
    print(f"  ✅ 登录成功: {data['name']}（{data['userId']}）")
    return data["userId"]


def test_create_task():
    """测试创建任务"""
    print("=" * 50)
    print("[Test 1] 创建任务...")
    result = create_task(
        project_id=PROJECT_ID,
        content="[自动化测试] Phase 2 创建任务测试",
        note="由 MCP Skill 自动化测试创建，可删除",
        priority=0,
    )
    print(f"  返回: {result}")
    data = json.loads(result)
    assert data["status"] == "success", f"创建失败: {result}"
    task_id = data["_id"]
    print(f"  ✅ 创建成功: {data['content']}（ID: {task_id}）")
    return task_id


def test_update_task_basic(task_id: str):
    """测试更新基础字段"""
    print("=" * 50)
    print(f"[Test 2] 更新任务基础字段（task={task_id}）...")
    result = update_task(
        task_id=task_id,
        project_id=PROJECT_ID,
        content="[自动化测试] Phase 2 创建任务测试（已修改）",
        note="更新后的描述",
        priority=1,
    )
    print(f"  返回: {result}")
    data = json.loads(result)
    assert data["status"] == "success", f"更新失败: {result}"
    print(f"  ✅ 更新成功: {data['updates']}")


def test_delete_task(task_id: str):
    """测试删除任务"""
    print("=" * 50)
    print(f"[Test 3] 删除任务（task={task_id}）...")
    result = delete_task(task_id=task_id, project_id=PROJECT_ID)
    print(f"  返回: {result}")
    data = json.loads(result)
    assert data["status"] == "success", f"删除失败: {result}"
    print(f"  ✅ 删除成功: isArchived={data.get('isArchived')}")


def main():
    print("🚀 Teambition MCP Server - Phase 2 测试")
    print()

    # 前置：登录
    user_id = test_login()

    # Test 1: 创建任务
    task_id = test_create_task()

    # Test 2: 更新任务
    test_update_task_basic(task_id)

    # Test 3: 删除任务（清理测试数据）
    test_delete_task(task_id)

    print()
    print("=" * 50)
    print("🎉 Phase 2 全部测试通过！")
    print(f"  - create_task ✅")
    print(f"  - update_task ✅")
    print(f"  - delete_task ✅")


if __name__ == "__main__":
    main()
