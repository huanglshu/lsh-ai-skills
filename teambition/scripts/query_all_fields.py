import sys, json
sys.path.insert(0, '.')
from teambition_mcp_server import _ensure_logged_in, _get_client, _retry_request, ORG_ID

_ensure_logged_in()
client = _get_client()

resp = _retry_request(lambda: client.get(
    '/api/v2/projects/693907787ad8b6f61a76a0a6/scenariofieldconfigs',
    headers={'X-Tenant-Id': ORG_ID}
))
data = resp.json()
for cfg in data:
    if cfg.get('objectType') == 'task' and cfg.get('isDefault'):
        sfields = cfg.get('scenariofields', [])
        print(f"scenariofields ({len(sfields)} fields):")
        for i, f in enumerate(sfields):
            print(f"\n--- field[{i}] ---")
            print(json.dumps(f, ensure_ascii=False, indent=2)[:500])
        break
