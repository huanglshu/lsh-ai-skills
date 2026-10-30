import sys, json, uuid
sys.path.insert(0, '.')
from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID

_ensure_logged_in()
client = _get_client()

task_id = "69d4db3b798759002a5ae842"

# 设置"开发人天"= 1 (number类型)
body = {
    "_customfieldId": "69b3e4407ad8b6f61a76ef3e",
    "type": "number",
    "value": [{"title": "1"}]
}
resp = _retry_request(lambda: client.put(
    f'/api/tasks/{task_id}/customfields',
    json=body,
    headers={
        'Content-Type': 'application/json',
        'X-Tenant-Id': ORG_ID,
        'x-request-id': str(uuid.uuid4()),
    }
))
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print("OK - 开发人天=1 设置成功")
else:
    print(resp.text[:500])
    # 尝试其他格式
    body2 = {
        "_customfieldId": "69b3e4407ad8b6f61a76ef3e",
        "type": "number",
        "value": [1]
    }
    resp2 = _retry_request(lambda: client.put(
        f'/api/tasks/{task_id}/customfields',
        json=body2,
        headers={
            'Content-Type': 'application/json',
            'X-Tenant-Id': ORG_ID,
            'x-request-id': str(uuid.uuid4()),
        }
    ))
    print(f"Retry Status: {resp2.status_code}")
    if resp2.status_code == 200:
        print("OK (format 2) - 开发人天=1 设置成功")
    else:
        print(resp2.text[:500])
