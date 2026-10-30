"""查询古妙霞用户ID + 完整字段 + 分类选项"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID

def main():
    _ensure_logged_in()
    client = _get_client()
    
    # 1. 搜索用户 古妙霞
    resp = _retry_request(lambda: client.get(
        "/api/organizations/5be50c1ebe825b60a7ad0894/members",
        params={"q": "古妙霞", "count": "5"},
        headers={"X-Tenant-Id": ORG_ID}
    ))
    members = resp.json()
    print("=== 搜索 古妙霞 ===")
    if isinstance(members, list):
        for m in members:
            print(f"  _id: {m.get('_id')}, name: {m.get('name')}, email: {m.get('email')}")
    else:
        print(json.dumps(members, ensure_ascii=False, indent=2)[:1000])
    
    # 2. 获取分类下拉选项
    cf_id = "693922107ad8b6f61a76a168"
    resp2 = _retry_request(lambda: client.get(
        f"/api/customfields/{cf_id}",
        headers={"X-Tenant-Id": ORG_ID}
    ))
    cf = resp2.json()
    print(f"\n=== 分类字段 ({cf.get('name', cf.get('label'))}) ===")
    choices = cf.get("choices", [])
    for c in choices:
        print(f"  _id: {c.get('_id')}, title: {c.get('title')}")
    
    # 3. 获取更多自定义字段配置（693793de7ad8b6f61a769edc 等）
    for fid in ["693793de7ad8b6f61a769edc", "693910667ad8b6f61a76a0fd", "69b21bbf7ad8b6f61a76ebe1"]:
        resp3 = _retry_request(lambda: client.get(
            f"/api/customfields/{fid}",
            headers={"X-Tenant-Id": ORG_ID}
        ))
        data = resp3.json()
        print(f"\n=== 自定义字段 {fid} ===")
        print(f"  name: {data.get('name', data.get('label'))}")
        print(f"  type: {data.get('type')}")
        choices2 = data.get("choices", [])
        if choices2:
            for c in choices2[:5]:
                print(f"  choice: {c.get('_id')} -> {c.get('title')}")

if __name__ == "__main__":
    main()
