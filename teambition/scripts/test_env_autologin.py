"""
回归测试：验证 .env 自动登录 + 全工具功能
不显式调用 login，验证 _ensure_logged_in 自动从 .env 读取凭据登录
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 重新加载模块（清除之前的全局状态）
import importlib
import teambition_mcp_server as tb
importlib.reload(tb)

WUFN_PROJECT_ID = "693907787ad8b6f61a76a0a6"


def parse(result: str) -> dict:
    return json.loads(result)


def main():
    print("=" * 60)
    print("🔧 回归测试：.env 自动登录 + 全功能验证")
    print("=" * 60)

    # Test 1: 不调用 login，直接 list_projects（触发自动登录）
    print("\n[Test 1] 不登录直接查询项目（验证自动登录）...")
    data = parse(tb.list_projects(page_size=5, fetch_all=False))
    assert data["status"] == "success"
    print(f"  ✅ 自动登录成功，查到 {data['count']} 个项目")

    # Test 2: 查询任务
    print("\n[Test 2] 查询奥飞财经系统任务...")
    data = parse(tb.list_tasks(project_id=WUFN_PROJECT_ID, page_size=2))
    assert data["status"] == "success"
    print(f"  ✅ 查到 {data['count']} 个任务")

    # Test 3: 创建-编辑-删除（完整流程）
    print("\n[Test 3] Create → Update → Delete...")
    ts = time.strftime("%H%M%S")
    data = parse(tb.create_task(
        project_id=WUFN_PROJECT_ID,
        content=f"[回归测试] auto-login {ts}",
    ))
    assert data["status"] == "success"
    task_id = data["_id"]
    print(f"  ✅ 创建成功: {task_id}")

    data = parse(
        tb.update_task(
            task_id=task_id,
            project_id=WUFN_PROJECT_ID,
            content=f"[回归测试-已更新] {ts}",
        )
    )
    assert data["status"] == "success"
    print(f"  ✅ 更新成功")

    data = parse(tb.delete_task(task_id=task_id, project_id=WUFN_PROJECT_ID))
    assert data["status"] == "success"
    print(f"  ✅ 删除成功")

    # Test 4: login 工具不传参数（从 .env 读取）
    print("\n[Test 4] login() 不传参数（从 .env 读取）...")
    data = parse(tb.login())
    assert data["status"] == "success"
    print(f"  ✅ login() 无参数登录成功: {data['name']}")

    print("\n" + "=" * 60)
    print("🎉 回归测试全部通过！")
    print("  ✅ .env 自动登录")
    print("  ✅ login() 无参数从 .env 读取")
    print("  ✅ list_projects / list_tasks / create / update / delete")
    print("=" * 60)


if __name__ == "__main__":
    main()
