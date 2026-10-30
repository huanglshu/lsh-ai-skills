"""测试 add_involvers 工具"""
import sys, json
sys.path.insert(0, '.')
from teambition_mcp_server import add_involvers, _ensure_logged_in, _get_client, _retry_request, ORG_ID

task_id = "69d4db3b798759002a5ae842"
project_id = "693907787ad8b6f61a76a0a6"

# 先查看当前参与者
_ensure_logged_in()
client = _get_client()
resp = _retry_request(lambda: client.get(
    f'/api/v2/tasks/{task_id}',
    headers={'X-Tenant-Id': ORG_ID}
))
data = resp.json()
print(f"当前参与者IDs: {data.get('involveMembers', [])}")

# 先移除古妙霞（如果已存在），然后用工具重新添加
gumiaoxia_id = "665d864abf5f11b187aa5279"
if gumiaoxia_id in data.get('involveMembers', []):
    print(f"\n古妙霞已是参与者，先移除...")
    resp2 = _retry_request(lambda: client.put(
        f'/api/tasks/{task_id}/involveMembers',
        json={"delInvolvers": [gumiaoxia_id]},
        headers={'Content-Type': 'application/json', 'x-request-id': 'test-remove'}
    ))
    print(f"移除结果: {resp2.status_code}")

# 使用 MCP 工具添加古妙霞
print("\n=== 测试 add_involvers 工具 ===")
result = add_involvers(task_id=task_id, user_ids=gumiaoxia_id, project_id=project_id)
print(f"结果:\n{result}")

# 验证
parsed = json.loads(result)
if parsed.get("status") == "success":
    print(f"\n✅ 测试通过！")
    print(f"   参与者数: {len(parsed.get('involvers', []))}")
    for m in parsed.get('involvers', []):
        print(f"   - {m.get('name')} ({m.get('_id')})")
else:
    print(f"\n❌ 测试失败: {result}")
