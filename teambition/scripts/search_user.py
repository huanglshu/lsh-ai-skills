"""搜索古妙霞 + 查看分类选项详情"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID

def main():
    _ensure_logged_in()
    client = _get_client()
    
    # 1. 换不同接口搜索用户
    print("=== 搜索用户: 古妙霞 ===")
    for endpoint in [
        f"/api/v2/organizations/{ORG_ID}/members?pageSize=5&keyword=古妙霞",
        f"/api/organizations/{ORG_ID}/members/search?q=古妙霞",
        f"/api/organizations/{ORG_ID}/search/members?keyword=妙霞&pageSize=5",
    ]:
        try:
            resp = _retry_request(lambda: client.get(endpoint, headers={"X-Tenant-Id": ORG_ID}))
            data = resp.json()
            print(f"\n  Endpoint: {endpoint}")
            print(f"  Status: {resp.status_code}")
            if isinstance(data, list):
                for m in data[:3]:
                    name = m.get("name", m.get("title", ""))
                    uid = m.get("_id", "")
                    print(f"    {uid} - {name}")
            elif isinstance(data, dict):
                result = data.get("result", data.get("members", []))
                if isinstance(result, list):
                    for m in result[:3]:
                        name = m.get("name", m.get("title", ""))
                        uid = m.get("_id", "")
                        print(f"    {uid} - {name}")
                else:
                    print(f"    {json.dumps(data, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"  Error: {e}")
    
    # 2. 重新获取分类字段详情（包含 choices 的 title）
    print("\n\n=== 分类下拉(完整) ===")
    resp = _retry_request(lambda: client.get(
        f"/api/customfields/693922107ad8b6f61a76a168",
        headers={"X-Tenant-Id": ORG_ID}
    ))
    cf = resp.json()
    print(json.dumps(cf, ensure_ascii=False, indent=2)[:2000])

if __name__ == "__main__":
    main()
