"""
Teambition MCP Server - 私有化部署项目管理工具
支持登录、查询项目、查询/创建/编辑/删除任务
"""

import os
import re
import json
import logging
import uuid
import time
from pathlib import Path
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP


# --------------- .env 文件加载 ---------------


def _load_dotenv():
    """从 .env 文件加载环境变量（不覆盖已有的）"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value


_load_dotenv()


def _load_multiline_json_env_from_file(env_key: str) -> str:
    """从 .env 文件中读取多行 JSON 类型环境变量。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return ""

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""

    prefix = f"{env_key}="
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(prefix):
            continue

        initial_value = line.partition("=")[2].strip()
        if not initial_value:
            return ""

        candidate = initial_value
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, (list, dict)):
                return candidate
        except json.JSONDecodeError:
            pass

        for follow_line in lines[index + 1:]:
            candidate = f"{candidate}\n{follow_line.rstrip()}"
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, (list, dict)):
                return candidate
            return ""

        return ""

    return ""


# --------------- 重试辅助 ---------------


def _retry_request(func, max_retries: int = 2, retry_delay: float = 1.0):
    """对 HTTP 请求进行重试，处理网络波动"""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
            last_error = e
            if attempt < max_retries:
                log.warning(
                    "请求失败（第%d次），%0.1f秒后重试: %s", attempt + 1, retry_delay, e
                )
                time.sleep(retry_delay)
    if last_error is not None:
        raise last_error
    else:
        # This should not happen, but just in case
        raise RuntimeError("Retry loop exited without an error")


