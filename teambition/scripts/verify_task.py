import sys, json
sys.path.insert(0, '.')
from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID

_ensure_logged_in()
client = _get_client()

task_id = "69d4db3b798759002a5ae842"
resp = _retry_request(lambda: client.get(
    f'/api/v2/tasks/{task_id}',
    params={'withCustomfields': True},
    headers={'X-Tenant-Id': ORG_ID}
))
data = resp.json()
print(f"标题: {data.get('content')}")
print(f"备注: {data.get('note','')[:100]}")
print(f"执行人: {data.get('executor', {}).get('name', 'N/A')}")
print(f"截止日期: {data.get('dueDate')}")
print(f"状态: isDone={data.get('isDone')}")

cfs = data.get('customfields', [])
print(f"\n自定义字段 ({len(cfs)}):")
for cf in cfs:
    cfid = cf.get('_customfieldId', '?')
    ctype = cf.get('type', '?')
    val = cf.get('value', [])
    vals = cf.get('values', [])
    print(f"  cfId={cfid}, type={ctype}, value={json.dumps(val, ensure_ascii=False)[:200]}, values={json.dumps(vals, ensure_ascii=False)[:100]}")
