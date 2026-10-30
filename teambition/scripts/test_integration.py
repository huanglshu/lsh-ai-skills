"""
Phase 3 集成测试：端到端工作流
Login → List Projects → List Tasks → Create Task → Update Task → Delete Task
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
PROJECT_ID = "65efbd2d7ad8b6f61a7516a1"  # 奥飞业务中台系统
USER_ID = "5bea5a57be825b33ab9afacb"  # 李光华


def parse(result: str) -> dict:
    """解析工具返回的 JSON 字符串"""
    return json.loads(result)


def run_integration_test():
    passed = 0
    failed = 0
    errors = []

    print("=" * 60)
    print("🔗 Teambition MCP Skill - 端到端集成测试")
    print("=" * 60)

    # --- Step 1: Login ---
    print("\n[Step 1/6] 登录...")
    try:
        data = parse(login(EMAIL, PASSWORD))
        assert data["status"] == "success"
        assert data["userId"] == USER_ID
        print(f"  ✅ 登录成功: {data['name']}")
        passed += 1
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        failed += 1
        errors.append(f"login: {e}")
        return  # 登录失败则后续无法继续

    # --- Step 2: List Projects ---
    print("\n[Step 2/6] 查询项目列表...")
    try:
        data = parse(list_projects(page_size=10, fetch_all=False))
        assert data["status"] == "success"
        assert data["count"] > 0
        # 检查目标项目在列表中
        project_ids = [p["_id"] for p in data["projects"]]
        assert PROJECT_ID in project_ids, f"目标项目 {PROJECT_ID} 不在列表中"
        target = next(p for p in data["projects"] if p["_id"] == PROJECT_ID)
        print(f"  ✅ 查到 {data['count']} 个项目，目标: {target['name']}")
        passed += 1
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        failed += 1
        errors.append(f"list_projects: {e}")

    # --- Step 3: List Tasks ---
    print("\n[Step 3/6] 查询任务列表...")
    try:
        data = parse(list_tasks(project_id=PROJECT_ID, page_size=5))
        assert data["status"] == "success"
        assert data["count"] > 0
        print(f"  ✅ 查到 {data['count']} 个任务，首个: {data['tasks'][0]['content']}")
        passed += 1
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        failed += 1
        errors.append(f"list_tasks: {e}")

    # --- Step 4: Create Task ---
    print("\n[Step 4/6] 创建测试任务...")
    task_id = None
    try:
        data = parse(create_task(
            project_id=PROJECT_ID,
            content="[集成测试] E2E 完整流程验证",
            note="由集成测试自动创建，验证后自动删除",
            executor_id=USER_ID,
            priority=1,
        ))
        assert data["status"] == "success"
        task_id = data["_id"]
        print(f"  ✅ 创建成功: {data['content']}（编号: {data.get('uniqueId')}）")
        passed += 1
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        failed += 1
        errors.append(f"create_task: {e}")

    # --- Step 5: Update Task ---
    if task_id:
        print(f"\n[Step 5/6] 更新任务（{task_id}）...")
        try:
            data = parse(update_task(
                task_id=task_id,
                project_id=PROJECT_ID,
                content="[集成测试] E2E 完整流程验证（已更新）",
                note="更新后的描述 - " + time.strftime("%Y-%m-%d %H:%M:%S"),
                priority=2,
            ))
            assert data["status"] == "success"
            assert any(u["type"] == "basic" for u in data["updates"])
            print(f"  ✅ 更新成功: {data['updates']}")
            passed += 1
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            failed += 1
            errors.append(f"update_task: {e}")

        # --- Step 6: Delete Task ---
        print(f"\n[Step 6/6] 删除任务（{task_id}）...")
        try:
            data = parse(delete_task(task_id=task_id, project_id=PROJECT_ID))
            assert data["status"] == "success"
            assert data["isArchived"] is True
            print(f"  ✅ 删除成功")
            passed += 1
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            failed += 1
            errors.append(f"delete_task: {e}")
    else:
        print("\n[Step 5/6] ⏭ 跳过（无任务ID）")
        print("[Step 6/6] ⏭ 跳过（无任务ID）")
        failed += 2

    # --- 结果汇总 ---
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"📊 集成测试结果: {passed}/{total} 通过")
    if errors:
        print("❌ 失败项:")
        for e in errors:
            print(f"   - {e}")
    else:
        print("🎉 全部通过！6/6 工具端到端验证成功")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
