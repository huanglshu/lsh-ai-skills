import sys, json
sys.path.insert(0, '.')
from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID

_ensure_logged_in()
client = _get_client()

# 查询所有未知的自定义字段ID
unknown_ids = ["693793817ad8b6f61a769ed7", "69b3e4407ad8b6f61a76ef3e"]
# 也查已知的确认一下
all_ids = [
    "693922107ad8b6f61a76a168",  # 系统
    "693793de7ad8b6f61a769edc",  # 业务价值
    "5d1b3638ce9f165cd5d980b5",  # 开发组
    "693910667ad8b6f61a76a0fd",  # 提出人
    "693793817ad8b6f61a769ed7",  # ?
    "69b21bbf7ad8b6f61a76ebe1",  # 上线时间
    "69b3e4407ad8b6f61a76ef3e",  # ?
]

for cid in all_ids:
    resp = _retry_request(lambda cid=cid: client.get(
        f'/api/v2/customfields/{cid}',
        headers={'X-Tenant-Id': ORG_ID}
    ))
    if resp.status_code == 200:
        d = resp.json()
        print(f"_id={cid}, name={d.get('name')}, type={d.get('type')}")
        choices = d.get('choices', [])
        if choices:
            for c in choices[:5]:
                print(f"    choice: {c.get('title','?')} -> {c.get('_id','?')}")
    else:
        print(f"_id={cid}, status={resp.status_code}")