# --------------- 配置 ---------------
BASE_URL = os.getenv("TB_BASE_URL", "https://i2m.gdalpha.com:4431")
ORG_ID = os.getenv("TB_ORG_ID", "5be50c1ebe825b60a7ad0894")
VERIFY_SSL = os.getenv("TB_VERIFY_SSL", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("teambition-mcp")

# --------------- MCP Server ---------------
mcp = FastMCP("teambition")

# --------------- Session 管理 ---------------
_client: Optional[httpx.Client] = None
_logged_in_user: Optional[dict] = None


def _get_client() -> httpx.Client:
    """获取或创建 HTTP 客户端（带持久化 Cookie）"""
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=BASE_URL,
            verify=VERIFY_SSL,
            timeout=30.0,
            follow_redirects=True,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
    return _client


def _ensure_logged_in() -> None:
    """检查登录状态，未登录时尝试从环境变量自动登录"""
    global _logged_in_user
    if _logged_in_user is not None:
        return

    # 优先使用持久化 Cookie；未配置或已过期时回退到账号密码。
    env_cookie = os.getenv("TB_COOKIE", "").strip()
    if env_cookie:
        log.info("检测到 .env Cookie，自动登录中...")
        result = _do_cookie_login(env_cookie)
        if _logged_in_user is not None:
            return
        log.warning("Cookie 自动登录失败: %s", result)

    env_email = os.getenv("TB_EMAIL", "")
    env_password = os.getenv("TB_PASSWORD", "")
    if env_email and env_password:
        log.info("检测到 .env 凭据，自动登录中...")
        result = _do_login(env_email, env_password)
        if _logged_in_user is not None:
            return
        log.warning("自动登录失败: %s", result)

    raise RuntimeError(
        "未登录，请先调用 login 工具进行登录（或在 .env 中配置 TB_COOKIE / TB_EMAIL / TB_PASSWORD）"
    )


# --------------- 项目配置缓存 ---------------

_project_config_cache: dict[str, dict] = {}
_project_config_cache_time: dict[str, float] = {}
CACHE_TTL = 1800  # 缓存有效期 30 分钟

# 项目默认提出人兜底配置：未配置环境变量时使用。
DEFAULT_PROPOSER_BY_PROJECT_FALLBACK = {
    "693907787ad8b6f61a76a0a6": {
        "project_name": "奥飞财经系统",
        "name": "古妙霞",
        "member_id": "665d864aeddf7ef85e0e4c14",  # lookup 成员ID（用于提出人字段）
        "user_id": "665d864abf5f11b187aa5279",  # 用户ID（用于参与者）
        "proposer_custom_field_id": "693910667ad8b6f61a76a0fd",
        "proposer_custom_field_name": "提出人",
        "executorname": "登录用户",
        "default_involver_include_proposer": True,
        "default_involver_include_executor": True,
    },
    "65efbd2d7ad8b6f61a7516a1": {
        "project_name": "奥飞业务中台系统",
        "name": "陈靖文",
        "member_id": "6863879eeddf7ef85e0e51d8",  # lookup 成员ID（用于提出人字段）
        "user_id": "6863879cbf5f11b187aa547f",  # 用户ID（用于参与者）
        "proposer_custom_field_id": None,
        "proposer_custom_field_name": "提出人",
        "executorname": "登录用户",
        "default_involver_include_proposer": True,
        "default_involver_include_executor": True,
    },
}


def _parse_participant_rule(rule_value: str) -> tuple[bool, bool]:
    """解析“参与者”规则，决定是否自动加入提出人/执行者。"""
    normalized = (rule_value or "").replace(" ", "").lower()
    if not normalized:
        return True, True

    include_proposer = ("name" in normalized) or ("提出人" in normalized)
    include_executor = (
        ("executorname" in normalized)
        or ("执行者" in normalized)
        or ("登录用户" in rule_value)
    )
    return include_proposer, include_executor


def _normalize_default_proposer_config(config: dict, project_id: str = "") -> dict:
    """规范化默认提出人配置，兼容旧格式和新格式。"""
    proposer_field_raw = config.get("proposer_custom_field_name")
    proposer_field_name = "提出人"
    proposer_field_rules: dict[str, str] = {}
    include_proposer = True
    include_executor = True

    if isinstance(proposer_field_raw, dict):
        for key, value in proposer_field_raw.items():
            field_key = str(key or "").strip()
            field_value = str(value or "").strip()
            if field_key:
                proposer_field_rules[field_key] = field_value

        if "提出人" in proposer_field_rules:
            proposer_field_name = "提出人"
        else:
            for field_key, field_value in proposer_field_rules.items():
                normalized_value = field_value.lower()
                if normalized_value in ("name", "proposer", "proposer_name"):
                    proposer_field_name = field_key
                    break

        include_proposer, include_executor = _parse_participant_rule(
            proposer_field_rules.get("参与者", "")
        )
    elif proposer_field_raw is not None:
        proposer_field_name = str(proposer_field_raw).strip() or "提出人"

    proposer_custom_field_id = config.get("proposer_custom_field_id")
    if proposer_custom_field_id is not None:
        proposer_custom_field_id = str(proposer_custom_field_id).strip() or None

    normalized = {
        "project_id": str(project_id or config.get("project_id") or "").strip(),
        "project_name": str(config.get("project_name") or "").strip(),
        "name": str(config.get("name") or "").strip(),
        "member_id": str(config.get("member_id") or "").strip(),
        "user_id": str(config.get("user_id") or "").strip(),
        "executorname": str(config.get("executorname") or "登录用户").strip() or "登录用户",
        "executor_user_id": str(config.get("executor_user_id") or "").strip(),
        "proposer_custom_field_id": proposer_custom_field_id,
        "proposer_custom_field_name": proposer_field_name,
        "proposer_custom_field_rules": proposer_field_rules,
        "default_involver_include_proposer": include_proposer,
        "default_involver_include_executor": include_executor,
    }
    return normalized


def _load_default_proposer_by_project() -> tuple[dict[str, dict], dict[str, dict]]:
    """从环境变量加载项目默认提出人配置，支持项目ID映射和项目名称映射。"""
    # 修改说明:
    # v1.4 2026-04-08 支持 name-only 配置（按 project_name），运行时自动解析 project_id/member_id/user_id
    raw_json = os.getenv("TB_DEFAULT_PROPOSER_BY_PROJECT_JSON", "").strip()
    # 修改说明:
    # v1.8 2026-04-08 兼容 .env 多行 JSON（用户按项目名称配置时无需改单行）
    if not raw_json or raw_json in ("[", "{"):
        rebuilt_json = _load_multiline_json_env_from_file(
            "TB_DEFAULT_PROPOSER_BY_PROJECT_JSON"
        ).strip()
        if rebuilt_json:
            raw_json = rebuilt_json
            log.info("已从 .env 重组多行默认提出人配置（length=%d）", len(raw_json))
    else:
        try:
            probe = json.loads(raw_json)
            if not isinstance(probe, (list, dict)):
                rebuilt_json = _load_multiline_json_env_from_file(
                    "TB_DEFAULT_PROPOSER_BY_PROJECT_JSON"
                ).strip()
                if rebuilt_json:
                    raw_json = rebuilt_json
                    log.info("检测到环境变量格式异常，已回退使用 .env 多行配置")
        except json.JSONDecodeError:
            rebuilt_json = _load_multiline_json_env_from_file(
                "TB_DEFAULT_PROPOSER_BY_PROJECT_JSON"
            ).strip()
            if rebuilt_json:
                raw_json = rebuilt_json
                log.info("环境变量JSON解析失败，已回退使用 .env 多行配置")

    if not raw_json:
        return dict(DEFAULT_PROPOSER_BY_PROJECT_FALLBACK), {}

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        log.warning(
            "TB_DEFAULT_PROPOSER_BY_PROJECT_JSON 解析失败，使用兜底配置: %s",
            exc,
        )
        return dict(DEFAULT_PROPOSER_BY_PROJECT_FALLBACK), {}

    loaded_by_id: dict[str, dict] = {}
    loaded_by_name: dict[str, dict] = {}

    if isinstance(parsed, dict) and isinstance(parsed.get("projects"), list):
        parsed = parsed.get("projects", [])

    if isinstance(parsed, list):
        for config in parsed:
            if not isinstance(config, dict):
                continue
            normalized = _normalize_default_proposer_config(config)
            project_id = normalized.get("project_id", "")
            project_name = normalized.get("project_name", "")
            if project_id:
                loaded_by_id[project_id] = normalized
            elif project_name:
                loaded_by_name[project_name] = normalized
    elif isinstance(parsed, dict):
        for project_id, config in parsed.items():
            if not isinstance(config, dict):
                continue
            normalized_project_id = str(project_id).strip()
            project_id_seed = ""
            if re.fullmatch(r"[0-9a-fA-F]{24}", normalized_project_id):
                project_id_seed = normalized_project_id

            normalized = _normalize_default_proposer_config(config, project_id_seed)
            if (not project_id_seed) and normalized_project_id and not normalized.get("project_name"):
                normalized["project_name"] = normalized_project_id

            normalized_project_id = normalized.get("project_id", "")
            project_name = normalized.get("project_name", "")
            if normalized_project_id:
                loaded_by_id[normalized_project_id] = normalized
            if project_name:
                loaded_by_name[project_name] = normalized
    else:
        log.warning(
            "TB_DEFAULT_PROPOSER_BY_PROJECT_JSON 既不是对象也不是数组，使用兜底配置"
        )
        return dict(DEFAULT_PROPOSER_BY_PROJECT_FALLBACK), {}

    if not loaded_by_id and not loaded_by_name:
        log.warning(
            "TB_DEFAULT_PROPOSER_BY_PROJECT_JSON 未加载到有效配置，使用兜底配置"
        )
        return dict(DEFAULT_PROPOSER_BY_PROJECT_FALLBACK), {}

    log.info(
        "已从环境变量加载默认提出人映射（project_id_count=%d, project_name_count=%d）",
        len(loaded_by_id),
        len(loaded_by_name),
    )
    return loaded_by_id, loaded_by_name


DEFAULT_PROPOSER_BY_PROJECT, DEFAULT_PROPOSER_BY_PROJECT_NAME = _load_default_proposer_by_project()

_custom_field_meta_cache: dict[str, dict] = {}
_custom_field_meta_cache_time: dict[str, float] = {}
_member_lookup_cache: dict[str, dict] = {}
_project_name_id_cache: dict[str, str] = {}
_project_name_id_cache_time: float = 0.0
_project_sprint_cache: dict[str, dict[str, str]] = {}
_project_sprint_cache_time: dict[str, float] = {}
_project_commongroup_cache: dict[str, dict[str, dict[str, str]]] = {}
_project_commongroup_cache_time: dict[str, float] = {}


def _get_custom_field_meta(client: httpx.Client, custom_field_id: str) -> dict:
    """获取自定义字段元信息（name/type），带缓存。"""
    now = time.time()
    if custom_field_id in _custom_field_meta_cache:
        if now - _custom_field_meta_cache_time.get(custom_field_id, 0) < CACHE_TTL:
            return _custom_field_meta_cache[custom_field_id]
        del _custom_field_meta_cache[custom_field_id]

    resp = _retry_request(lambda: client.get(f"/api/customfields/{custom_field_id}"))
    if resp.status_code != 200:
        return {}

    data = resp.json() if isinstance(resp.json(), dict) else {}
    _custom_field_meta_cache[custom_field_id] = data
    _custom_field_meta_cache_time[custom_field_id] = time.time()
    return data


def _find_custom_field_id_by_name(
    client: httpx.Client, config: dict, field_name: str
) -> Optional[str]:
    """按字段名称在项目场景字段中查找 custom field id。"""
    for field in config.get("customFields", []):
        custom_field_id = field.get("_customfieldId")
        if not custom_field_id:
            continue

        meta = _get_custom_field_meta(client, custom_field_id)
        meta_name = (meta.get("name") or meta.get("label") or "").strip()
        if meta_name == field_name:
            return custom_field_id
    return None


def _collect_project_tasks_raw(
    client: httpx.Client,
    project_id: str,
    is_done: str,
    max_pages: int = 8,
) -> list[dict]:
    """分页获取项目任务原始数据。"""
    tasks: list[dict] = []
    next_page_token: Optional[str] = None

    for _ in range(max_pages):
        params = {
            "_projectId": project_id,
            "isDone": is_done,
            "pageSize": "100",
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        resp = _retry_request(lambda params=params: client.get("/api/v2/tasks", params=params))
        if resp.status_code != 200:
            break

        data = resp.json() if isinstance(resp.json(), dict) else {}
        page_tasks = data.get("result", [])
        if isinstance(page_tasks, list):
            tasks.extend([t for t in page_tasks if isinstance(t, dict)])

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return tasks


def _refresh_project_sprint_cache(client: httpx.Client, project_id: str) -> None:
    """刷新项目迭代名称到ID映射。"""
    now = time.time()
    if project_id in _project_sprint_cache:
        if now - _project_sprint_cache_time.get(project_id, 0) < CACHE_TTL:
            return

    sprint_id_to_name: dict[str, str] = {}
    # v1.6 2026-04-08 优先使用项目 sprint 接口，避免仅依赖历史任务导致迭代缺失
    log.info("正在刷新项目迭代缓存（project=%s）...", project_id)
    sprint_resp = _retry_request(
        lambda: client.get(
            f"/api/projects/{project_id}/sprints",
            headers={"X-Tenant-Id": ORG_ID},
        )
    )

    if sprint_resp.status_code == 200 and isinstance(sprint_resp.json(), list):
        for sprint_item in sprint_resp.json():
            if not isinstance(sprint_item, dict):
                continue
            sprint_id = str(sprint_item.get("_id") or "").strip()
            sprint_name = str(sprint_item.get("name") or "").strip()
            if sprint_id and sprint_name:
                sprint_id_to_name[sprint_name] = sprint_id

    if not sprint_id_to_name:
        raw_tasks = _collect_project_tasks_raw(client, project_id, "false")
        raw_tasks.extend(_collect_project_tasks_raw(client, project_id, "true"))

        checked_task_ids: set[str] = set()
        for task in raw_tasks:
            task_id = str(task.get("_id") or "").strip()
            sprint_id = str(task.get("_sprintId") or "").strip()
            if not task_id or not sprint_id or task_id in checked_task_ids:
                continue
            checked_task_ids.add(task_id)

            detail_resp = _retry_request(
                lambda task_id=task_id: client.get(
                    f"/api/tasks/{task_id}",
                    headers={"X-Tenant-Id": ORG_ID},
                )
            )
            if detail_resp.status_code != 200:
                continue

            detail = detail_resp.json() if isinstance(detail_resp.json(), dict) else {}
            sprint = detail.get("sprint") if isinstance(detail.get("sprint"), dict) else {}
            sprint_name = str(sprint.get("name") or "").strip()
            if sprint_name:
                sprint_id_to_name[sprint_name] = sprint_id

    log.info("项目迭代缓存刷新完成（project=%s, count=%d）", project_id, len(sprint_id_to_name))

    _project_sprint_cache[project_id] = sprint_id_to_name
    _project_sprint_cache_time[project_id] = time.time()


def _resolve_sprint_id_by_name(
    client: httpx.Client,
    project_id: str,
    sprint_name: str,
) -> Optional[str]:
    """按迭代名称解析 sprint_id。"""
    normalized_name = (sprint_name or "").strip()
    if not normalized_name:
        return None

    _refresh_project_sprint_cache(client, project_id)
    mapping = _project_sprint_cache.get(project_id, {})
    if normalized_name in mapping:
        return mapping[normalized_name]

    for known_name, sprint_id in mapping.items():
        if normalized_name in known_name or known_name in normalized_name:
            return sprint_id
    return None


def _refresh_project_commongroup_cache(
    client: httpx.Client,
    project_id: str,
    custom_field_id: str,
) -> None:
    """刷新 commongroup 字段 title->id 映射。"""
    now = time.time()
    cache_key = f"{project_id}:{custom_field_id}"
    existing = _project_commongroup_cache.get(cache_key)
    if existing and now - _project_commongroup_cache_time.get(cache_key, 0) < CACHE_TTL:
        return

    title_to_id: dict[str, str] = {}
    raw_tasks = _collect_project_tasks_raw(client, project_id, "false")
    raw_tasks.extend(_collect_project_tasks_raw(client, project_id, "true"))

    for task in raw_tasks:
        for custom_field in task.get("customfields", []) or []:
            if not isinstance(custom_field, dict):
                continue
            if custom_field.get("_customfieldId") != custom_field_id:
                continue

            for item in custom_field.get("value", []) or []:
                if not isinstance(item, dict):
                    continue
                item_title = str(item.get("title") or "").strip()
                item_id = str(item.get("_id") or "").strip()
                if item_title and item_id:
                    title_to_id[item_title] = item_id

    _project_commongroup_cache[cache_key] = title_to_id
    _project_commongroup_cache_time[cache_key] = time.time()


def _resolve_commongroup_id_by_title(
    client: httpx.Client,
    project_id: str,
    custom_field_id: str,
    title: str,
) -> Optional[str]:
    """按标题解析 commongroup 的 _id，未命中时返回任意可用 _id 作为兜底。"""
    normalized_title = (title or "").strip()
    if not normalized_title:
        return None

    _refresh_project_commongroup_cache(client, project_id, custom_field_id)
    cache_key = f"{project_id}:{custom_field_id}"
    title_to_id = _project_commongroup_cache.get(cache_key, {})

    if normalized_title in title_to_id:
        return title_to_id[normalized_title]

    for known_title, value_id in title_to_id.items():
        if normalized_title in known_title or known_title in normalized_title:
            return value_id

    if title_to_id:
        return next(iter(title_to_id.values()))
    return None


def _resolve_rule_text_value(
    rule_value: str,
    proposer_name: str,
    executor_name: str,
    standardized_note: str,
) -> str:
    """解析规则值中的占位符。"""
    normalized = (rule_value or "").strip()
    lowered = normalized.lower()
    if lowered in ("name", "proposer", "proposer_name"):
        return proposer_name
    if lowered in ("executorname", "executor", "执行者"):
        return executor_name
    if lowered in ("name和executorname", "name+executorname"):
        values = [v for v in [proposer_name, executor_name] if v]
        return "、".join(values)
    if normalized == "登录用户":
        return executor_name
    if normalized == "根据任务内容扩展，包括问题的现象，问题的分析，问题的验证等":
        return standardized_note
    return normalized

def _search_member_by_name(client: httpx.Client, member_name: str) -> dict:
    """按姓名查询成员，返回 member_id 和 user_id。"""
    normalized_name = (member_name or "").strip()
    if not normalized_name:
        return {}

    cache_key = f"{ORG_ID}:{normalized_name}"
    cached = _member_lookup_cache.get(cache_key)
    if cached:
        return cached

    resp = _retry_request(
        lambda: client.get(
            f"/api/organizations/{ORG_ID}/members/search",
            params={"q": normalized_name},
            headers={"X-Tenant-Id": ORG_ID},
        )
    )
    if resp.status_code != 200:
        log.warning("成员检索失败（name=%s, status=%s）", normalized_name, resp.status_code)
        return {}

    payload = resp.json()
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = payload.get("result", payload.get("members", []))
    else:
        candidates = []

    if not isinstance(candidates, list):
        return {}

    target = None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if (item.get("name") or "").strip() == normalized_name:
            target = item
            break
    if target is None:
        for item in candidates:
            if isinstance(item, dict):
                target = item
                break
    if target is None:
        return {}

    resolved = {
        "name": (target.get("name") or normalized_name).strip(),
        "member_id": str(target.get("_id") or target.get("_memberId") or "").strip(),
        "user_id": str(target.get("_userId") or "").strip(),
    }
    if not resolved["user_id"]:
        resolved["user_id"] = resolved["member_id"]

    _member_lookup_cache[cache_key] = resolved
    return resolved


def _refresh_project_name_id_cache(client: httpx.Client) -> None:
    """刷新项目名称到项目ID映射缓存。"""
    global _project_name_id_cache, _project_name_id_cache_time

    now = time.time()
    if _project_name_id_cache and now - _project_name_id_cache_time < CACHE_TTL:
        return

    mapping: dict[str, str] = {}
    next_page_token: Optional[str] = None

    while True:
        params = {
            "selectBy": "joined",
            "orderBy": "name",
            "pageSize": "100",
            "_organizationId": ORG_ID,
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        resp = _retry_request(lambda: client.get("/api/v2/projects", params=params))
        if resp.status_code != 200:
            log.warning("刷新项目名称缓存失败（status=%s）", resp.status_code)
            break

        data = resp.json() if isinstance(resp.json(), dict) else {}
        for project in data.get("result", []):
            if not isinstance(project, dict):
                continue
            project_name = str(project.get("name") or "").strip()
            project_id = str(project.get("_id") or "").strip()
            if project_name and project_id:
                mapping[project_name] = project_id

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    if mapping:
        _project_name_id_cache = mapping
        _project_name_id_cache_time = time.time()
        log.info("项目名称缓存已刷新（count=%d）", len(mapping))


def _resolve_project_id_by_name(client: httpx.Client, project_name: str) -> Optional[str]:
    """按项目名称解析项目ID（支持模糊唯一匹配）。"""
    normalized_name = (project_name or "").strip()
    if not normalized_name:
        return None

    _refresh_project_name_id_cache(client)
    if normalized_name in _project_name_id_cache:
        return _project_name_id_cache[normalized_name]

    matched_ids: list[str] = []
    for cached_name, cached_id in _project_name_id_cache.items():
        if (normalized_name in cached_name) or (cached_name in normalized_name):
            matched_ids.append(cached_id)

    matched_ids = list(dict.fromkeys(matched_ids))
    if len(matched_ids) == 1:
        return matched_ids[0]

    if len(matched_ids) > 1:
        log.warning("项目名称匹配到多个项目（name=%s, matches=%s）", normalized_name, matched_ids)
    else:
        log.warning("未匹配到项目ID（project_name=%s）", normalized_name)
    return None


def _get_default_proposer_config(client: httpx.Client, project_id: str) -> Optional[dict]:
    """获取指定项目的默认提出人配置，支持按 project_name 配置自动解析 project_id。"""
    direct = DEFAULT_PROPOSER_BY_PROJECT.get(project_id)
    if direct:
        return direct

    if not DEFAULT_PROPOSER_BY_PROJECT_NAME:
        return None

    for project_name, config in DEFAULT_PROPOSER_BY_PROJECT_NAME.items():
        resolved_project_id = _resolve_project_id_by_name(client, project_name)
        if resolved_project_id != project_id:
            continue

        matched = dict(config)
        matched["project_id"] = project_id
        DEFAULT_PROPOSER_BY_PROJECT[project_id] = matched
        log.info("按项目名称命中默认提出人配置（project=%s, project_name=%s）", project_id, project_name)
        return matched

    return None


def _resolve_default_proposer(
    client: httpx.Client,
    project_id: str,
    project_config: dict,
    proposer_config: dict,
) -> dict:
    """解析默认提出人配置：支持仅配置姓名，运行时自动补全 ID。"""
    resolved = dict(proposer_config or {})
    proposer_name = (resolved.get("name") or "").strip()
    if not proposer_name:
        return resolved

    if not (resolved.get("member_id") and resolved.get("user_id")):
        member_info = _search_member_by_name(client, proposer_name)
        if member_info.get("member_id"):
            resolved["member_id"] = member_info["member_id"]
        if member_info.get("user_id"):
            resolved["user_id"] = member_info["user_id"]

    executor_name = (resolved.get("executorname") or "登录用户").strip() or "登录用户"
    resolved["executorname"] = executor_name
    if executor_name not in ("登录用户", "当前登录用户", "current_user"):
        if not resolved.get("executor_user_id"):
            executor_info = _search_member_by_name(client, executor_name)
            if executor_info.get("user_id"):
                resolved["executor_user_id"] = executor_info["user_id"]

    field_name = (resolved.get("proposer_custom_field_name") or "提出人").strip() or "提出人"
    resolved["proposer_custom_field_name"] = field_name
    if not resolved.get("proposer_custom_field_id"):
        resolved["proposer_custom_field_id"] = _find_custom_field_id_by_name(
            client, project_config, field_name
        )

    # 缓存解析结果，避免重复查人和查字段
    DEFAULT_PROPOSER_BY_PROJECT[project_id] = resolved
    project_name = (resolved.get("project_name") or "").strip()
    if project_name:
        DEFAULT_PROPOSER_BY_PROJECT_NAME[project_name] = resolved
    return resolved


def _validate_project_required(project_id: str, action_name: str) -> Optional[str]:
    """任务操作强制校验：必须提供项目ID。"""
    normalized_project_id = (project_id or "").strip()
    if normalized_project_id:
        return None

    return (
        f"{action_name}失败：未指定任务所属项目。"
        "请先提供项目ID或项目名称（如：奥飞财经系统 / 奥飞业务中台系统）。"
    )


def _build_standard_task_note(
    content: str,
    note: Optional[str],
    issue_phenomenon: Optional[str] = None,
    possible_reason: Optional[str] = None,
    verification_items: Optional[str] = None,
) -> str:
    """补齐任务备注最少结构：问题现象、可能原因、需要验证。"""
    template_mode = any([issue_phenomenon, possible_reason, verification_items])

    if template_mode:
        phenomenon_text = (issue_phenomenon or "").strip() or content
        reason_text = (possible_reason or "").strip() or "待排查（如：部分行未入账、状态不一致、前置校验未通过等）"
        verification_text = (verification_items or "").strip() or (
            "1. 核对相关单据/行的状态一致性。\n"
            "2. 复核业务校验规则与触发条件。\n"
            "3. 给出根因与处理建议。"
        )
        extra_note = (note or "").strip()

        standardized_note = (
            f"【问题现象】\n{phenomenon_text}\n\n"
            f"【可能原因】\n{reason_text}\n\n"
            f"【需要验证】\n{verification_text}"
        )
        if extra_note:
            standardized_note = f"{standardized_note}\n\n【补充说明】\n{extra_note}"
        return standardized_note.strip()

    raw_note = (note or "").strip()
    has_issue = "问题现象" in raw_note
    has_reason = "可能原因" in raw_note
    has_verify = "需要验证" in raw_note

    if not raw_note:
        raw_note = content

    standardized_note = raw_note
    if not has_issue:
        standardized_note = f"【问题现象】\n{content}\n\n{standardized_note}".strip()
    if not has_reason:
        standardized_note = (
            f"{standardized_note}\n\n"
            "【可能原因】\n"
            "待排查（如：部分行未入账、状态不一致、前置校验未通过等）"
        )
    if not has_verify:
        standardized_note = (
            f"{standardized_note}\n\n"
            "【需要验证】\n"
            "1. 核对相关单据/行的状态一致性。\n"
            "2. 复核业务校验规则与触发条件。\n"
            "3. 给出根因与处理建议。"
        )

    return standardized_note.strip()


def _normalize_dev_days(dev_days: Optional[float]) -> tuple[str, Optional[str]]:
    """开发人天默认值处理：未传时默认1，非法或非正数回退为1并返回警告。"""
    if dev_days is None:
        return "1", None

    try:
        value = float(dev_days)
    except (TypeError, ValueError):
        return "1", f"dev_days={dev_days} 非法，已强制回退为1"

    if value <= 0:
        return "1", f"dev_days={dev_days} <= 0，已强制回退为1"

    if value.is_integer():
        return str(int(value)), None
    return str(value), None


def _get_project_config(client: httpx.Client, project_id: str) -> dict:
    """
    获取项目配置（tasklist、taskflow、scenariofieldconfig），带缓存。
    创建任务时需要用到这些配置。
    """
    now = time.time()
    if project_id in _project_config_cache:
        if now - _project_config_cache_time.get(project_id, 0) < CACHE_TTL:
            log.info("使用缓存的项目配置（project=%s）", project_id)
            return _project_config_cache[project_id]
        else:
            log.info("项目配置缓存已过期（project=%s），重新获取", project_id)
            del _project_config_cache[project_id]

    log.info("正在查询项目配置（project=%s）...", project_id)
    config = {}

    # 1. 获取 tasklist
    resp = client.get("/api/tasklists", params={"_projectId": project_id})
    resp.raise_for_status()
    tasklists = resp.json()
    if tasklists:
        config["_tasklistId"] = tasklists[0].get("_id")
    log.info("  tasklist: %s", config.get("_tasklistId"))

    # 2. 获取 scenariofieldconfig（字段配置 + stageId）
    resp = client.get(f"/api/v2/projects/{project_id}/scenariofieldconfigs")
    resp.raise_for_status()
    scenario_data = resp.json()
    scenarios = (
        scenario_data
        if isinstance(scenario_data, list)
        else scenario_data.get("result", [])
    )
    if scenarios:
        scenario = scenarios[0]
        config["_scenariofieldconfigId"] = scenario.get("_id")

        # 提取 taskflow ID
        taskflow_id = scenario.get("_taskflowId")
        if taskflow_id:
            config["_taskflowId"] = taskflow_id

        # 提取字段列表（用于创建时填必填字段）
        fields = scenario.get("scenariofields", [])
        config["fields"] = fields
        config["customFields"] = [
            f for f in fields if f.get("fieldType") == "customfield"
        ]
    log.info("  scenariofieldconfig: %s", config.get("_scenariofieldconfigId"))

    # 3. 获取默认 stageId（从现有任务中取，或从 taskflow 中取）
    if config.get("_taskflowId"):
        resp = client.get(f"/api/taskflows/{config['_taskflowId']}")
        resp.raise_for_status()
        taskflow = resp.json()
        statuses = taskflow.get("taskflowstatuses", [])
        if statuses:
            config["_defaultStageId"] = statuses[0].get("_id")
            config["taskflowStatuses"] = [
                {"_id": s.get("_id"), "name": s.get("name"), "kind": s.get("kind")}
                for s in statuses
            ]
        log.info(
            "  taskflow: %s, defaultStage: %s",
            config.get("_taskflowId"),
            config.get("_defaultStageId"),
        )

    # 如果没有从 taskflow 获取到 stageId，从已有任务中获取
    if not config.get("_defaultStageId") or not config.get("_defaultTaskflowstatusId"):
        resp = client.get(
            "/api/v2/tasks",
            params={
                "_projectId": project_id,
                "isDone": "false",
                "pageSize": "1",
            },
        )
        if resp.status_code == 200:
            tasks_data = resp.json()
            tasks = (
                tasks_data
                if isinstance(tasks_data, list)
                else tasks_data.get("result", [])
            )
            if tasks:
                if not config.get("_defaultStageId"):
                    config["_defaultStageId"] = tasks[0].get("_stageId")
                if not config.get("_defaultTaskflowstatusId"):
                    config["_defaultTaskflowstatusId"] = tasks[0].get(
                        "_taskflowstatusId"
                    )
        log.info(
            "  from existing task: stageId=%s, taskflowstatusId=%s",
            config.get("_defaultStageId"),
            config.get("_defaultTaskflowstatusId"),
        )

    _project_config_cache[project_id] = config
    _project_config_cache_time[project_id] = time.time()
    return config


def _get_login_token(client: httpx.Client) -> tuple[str, str]:
    """
    从登录页面 HTML 中提取 token 和 client_id。
    token 和 client_id 存储在 <script id="secrets"> 标签的 data 属性中。
    """
    log.info("正在获取登录页面 token...")
    resp = client.get("/login?enforceLogin=1")
    resp.raise_for_status()
    html = resp.text

    # 提取 <script id="secrets" data-clientid="..." data-clienttoken="...">
    client_id_match = re.search(r'data-clientid="([^"]+)"', html)
    token_match = re.search(r'data-clienttoken="([^"]+)"', html)

    if not client_id_match or not token_match:
        raise RuntimeError("无法从登录页面提取 token，页面结构可能已变更")

    client_id = client_id_match.group(1)
    token = token_match.group(1)
    log.info("成功获取 token（client_id=%s）", client_id)
    return token, client_id


# --------------- 工具实现 ---------------


def _do_login(email: str, password: str) -> str:
    """使用邮箱和密码登录，供工具和自动登录共用。"""
    global _logged_in_user
    client = _get_client()

    try:
        token, client_id = _get_login_token(client)
        log.info("正在登录（email=%s）...", email)
        resp = client.post(
            "/api/login/email",
            data={
                "phone": "",
                "email": email,
                "password": password,
                "next_url": f"{BASE_URL}/projects",
                "response_type": "session",
                "token": token,
                "client_id": client_id,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
            },
        )
        if resp.status_code != 200:
            try:
                error_message = resp.json().get("message", resp.text)
            except ValueError:
                error_message = resp.text
            return f"登录失败（状态码 {resp.status_code}）：{error_message}"

        user_resp = client.get("/api/users/me")
        if user_resp.status_code != 200:
            return "登录请求返回200但无法获取用户信息，可能 Cookie 未正确设置"

        user_info = user_resp.json()
        _logged_in_user = user_info
        log.info("登录成功：%s（%s）", user_info.get("name"), user_info.get("_id"))
        return json.dumps(
            {
                "status": "success",
                "userId": user_info.get("_id"),
                "name": user_info.get("name"),
                "email": user_info.get("email"),
                "joinedProjectsCount": user_info.get("joinedProjectsCount"),
                "source": "password",
            },
            ensure_ascii=False,
        )
    except httpx.HTTPError as error:
        log.error("登录HTTP错误: %s", error)
        return f"登录失败（网络错误）：{error}"
    except Exception as error:
        log.error("登录异常: %s", error)
        return f"登录失败：{error}"


def _do_cookie_login(cookie: str) -> str:
    """使用已有的 Cookie 登录（推荐持久化方式）"""
    global _logged_in_user
    client = _get_client()

    try:
        # 支持浏览器复制的 Cookie 请求头，空片段和 Cookie 属性会被忽略。
        for item in cookie.split(";"):
            if "=" not in item:
                continue
            name, value = item.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name and name.lower() not in {"path", "domain", "expires", "max-age", "samesite"}:
                client.cookies.set(name, value, domain=httpx.URL(BASE_URL).host, path="/")

        log.info("正在使用 Cookie 登录...")

        # 验证登录状态
        user_resp = client.get("/api/users/me")
        if user_resp.status_code != 200:
            return "Cookie 登录失败：无法获取用户信息"

        user_info = user_resp.json()
        _logged_in_user = user_info
        log.info("Cookie 登录成功：%s（%s）", user_info.get("name"), user_info.get("_id"))

        return json.dumps(
            {
                "status": "success",
                "userId": user_info.get("_id"),
                "name": user_info.get("name"),
                "email": user_info.get("email"),
                "joinedProjectsCount": user_info.get("joinedProjectsCount"),
                "source": "cookie",
            },
            ensure_ascii=False,
        )

    except httpx.HTTPError as e:
        log.error("Cookie 登录HTTP错误: %s", e)
        return f"Cookie 登录失败（网络错误）：{e}"
    except Exception as e:
        log.error("Cookie 登录异常: %s", e)
        return f"Cookie 登录失败：{e}"


@mcp.tool()
def login(
    email: str = "",
    password: str = "",
    cookie: str = "",
) -> str:
    """
    登录 Teambition 私有化部署实例。

    支持两种方式：
    1. email + password（经典方式）
    2. 已有的 Cookie（推荐用于持久化 Session，无需每次输入密码）

    Args:
        email: 登录邮箱或手机号（可选）
        password: 登录密码（可选）
        cookie: 有效的 Cookie 字符串（如 "JSESSIONID=xxx; csrftoken=yyy"），优先使用
                （如果提供 cookie，将跳过密码登录流程）

    Returns:
        登录结果，包含用户名和用户ID
    """
    actual_email = email or os.getenv("TB_EMAIL", "")
    actual_password = password or os.getenv("TB_PASSWORD", "")

    if cookie.strip():
        return _do_cookie_login(cookie.strip())
    elif actual_email and actual_password:
        return _do_login(actual_email, actual_password)
    else:
        return json.dumps(
            {
                "status": "error",
                "message": "请提供登录凭据。支持两种方式："
                           "1. email + password\n"
                           "2. cookie 字符串（推荐）",
            },
            ensure_ascii=False,
        )


@mcp.tool()
def list_projects(page_size: int = 50, fetch_all: bool = True) -> str:
    """
    查询当前用户参与的项目列表。

    Args:
        page_size: 每页数量，默认50
        fetch_all: 是否获取全部项目（自动分页），默认True

    Returns:
        项目列表JSON，包含项目ID、名称、成员数等
    """
    _ensure_logged_in()
    client = _get_client()
    all_projects = []
    next_page_token = None

    try:
        while True:
            params = {
                "selectBy": "joined",
                "orderBy": "name",
                "pageSize": str(page_size),
                "_organizationId": ORG_ID,
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            log.info("正在查询项目列表（pageToken=%s）...", next_page_token)
            resp = client.get("/api/v2/projects", params=params)
            resp.raise_for_status()
            data = resp.json()

            projects = data.get("result", [])
            for p in projects:
                all_projects.append(
                    {
                        "_id": p.get("_id"),
                        "name": p.get("name"),
                        "membersCount": p.get("membersCount"),
                        "tasksCount": p.get("tasksCount"),
                        "created": p.get("created"),
                        "isArchived": p.get("isArchived", False),
                    }
                )

            next_page_token = data.get("nextPageToken")
            if not fetch_all or not next_page_token:
                break

        log.info("查询到 %d 个项目", len(all_projects))
        return json.dumps(
            {
                "status": "success",
                "count": len(all_projects),
                "projects": all_projects,
            },
            ensure_ascii=False,
        )

    except httpx.HTTPError as e:
        log.error("查询项目HTTP错误: %s", e)
        return f"查询项目失败（网络错误）：{e}"
    except Exception as e:
        log.error("查询项目异常: %s", e)
        return f"查询项目失败：{e}"


@mcp.tool()
def list_tasks(
    project_id: str,
    page_size: int = 30,
    is_done: bool = False,
    keyword: Optional[str] = None,
) -> str:
    """
    查询指定项目下的任务/需求列表。

    Args:
        project_id: 项目ID
        page_size: 每页数量，默认30
        is_done: 是否查询已完成任务，默认False（查未完成）
        keyword: 搜索关键词，可选

    Returns:
        任务列表JSON，包含任务ID、标题、状态、执行者等
    """
    project_error = _validate_project_required(project_id, "查询任务")
    if project_error:
        return project_error

    _ensure_logged_in()
    client = _get_client()

    try:
        params = {
            "_projectId": project_id,
            "isDone": str(is_done).lower(),
            "pageSize": str(page_size),
        }
        if keyword:
            params["q"] = keyword

        log.info("正在查询任务列表（project=%s, keyword=%s）...", project_id, keyword)
        resp = client.get("/api/v2/tasks", params=params)
        resp.raise_for_status()
        data = resp.json()

        tasks = data if isinstance(data, list) else data.get("result", [])
        task_list = []
        for t in tasks:
            task_list.append(
                {
                    "_id": t.get("_id"),
                    "content": t.get("content"),
                    "uniqueId": t.get("uniqueId"),
                    "priority": t.get("priority"),
                    "isDone": t.get("isDone"),
                    "created": t.get("created"),
                    "_executorId": t.get("_executorId"),
                    "_creatorId": t.get("_creatorId"),
                    "stageId": t.get("_stageId"),
                }
            )

        log.info("查询到 %d 个任务", len(task_list))
        return json.dumps(
            {
                "status": "success",
                "count": len(task_list),
                "tasks": task_list,
            },
            ensure_ascii=False,
        )

    except httpx.HTTPError as e:
        log.error("查询任务HTTP错误: %s", e)
        return f"查询任务失败（网络错误）：{e}"
    except Exception as e:
        log.error("查询任务异常: %s", e)
        return f"查询任务失败：{e}"


@mcp.tool()
def create_task(
    project_id: str,
    content: str,
    executor_id: Optional[str] = None,
    note: Optional[str] = None,
    priority: int = 0,
    involver_ids: Optional[str] = None,
    dev_days: float | None = None,
    issue_phenomenon: Optional[str] = None,
    possible_reason: Optional[str] = None,
    verification_items: Optional[str] = None,
) -> str:
    """
    在指定项目下创建新任务/需求。
    创建后会自动将指定的参与者（如提出者）添加为任务参与者。

    Args:
        project_id: 项目ID
        content: 任务标题
        executor_id: 执行者用户ID，可选（未传或空白时默认当前登录用户）
        note: 任务描述/备注，可选。会自动补齐“问题现象/可能原因/需要验证”三段结构。
        priority: 优先级(0=普通,1=紧急,2=非常紧急)，默认0
        involver_ids: 参与者用户ID，多个用逗号分隔（如提出者ID），可选。未传时按项目默认提出人自动添加参与者。
        dev_days: 开发人天，可选。不传时默认1。
        issue_phenomenon: 模板化备注参数-问题现象，可选。
        possible_reason: 模板化备注参数-可能原因，可选。
        verification_items: 模板化备注参数-需要验证，可选（支持多行文本）。

    Returns:
        创建结果JSON，包含任务ID和编号
    """
    project_error = _validate_project_required(project_id, "创建任务")
    if project_error:
        return project_error

    _ensure_logged_in()
    client = _get_client()

    try:
        # Step 1: 获取项目配置
        config = _get_project_config(client, project_id)

        if not config.get("_tasklistId"):
            return "创建失败：无法获取项目的 tasklistId"

        # Step 2: 构造请求体
        standardized_note = _build_standard_task_note(
            content,
            note,
            issue_phenomenon=issue_phenomenon,
            possible_reason=possible_reason,
            verification_items=verification_items,
        )
        resolved_dev_days, dev_days_warning = _normalize_dev_days(dev_days)
        dev_days_field_id = _find_custom_field_id_by_name(client, config, "开发人天")
        log.info(
            "创建任务备注与开发人天解析（dev_days_input=%s, dev_days_resolved=%s, dev_days_field=%s）",
            dev_days,
            resolved_dev_days,
            dev_days_field_id,
        )

        task_data = {
            "content": content,
            "_projectId": project_id,
            "_tasklistId": config["_tasklistId"],
            "priority": priority,
            "note": standardized_note,
        }

        # 修改说明:
        # v1.2 2026-04-08 未指定提出人时，按项目默认提出人回填，并同步到参与者
        normalized_involver_ids = []
        if involver_ids:
            normalized_involver_ids = [
                uid.strip() for uid in involver_ids.split(",") if uid.strip()
            ]

        default_proposer = _get_default_proposer_config(client, project_id)
        use_project_default_proposer = (
            not normalized_involver_ids and default_proposer is not None
        )
        if use_project_default_proposer:
            default_proposer = _resolve_default_proposer(
                client,
                project_id,
                config,
                default_proposer,
            )
        log.info(
            "创建任务提出人解析（project=%s, has_involver_ids=%s, use_default=%s）",
            project_id,
            bool(normalized_involver_ids),
            use_project_default_proposer,
        )

        # 修改说明:
        # v1.1 2026-04-08 未传或空白 executor_id 时，默认使用当前登录用户
        normalized_executor_id = (executor_id or "").strip()
        configured_executor_name = ""
        configured_executor_id = ""
        if use_project_default_proposer:
            configured_executor_name = (
                default_proposer.get("executorname") or ""
            ).strip()
            if configured_executor_name not in ("", "登录用户", "当前登录用户", "current_user"):
                configured_executor_id = (
                    default_proposer.get("executor_user_id") or ""
                ).strip()

        current_user_id = (_logged_in_user or {}).get("_id")
        log.info(
            "创建任务执行者解析（executor_id=%s, configured_executor=%s, current_user_id=%s）",
            normalized_executor_id or "<empty>",
            configured_executor_name or "<none>",
            current_user_id,
        )

        # 设置执行者
        effective_executor_name = ""
        if normalized_executor_id:
            task_data["_executorId"] = normalized_executor_id
            if normalized_executor_id == current_user_id:
                effective_executor_name = ((_logged_in_user or {}).get("name") or "").strip()
        elif configured_executor_id:
            task_data["_executorId"] = configured_executor_id
            log.info(
                "未指定执行者，使用配置执行者: %s（%s）",
                configured_executor_name,
                configured_executor_id,
            )
            effective_executor_name = configured_executor_name
        elif current_user_id:
            task_data["_executorId"] = current_user_id
            log.info("未指定执行者，默认使用当前登录用户: %s", current_user_id)
            effective_executor_name = ((_logged_in_user or {}).get("name") or "").strip()
        else:
            return "创建失败：未指定执行者且无法获取当前登录用户"

        if not effective_executor_name:
            effective_executor_name = configured_executor_name or ((_logged_in_user or {}).get("name") or "").strip()

        # 设置 scenariofieldconfigId（必填）
        if config.get("_scenariofieldconfigId"):
            task_data["_scenariofieldconfigId"] = config["_scenariofieldconfigId"]

        # 设置工作流 taskflowstatusId（必填）
        preferred_taskflowstatus_id = ""
        if config.get("_defaultTaskflowstatusId"):
            preferred_taskflowstatus_id = config["_defaultTaskflowstatusId"]
        elif config.get("_defaultStageId"):
            preferred_taskflowstatus_id = config["_defaultStageId"]

        if preferred_taskflowstatus_id:
            task_data["_taskflowstatusId"] = preferred_taskflowstatus_id

        log.info("正在创建任务（project=%s, content=%s）...", project_id, content)
        resp = client.post(
            "/api/v2/tasks",
            json=task_data,
            headers={
                "Content-Type": "application/json",
                "x-request-id": str(uuid.uuid4()),
            },
        )
        # 修改说明:
        # v1.5 2026-04-08 兼容部分项目返回 InvalidTaskflowstatusKind 场景，自动回退 stageId 重试一次
        fallback_stage_id = config.get("_defaultStageId")
        if (
            resp.status_code == 400
            and "InvalidTaskflowstatusKind" in (resp.text or "")
            and fallback_stage_id
            and fallback_stage_id != preferred_taskflowstatus_id
        ):
            log.info(
                "创建任务命中InvalidTaskflowstatusKind，回退stageId重试（project=%s, stageId=%s）",
                project_id,
                fallback_stage_id,
            )
            retry_task_data = dict(task_data)
            retry_task_data["_taskflowstatusId"] = fallback_stage_id
            resp = client.post(
                "/api/v2/tasks",
                json=retry_task_data,
                headers={
                    "Content-Type": "application/json",
                    "x-request-id": str(uuid.uuid4()),
                },
            )

        if resp.status_code not in (200, 201):
            return f"创建失败（状态码 {resp.status_code}）：{resp.text}"

        result = resp.json()
        task_id = result.get("_id")
        log.info("任务创建成功：%s（ID: %s）", result.get("content"), task_id)

        # Step 3: 回填项目默认提出人与规则字段（仅未指定提出人时）
        default_proposer_field_updated = False
        rule_field_updates = []
        rule_field_warnings = []
        if use_project_default_proposer:
            proposer_field_id = default_proposer.get("proposer_custom_field_id")
            proposer_member_id = default_proposer.get("member_id")
            proposer_name = str(default_proposer.get("name") or "").strip()

            if proposer_field_id and proposer_name:
                proposer_meta_resp = _retry_request(
                    lambda: client.get(
                        f"/api/v2/customfields/{proposer_field_id}",
                        headers={"X-Tenant-Id": ORG_ID},
                    )
                )
                proposer_meta = (
                    proposer_meta_resp.json()
                    if proposer_meta_resp.status_code == 200 and isinstance(proposer_meta_resp.json(), dict)
                    else {}
                )
                proposer_field_type = (
                    str(proposer_meta.get("type") or "").strip() or "lookup"
                )

                proposer_value = None
                if proposer_field_type == "lookup":
                    if proposer_member_id:
                        proposer_value = [{"_id": proposer_member_id, "title": proposer_name}]
                elif proposer_field_type == "commongroup":
                    commongroup_id = _resolve_commongroup_id_by_title(
                        client,
                        project_id,
                        proposer_field_id,
                        proposer_name,
                    )
                    if commongroup_id:
                        proposer_value = [{"_id": commongroup_id, "title": proposer_name}]
                elif proposer_field_type == "dropDown":
                    dropdown_id = ""
                    for choice in proposer_meta.get("choices", []) or []:
                        choice_title = str(choice.get("value") or choice.get("title") or "").strip()
                        if choice_title == proposer_name:
                            dropdown_id = str(choice.get("_id") or "").strip()
                            break
                    if dropdown_id:
                        proposer_value = [{"_id": dropdown_id, "title": proposer_name}]
                    else:
                        proposer_value = [{"title": proposer_name}]
                else:
                    proposer_value = [{"title": proposer_name}]

                if proposer_value:
                    resp_proposer = _retry_request(
                        lambda: client.put(
                            f"/api/tasks/{task_id}/customfields",
                            json={
                                "_customfieldId": proposer_field_id,
                                "type": proposer_field_type,
                                "value": proposer_value,
                            },
                            headers={
                                "Content-Type": "application/json",
                                "x-request-id": str(uuid.uuid4()),
                            },
                        )
                    )
                    if resp_proposer.status_code == 200:
                        default_proposer_field_updated = True
                        rule_field_updates.append(
                            {
                                "field": default_proposer.get("proposer_custom_field_name") or "提出人",
                                "type": proposer_field_type,
                                "status": "success",
                            }
                        )
                    else:
                        rule_field_warnings.append(
                            f"提出人字段回填失败: {resp_proposer.status_code}"
                        )
                else:
                    rule_field_warnings.append(
                        f"提出人字段回填失败：字段类型={proposer_field_type}，缺少可用值"
                    )

            rule_map = default_proposer.get("proposer_custom_field_rules") or {}
            if isinstance(rule_map, dict):
                proposer_name_text = str(default_proposer.get("name") or "").strip()
                executor_name_text = (effective_executor_name or "").strip()

                for field_name, raw_rule_value in rule_map.items():
                    normalized_field_name = str(field_name or "").strip()
                    if not normalized_field_name:
                        continue
                    if normalized_field_name in ("提出人", "参与者"):
                        continue

                    resolved_rule_value = _resolve_rule_text_value(
                        str(raw_rule_value or ""),
                        proposer_name_text,
                        executor_name_text,
                        standardized_note,
                    )

                    if normalized_field_name == "备注":
                        rule_field_updates.append({"field": "备注", "type": "note", "status": "success"})
                        continue

                    if normalized_field_name == "开发人天":
                        continue

                    if normalized_field_name == "迭代":
                        sprint_id = _resolve_sprint_id_by_name(client, project_id, resolved_rule_value)
                        if not sprint_id:
                            rule_field_warnings.append(
                                f"迭代字段回填失败：未匹配到迭代[{resolved_rule_value}]"
                            )
                            continue

                        resp_sprint = _retry_request(
                            lambda sprint_id=sprint_id: client.put(
                                # v1.7 2026-04-08 迭代回填改为 v2 任务接口，确保 _sprintId 生效
                                f"/api/v2/tasks/{task_id}",
                                json={"_sprintId": sprint_id},
                                headers={
                                    "Content-Type": "application/json",
                                    "x-request-id": str(uuid.uuid4()),
                                },
                            )
                        )
                        if resp_sprint.status_code in (200, 204):
                            rule_field_updates.append(
                                {"field": "迭代", "type": "sprint", "status": "success", "value": resolved_rule_value}
                            )
                        else:
                            rule_field_warnings.append(
                                f"迭代字段回填失败: {resp_sprint.status_code}"
                            )
                        continue

                    custom_field_id = _find_custom_field_id_by_name(client, config, normalized_field_name)
                    if not custom_field_id:
                        rule_field_warnings.append(
                            f"字段[{normalized_field_name}]未找到，跳过回填"
                        )
                        continue

                    field_meta_resp = _retry_request(
                        lambda custom_field_id=custom_field_id: client.get(
                            f"/api/v2/customfields/{custom_field_id}",
                            headers={"X-Tenant-Id": ORG_ID},
                        )
                    )
                    field_meta = (
                        field_meta_resp.json()
                        if field_meta_resp.status_code == 200 and isinstance(field_meta_resp.json(), dict)
                        else {}
                    )
                    field_type = (
                        str(field_meta.get("type") or "").strip()
                        or str((_get_custom_field_meta(client, custom_field_id) or {}).get("type") or "").strip()
                        or "text"
                    )

                    custom_field_value = None
                    if field_type == "lookup":
                        member_info = _search_member_by_name(client, resolved_rule_value)
                        member_id = member_info.get("member_id")
                        if member_id:
                            custom_field_value = [{"_id": member_id, "title": resolved_rule_value}]
                    elif field_type == "commongroup":
                        commongroup_id = _resolve_commongroup_id_by_title(
                            client,
                            project_id,
                            custom_field_id,
                            resolved_rule_value,
                        )
                        if commongroup_id:
                            custom_field_value = [{"_id": commongroup_id, "title": resolved_rule_value}]
                    elif field_type == "dropDown":
                        dropdown_id = ""
                        for choice in field_meta.get("choices", []) or []:
                            choice_title = str(choice.get("value") or choice.get("title") or "").strip()
                            if choice_title == resolved_rule_value:
                                dropdown_id = str(choice.get("_id") or "").strip()
                                break
                        if dropdown_id:
                            custom_field_value = [{"_id": dropdown_id, "title": resolved_rule_value}]
                        else:
                            custom_field_value = [{"title": resolved_rule_value}]
                    else:
                        custom_field_value = [{"title": resolved_rule_value}]

                    if not custom_field_value:
                        rule_field_warnings.append(
                            f"字段[{normalized_field_name}]回填失败：无法解析字段值"
                        )
                        continue

                    resp_rule_field = _retry_request(
                        lambda custom_field_id=custom_field_id, field_type=field_type, custom_field_value=custom_field_value: client.put(
                            f"/api/tasks/{task_id}/customfields",
                            json={
                                "_customfieldId": custom_field_id,
                                "type": field_type,
                                "value": custom_field_value,
                            },
                            headers={
                                "Content-Type": "application/json",
                                "x-request-id": str(uuid.uuid4()),
                            },
                        )
                    )
                    if resp_rule_field.status_code == 200:
                        rule_field_updates.append(
                            {
                                "field": normalized_field_name,
                                "type": field_type,
                                "status": "success",
                                "value": resolved_rule_value,
                            }
                        )
                    else:
                        rule_field_warnings.append(
                            f"字段[{normalized_field_name}]回填失败: {resp_rule_field.status_code}"
                        )

        # Step 3.1: 回填开发人天（未传时默认1）
        dev_days_field_updated = False
        if dev_days_field_id:
            log.info(
                "回填开发人天（task=%s, value=%s, field=%s）",
                task_id,
                resolved_dev_days,
                dev_days_field_id,
            )
            resp_dev_days = _retry_request(
                lambda: client.put(
                    f"/api/tasks/{task_id}/customfields",
                    json={
                        "_customfieldId": dev_days_field_id,
                        "type": "number",
                        "value": [{"title": resolved_dev_days}],
                    },
                    headers={
                        "Content-Type": "application/json",
                        "x-request-id": str(uuid.uuid4()),
                    },
                )
            )
            if resp_dev_days.status_code == 200:
                dev_days_field_updated = True
            else:
                log.warning(
                    "开发人天回填失败: %s - %s",
                    resp_dev_days.status_code,
                    resp_dev_days.text[:200],
                )
        else:
            log.info("项目未配置开发人天字段，跳过回填（project=%s）", project_id)

        # Step 4: 自动添加参与者（未指定时默认与提出人一致）
        involvers_result = []
        involver_user_ids = list(normalized_involver_ids)
        if use_project_default_proposer:
            include_proposer = default_proposer.get(
                "default_involver_include_proposer", True
            )
            include_executor = default_proposer.get(
                "default_involver_include_executor", True
            )

            if include_proposer and default_proposer.get("user_id"):
                involver_user_ids.append(default_proposer["user_id"])

            if include_executor and task_data.get("_executorId"):
                involver_user_ids.append(task_data["_executorId"])

        involver_user_ids = list(dict.fromkeys(involver_user_ids))
        if involver_user_ids:
            log.info("正在添加参与者（task=%s, users=%s）...", task_id, involver_user_ids)
            resp_inv = _retry_request(
                lambda: client.put(
                    f"/api/tasks/{task_id}/involveMembers",
                    json={"addInvolvers": involver_user_ids},
                    headers={
                        "Content-Type": "application/json",
                        "x-request-id": str(uuid.uuid4()),
                        "x-timezone": "8",
                    },
                )
            )
            if resp_inv.status_code == 200:
                inv_data = resp_inv.json()
                involvers_result = [
                    {"_id": m.get("_id"), "name": m.get("name")}
                    for m in inv_data.get("involvers", [])
                ]
                log.info("参与者添加成功，当前 %d 人", len(involvers_result))
            else:
                log.warning(
                    "添加参与者失败: %s - %s",
                    resp_inv.status_code,
                    resp_inv.text[:200],
                )

        output = {
            "status": "success",
            "_id": task_id,
            "content": result.get("content"),
            "uniqueId": result.get("uniqueId"),
            "_projectId": result.get("_projectId"),
            "created": result.get("created"),
        }
        if use_project_default_proposer:
            output["defaultProposer"] = {
                "name": default_proposer.get("name"),
                "memberId": default_proposer.get("member_id"),
                "userId": default_proposer.get("user_id"),
            }
            output["proposerCustomFieldUpdated"] = default_proposer_field_updated
        output["devDays"] = resolved_dev_days
        output["devDaysFieldUpdated"] = dev_days_field_updated
        warnings = []
        if dev_days_warning:
            warnings.append(dev_days_warning)
        warnings.extend(rule_field_warnings)
        if warnings:
            output["warnings"] = warnings
        if rule_field_updates:
            output["ruleFieldUpdates"] = rule_field_updates
        if involvers_result:
            output["involvers"] = involvers_result

        return json.dumps(output, ensure_ascii=False)

    except httpx.HTTPError as e:
        log.error("创建任务HTTP错误: %s", e)
        return f"创建任务失败（网络错误）：{e}"
    except Exception as e:
        log.error("创建任务异常: %s", e)
        return f"创建任务失败：{e}"


@mcp.tool()
def update_task(
    task_id: str,
    project_id: str = "",
    content: str | None = None,
    note: str | None = None,
    executor_id: str | None = None,
    priority: int | None = None,
    custom_field_id: str | None = None,
    custom_field_type: str | None = None,
    custom_field_value: str | None = None,
) -> str:
    """
    编辑已有任务的属性。支持修改基础字段和自定义字段。

    Args:
        task_id: 任务ID
        project_id: 所属项目ID（必填）
        content: 新的任务标题，可选
        note: 新的任务描述，可选
        executor_id: 新的执行者用户ID，可选
        priority: 新的优先级(0/1/2)，可选
        custom_field_id: 要修改的自定义字段ID，可选（与custom_field_value配合使用）
        custom_field_type: 自定义字段类型（如 text, number, date, dropDown, lookup），可选
        custom_field_value: 自定义字段的新值（JSON字符串格式），可选

    Returns:
        更新结果JSON
    """
    project_error = _validate_project_required(project_id, "更新任务")
    if project_error:
        return project_error

    _ensure_logged_in()
    client = _get_client()

    try:
        results = []

        # 修改基础字段
        basic_update = {}
        if content is not None:
            basic_update["content"] = content
        if note is not None:
            basic_update["note"] = note
        if executor_id is not None:
            basic_update["_executorId"] = executor_id
        if priority is not None:
            basic_update["priority"] = priority

        if basic_update:
            log.info(
                "正在更新任务基础字段（task=%s）: %s",
                task_id,
                list(basic_update.keys()),
            )
            resp = client.put(
                f"/api/tasks/{task_id}",
                json=basic_update,
                headers={
                    "Content-Type": "application/json",
                    "x-request-id": str(uuid.uuid4()),
                },
            )
            if resp.status_code != 200:
                return f"更新基础字段失败（状态码 {resp.status_code}）：{resp.text}"
            results.append(
                {
                    "type": "basic",
                    "status": "success",
                    "fields": list(basic_update.keys()),
                }
            )

        # 修改自定义字段
        if custom_field_id and custom_field_value is not None:
            # 尝试将 value 解析为 JSON
            try:
                parsed_value = json.loads(custom_field_value)
            except (json.JSONDecodeError, TypeError):
                parsed_value = custom_field_value

            cf_data = {
                "_customfieldId": custom_field_id,
                "value": parsed_value,
            }
            if custom_field_type:
                cf_data["type"] = custom_field_type

            log.info(
                "正在更新自定义字段（task=%s, field=%s）...", task_id, custom_field_id
            )
            resp = client.put(
                f"/api/tasks/{task_id}/customfields",
                json=cf_data,
                headers={
                    "Content-Type": "application/json",
                    "x-request-id": str(uuid.uuid4()),
                },
            )
            if resp.status_code != 200:
                return f"更新自定义字段失败（状态码 {resp.status_code}）：{resp.text}"
            results.append(
                {"type": "customfield", "status": "success", "fieldId": custom_field_id}
            )

        if not results:
            return "未指定任何要修改的字段"

        log.info("任务更新成功：%s", task_id)
        return json.dumps(
            {
                "status": "success",
                "taskId": task_id,
                "_projectId": project_id,
                "updates": results,
            },
            ensure_ascii=False,
        )

    except httpx.HTTPError as e:
        log.error("更新任务HTTP错误: %s", e)
        return f"更新任务失败（网络错误）：{e}"
    except Exception as e:
        log.error("更新任务异常: %s", e)
        return f"更新任务失败：{e}"


@mcp.tool()
def delete_task(task_id: str, project_id: str = "") -> str:
    """
    将任务移到回收站（软删除）。

    Args:
        task_id: 任务ID
        project_id: 所属项目ID（必填）

    Returns:
        删除结果JSON
    """
    project_error = _validate_project_required(project_id, "删除任务")
    if project_error:
        return project_error

    _ensure_logged_in()
    client = _get_client()

    try:
        log.info("正在删除任务（task=%s）...", task_id)
        resp = client.post(
            f"/api/tasks/{task_id}/archive",
            json={},
            headers={
                "Content-Type": "application/json",
                "x-request-id": str(uuid.uuid4()),
            },
        )

        if resp.status_code != 200:
            return f"删除失败（状态码 {resp.status_code}）：{resp.text}"

        result = resp.json()
        log.info("任务删除成功：%s（isArchived=%s）", task_id, result.get("isArchived"))

        return json.dumps(
            {
                "status": "success",
                "taskId": task_id,
                "_projectId": project_id,
                "isArchived": result.get("isArchived"),
                "updated": result.get("updated"),
            },
            ensure_ascii=False,
        )

    except httpx.HTTPError as e:
        log.error("删除任务HTTP错误: %s", e)
        return f"删除任务失败（网络错误）：{e}"
    except Exception as e:
        log.error("删除任务异常: %s", e)
        return f"删除任务失败：{e}"


@mcp.tool()
def add_involvers(task_id: str, user_ids: str, project_id: str = "") -> str:
    """
    为任务添加参与者。

    Args:
        task_id: 任务ID
        user_ids: 要添加的参与者用户ID，多个用逗号分隔（如 "id1,id2"）
        project_id: 所属项目ID（必填）

    Returns:
        添加结果JSON，包含当前参与者列表
    """
    project_error = _validate_project_required(project_id, "添加参与者")
    if project_error:
        return project_error

    _ensure_logged_in()
    client = _get_client()

    try:
        ids = [uid.strip() for uid in user_ids.split(",") if uid.strip()]
        if not ids:
            return "错误：至少需要提供一个用户ID"

        log.info("正在添加参与者（task=%s, users=%s）...", task_id, ids)
        resp = _retry_request(
            lambda: client.put(
                f"/api/tasks/{task_id}/involveMembers",
                json={"addInvolvers": ids},
                headers={
                    "Content-Type": "application/json",
                    "x-request-id": str(uuid.uuid4()),
                    "x-timezone": "8",
                },
            )
        )

        if resp.status_code != 200:
            return f"添加参与者失败（状态码 {resp.status_code}）：{resp.text}"

        result = resp.json()
        involvers = result.get("involvers", [])
        log.info("参与者添加成功：%s，当前参与者 %d 人", task_id, len(involvers))

        return json.dumps(
            {
                "status": "success",
                "taskId": task_id,
                "_projectId": project_id,
                "involveMembers": result.get("involveMembers", []),
                "involvers": [
                    {
                        "_id": m.get("_id"),
                        "name": m.get("name"),
                        "email": m.get("email"),
                    }
                    for m in involvers
                ],
                "updated": result.get("updated"),
            },
            ensure_ascii=False,
        )

    except httpx.HTTPError as e:
        log.error("添加参与者HTTP错误: %s", e)
        return f"添加参与者失败（网络错误）：{e}"
    except Exception as e:
        log.error("添加参与者异常: %s", e)
        return f"添加参与者失败：{e}"


# --------------- 入口 ---------------
if __name__ == "__main__":
    mcp.run()
