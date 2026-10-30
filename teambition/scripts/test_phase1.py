"""
Teambition MCP Server 快速测试脚本
直接调用工具函数验证登录、查项目、查任务
"""

import sys
import json

sys.path.insert(0, r"/Users/caizhijian/ai/teambition/scripts")

from teambition_mcp_server import login, list_projects, list_tasks

def test_login():
    print("=" * 60)
    print("测试 1: login")
    print("=" * 60)
    result = login(email="echizen_hua@163.com", password="Hua902201$")
    print(result)
    parsed = json.loads(result)
    assert parsed["status"] == "success", f"登录失败: {result}"
    assert parsed["name"] == "李光华", f"用户名不匹配: {parsed['name']}"
    print("✅ login 测试通过\n")
    return parsed

def test_list_projects():
    print("=" * 60)
    print("测试 2: list_projects")
    print("=" * 60)
    result = list_projects(page_size=10, fetch_all=False)
    print(result[:500] + "..." if len(result) > 500 else result)
    parsed = json.loads(result)
    assert parsed["status"] == "success", f"查询失败: {result}"
    assert parsed["count"] > 0, "项目数量为 0"
    print(f"✅ list_projects 测试通过（共 {parsed['count']} 个项目）\n")
    return parsed

def test_list_tasks():
    print("=" * 60)
    print("测试 3: list_tasks")
    print("=" * 60)
    # 使用奥飞业务中台系统
    project_id = "65efbd2d7ad8b6f61a7516a1"
    result = list_tasks(project_id=project_id, page_size=5)
    print(result[:500] + "..." if len(result) > 500 else result)
    parsed = json.loads(result)
    assert parsed["status"] == "success", f"查询失败: {result}"
    print(f"✅ list_tasks 测试通过（共 {parsed['count']} 个任务）\n")
    return parsed

if __name__ == "__main__":
    try:
        test_login()
        test_list_projects()
        test_list_tasks()
        print("🎉 所有测试通过！")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
