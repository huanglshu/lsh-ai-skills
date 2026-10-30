"""测试 create_task 工具的 involver_ids 集成"""
import sys, json
sys.path.insert(0, '.')
from teambition_mcp_server import create_task, delete_task

# 在 WUFN 项目创建测试任务，并自动添加古妙霞为参与者
result = create_task(
    project_id="693907787ad8b6f61a76a0a6",
    content="[测试] create_task 自动添加参与者功能验证",
    executor_id="5bea5a57be825b33ab9afacb",  # 李光华
    note="此任务用于测试 create_task 的 involver_ids 参数，测试后删除。",
    involver_ids="665d864abf5f11b187aa5279",  # 古妙霞 involveMembers ID
)

print("create_task 返回:")
print(result)

parsed = json.loads(result)
if parsed.get("status") == "success":
    task_id = parsed.get("_id")
    involvers = parsed.get("involvers", [])
    print(f"\n✅ 任务创建成功！ID: {task_id}")
    if involvers:
        print(f"   参与者: {', '.join(m.get('name','?') for m in involvers)}")
    else:
        print("   ⚠️ 参与者列表为空")
    
    # 清理：删除测试任务
    print(f"\n正在清理测试任务...")
    del_result = delete_task(
        task_id=task_id,
        project_id="693907787ad8b6f61a76a0a6",
    )
    print(f"删除结果: {del_result}")
else:
    print(f"\n❌ 创建失败: {result}")
