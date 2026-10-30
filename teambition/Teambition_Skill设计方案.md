# Teambition Skill 设计方案

## 1. 概述

### 1.1 目标

开发一个基于 MCP（Model Context Protocol）的 Teambition Skill，使 AI Agent 能够直接操作 Teambition 私有化部署实例，实现项目管理自动化。

### 1.2 核心功能

| 序号 | 功能 | 对应API | 优先级 |
|------|------|---------|--------|
| 1 | 用户登录 | `POST /api/login/email` | P0 |
| 2 | 查询项目列表 | `GET /api/v2/projects?selectBy=joined` | P0 |
| 3 | 查询指定项目下的任务 | `GET /api/v2/tasks?_projectId={id}` | P0 |
| 4 | 创建任务 | `POST /api/v2/tasks` | P0 |
| 5 | 编辑任务 | `PUT /api/tasks/{taskId}/customfields` | P0 |
| 6 | 删除任务 | `POST /api/tasks/{taskId}/archive` | P1 |
| 7 | 添加参与者 | `PUT /api/tasks/{taskId}/involveMembers` | P1 |

### 1.3 技术选型

| 项 | 选择 | 理由 |
|----|------|------|
| 协议 | MCP (Model Context Protocol) | 与 Claude/Copilot Agent 无缝集成 |
| 语言 | Python 3.10+ | FastMCP 生态成熟，开发效率高 |
| 框架 | FastMCP | Python MCP 官方推荐框架 |
| HTTP客户端 | httpx | 异步支持好，session 管理完善 |
| 部署 | 本地 stdio 模式 | 私有化部署，无需公网暴露 |

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────┐
│           AI Agent (Claude/Copilot)      │
│                                         │
│  用户指令 → Skill SKILL.md → MCP Tool   │
└────────────────┬────────────────────────┘
                 │ MCP Protocol (stdio)
                 ▼
┌─────────────────────────────────────────┐
│         Teambition MCP Server           │
│                                         │
│  ┌───────────┐  ┌───────────────────┐   │
│  │  Session   │  │   Tool Registry   │   │
│  │  Manager   │  │                   │   │
│  │ (Cookie/   │  │  - login          │   │
│  │  Token)    │  │  - list_projects  │   │
│  │            │  │  - list_tasks     │   │
│  └─────┬─────┘  │  - create_task    │   │
│        │        │  - update_task    │   │
│        │        │  - delete_task    │   │
│        │        └───────────────────┘   │
│        ▼                                │
│  ┌───────────────────────────────────┐  │
│  │      HTTP Client (httpx)          │  │
│  │   Session With Cookie Jar         │  │
│  └─────────────┬─────────────────────┘  │
└────────────────┼────────────────────────┘
                 │ HTTPS
                 ▼
┌─────────────────────────────────────────┐
│   Teambition Private Deployment         │
│   https://i2m.gdalpha.com:4431          │
└─────────────────────────────────────────┘
```

### 2.2 目录结构

```
teambition/
├── SKILL.md                          # Skill 入口文件（必需）
├── scripts/
│   └── teambition_mcp_server.py      # MCP Server 主程序
├── references/
│   ├── api_docs.md                   # API 接口详细文档（已有内容的精简版）
│   └── project_config.md             # 项目配置参考（自定义字段映射等）
└── teambition接口文档.md              # 原始API文档（保留作参考）
```

### 2.3 Session 管理方案

```
登录流程:
1. Agent 调用 login 工具 → MCP Server 收到请求
2. MCP Server 先访问 GET /login 页面，解析 HTML 获取 token 和 client_id
3. MCP Server 用 email + password + token + client_id 调用 POST /api/login/email
4. httpx.Client 的 CookieJar 自动保存 httpOnly Cookie
5. 后续所有请求自动携带 Cookie（无需手动管理）

Session 保持:
- httpx.Client 使用持久化 Session
- Cookie 过期后自动重新登录
- 登录状态通过 GET /api/users/me 检测
```

---

## 3. 工具详细设计

### 3.0 统一约束（项目必填）

- 除 `list_projects` 与 `login` 外，所有任务相关工具调用都必须明确传入 `project_id`。
- 适用工具：`list_tasks`、`create_task`、`update_task`、`delete_task`、`add_involvers`。
- 若缺失 `project_id`，MCP 层直接拒绝执行并返回错误，防止跨项目误操作。

### 3.1 login - 用户登录

```python
@mcp.tool()
async def login(email: str, password: str) -> str:
    """
    登录 Teambition 私有化部署实例。
    
    Args:
        email: 登录邮箱或手机号
        password: 登录密码
    
    Returns:
        登录结果，包含用户名和用户ID
    """
```

**实现要点**：
1. 先 GET 登录页面，用正则提取 `token` 和 `client_id`
2. 构造 form-urlencoded 请求体
3. POST `/api/login/email`
4. 验证返回状态码
5. 调用 `/api/users/me` 确认登录成功，返回用户信息

**Token 提取方案**：
```python
# 登录页面的 HTML 中，表单 hidden input 或 JS 变量中包含 token
# 方案A：从页面 HTML 中正则提取
import re
html = response.text
token_match = re.search(r'"token"\s*:\s*"([^"]+)"', html)
client_id_match = re.search(r'"client_id"\s*:\s*"([^"]+)"', html)

# 方案B：从页面 <script> 标签中提取
# 方案C：固定 client_id（已知固定值），仅提取 token
```

### 3.2 list_projects - 查询项目列表

```python
@mcp.tool()
async def list_projects(
    page_size: int = 30,
    select_by: str = "joined"
) -> str:
    """
    查询当前用户参与的项目列表。
    
    Args:
        page_size: 每页数量，默认30
        select_by: 筛选方式，默认 "joined"（参与的项目）
    
    Returns:
        项目列表，包含项目ID、名称、创建时间等
    """
```

**实现要点**：
1. 自动处理分页（nextPageToken）
2. 返回精简的项目信息列表（ID、名称、成员数）
3. 支持一次性获取全部项目

### 3.3 list_tasks - 查询任务列表

```python
@mcp.tool()
async def list_tasks(
    project_id: str,
    page_size: int = 30,
    is_done: bool = False,
    keyword: str = None
) -> str:
    """
    查询指定项目下的任务列表。
    
    Args:
        project_id: 项目ID
        page_size: 每页数量，默认30
        is_done: 是否只查已完成任务，默认False
        keyword: 搜索关键词，可选
    
    Returns:
        任务列表，包含任务ID、标题、状态、创建人等
    """
```

**实现要点**：
1. 必须先登录
2. 支持分页查询
3. 返回精简的任务信息（ID、标题、前缀编号、状态、执行者）

### 3.4 create_task - 创建任务

```python
@mcp.tool()
async def create_task(
    project_id: str,
    content: str,
    executor_id: str = None,
    note: str = None,
    priority: int = 0,
    involver_ids: str = None,
    dev_days: float = None,
    issue_phenomenon: str = None,
    possible_reason: str = None,
    verification_items: str = None
) -> str:
    """
    在指定项目下创建新任务/需求。
    
    Args:
        project_id: 项目ID
        content: 任务标题
        executor_id: 执行者用户ID，可选
        note: 任务描述，可选
        priority: 优先级(0=普通,1=紧急,2=非常紧急)，默认0
        involver_ids: 参与者用户ID（逗号分隔），可选
        dev_days: 开发人天，可选（不传默认1）
        issue_phenomenon: 模板化备注参数-问题现象，可选
        possible_reason: 模板化备注参数-可能原因，可选
        verification_items: 模板化备注参数-需要验证，可选
    
    Returns:
        创建结果，包含任务ID和前缀编号
    """
```

**实现要点**：
1. 创建前需查询项目配置（tasklist、taskflow、scenariofieldconfig）
2. 自动填充必填的 `_tasklistId` 和 `_stageId`
3. 支持设置自定义字段（如"提出人"、"开发人天"等）
4. 备注支持模板化参数自动组装，最少包含：`问题现象`、`可能原因`、`需要验证`
5. `dev_days` 未传时默认 `1`；非法值（<=0 或非数值）会回退为 `1`
6. 当发生回退时，在返回JSON里写入 `warnings`，便于调用方感知
7. 默认提出人映射支持数组配置（按 `project_name` + `name` + 可选 `executorname`），运行时自动解析 `project_id`、`member_id`、`user_id`、`proposer_custom_field_id`
8. 返回创建的任务ID和编号

**创建流程（7步）**：
```
Step 1: GET /api/tasklists?_projectId={id}         → 获取 _tasklistId
Step 2: GET /api/v2/projects/{id}/scenariofieldconfigs → 获取必填字段和场景配置
Step 3: GET /api/v2/customfields/{fieldId}          → 获取自定义字段选项（按需）
Step 4: GET /api/v2/organizations/{orgId}/members   → 获取成员列表（按需）
Step 5: GET /api/taskflows/{flowId}                 → 获取工作流状态
Step 6: GET /api/v2/tasks?_projectId={id}&pageSize=1 → 获取现有任务的默认状态
Step 7: POST /api/v2/tasks                          → 创建任务
```

### 3.5 update_task - 编辑任务

```python
@mcp.tool()
async def update_task(
    task_id: str,
    project_id: str,
    content: str = None,
    note: str = None,
    executor_id: str = None,
    priority: int = None,
    custom_field_id: str = None,
    custom_field_value: str = None
) -> str:
    """
    编辑已有任务的属性。
    
    Args:
        task_id: 任务ID
        project_id: 所属项目ID（必填）
        content: 新的任务标题，可选
        note: 新的任务描述，可选
        executor_id: 新的执行者ID，可选
        priority: 新的优先级，可选
        custom_field_id: 要修改的自定义字段ID，可选
        custom_field_value: 自定义字段的新值，可选
    
    Returns:
        更新结果
    """
```

**实现要点**：
1. 基础字段修改使用 `PUT /api/tasks/{taskId}`
2. 自定义字段修改使用 `PUT /api/tasks/{taskId}/customfields`
3. 自动判断使用哪个接口

### 3.6 delete_task - 删除任务

```python
@mcp.tool()
async def delete_task(task_id: str, project_id: str) -> str:
    """
    将任务移到回收站（软删除）。
    
    Args:
        task_id: 任务ID
        project_id: 所属项目ID（必填）
    
    Returns:
        删除结果
    """
```

**实现要点**：
1. 调用 `POST /api/tasks/{taskId}/archive`
2. 请求体为空 `{}`
3. 确认 `isArchived: true`

### 3.7 add_involvers - 添加参与者

```python
@mcp.tool()
async def add_involvers(task_id: str, user_ids: str, project_id: str) -> str:
    """
    为任务添加参与者。

    Args:
        task_id: 任务ID
        user_ids: 参与者用户ID（逗号分隔）
        project_id: 所属项目ID（必填）

    Returns:
        添加结果
    """
```

**实现要点**：
1. 调用 `PUT /api/tasks/{taskId}/involveMembers`
2. 请求体为 `{"addInvolvers": ["id1", "id2"]}`
3. 返回最新参与者列表与操作状态

---

## 4. SKILL.md 设计

### 4.1 Frontmatter

```yaml
---
name: teambition
description: >
  Teambition 私有化部署项目管理 MCP 工具。支持登录认证、查询项目列表、
  查询/创建/编辑/删除任务。适用于需要操作 Teambition 进行项目管理、
  任务跟踪的场景。触发条件：用户提到 teambition、任务管理、项目管理、
  创建需求、WDIS、WUFN 等项目前缀。
triggers: [
  "teambition", "任务管理", "项目管理", "创建需求", "创建任务",
  "WDIS", "WUFN", "项目列表", "任务列表"
]
dependencies: python>=3.10, httpx>=0.24.0, mcp>=1.0.0
version: 1.0.0
---
```

### 4.2 Body 核心内容

SKILL.md 正文应包含：
1. **快速开始**：登录 → 查询项目 → 查询任务 → 创建任务 的最简路径
2. **工具总览表**：7个工具的一句话说明
3. **关键配置**：Teambition 服务地址、组织ID
4. **常用项目ID速查**：常用项目的 ID 和前缀编号
5. **指向详细文档的链接**：`references/api_docs.md`

### 4.3 References 文件

- `references/api_docs.md`：从 `teambition接口文档.md` 精简而来，保留 API 请求/响应格式
- `references/project_config.md`：已知项目的配置信息（tasklistId、字段映射等）

---

## 5. 落地步骤

### Phase 1：基础框架搭建（登录 + 查询）

| 步骤 | 任务 | 估计产出 |
|------|------|---------|
| 1.1 | 创建 SKILL.md 文件（frontmatter + 基础说明） | SKILL.md |
| 1.2 | 创建 `scripts/teambition_mcp_server.py` 骨架代码 | Python 文件 |
| 1.3 | 实现 Session 管理器（httpx.AsyncClient + CookieJar） | SessionManager 类 |
| 1.4 | 实现 `login` 工具（含 token 提取） | login 函数 |
| 1.5 | 实现 `list_projects` 工具（含分页） | list_projects 函数 |
| 1.6 | 实现 `list_tasks` 工具 | list_tasks 函数 |
| 1.7 | 本地测试 Phase 1 全部工具 | 测试通过 |

### Phase 2：写入操作（创建 / 编辑 / 删除）

| 步骤 | 任务 | 估计产出 |
|------|------|---------|
| 2.1 | 实现项目配置缓存（tasklist、taskflow、customfields） | ConfigCache 类 |
| 2.2 | 实现 `create_task` 工具（含7步配置查询流程） | create_task 函数 |
| 2.3 | 实现 `update_task` 工具（支持基础字段 + 自定义字段） | update_task 函数 |
| 2.4 | 实现 `delete_task` 工具 | delete_task 函数 |
| 2.5 | 实现 `add_involvers` 工具 | add_involvers 函数 |
| 2.6 | 本地测试 Phase 2 全部工具 | 测试通过 |

### Phase 3：集成测试 + MCP 配置

| 步骤 | 任务 | 估计产出 |
|------|------|---------|
| 3.1 | 编写 references/api_docs.md（精简版接口文档） | Markdown 文件 |
| 3.2 | 编写 references/project_config.md（常用项目配置） | Markdown 文件 |
| 3.3 | 完善 SKILL.md 正文内容 | SKILL.md 更新 |
| 3.4 | 生成 MCP 配置（claude_desktop_config.json 或 settings.json） | 配置文件 |
| 3.5 | 端到端集成测试（Agent → MCP → Teambition） | 测试报告 |
| 3.6 | 修复测试中发现的问题 | Bug fix |

### Phase 4：优化与扩展（可选）

| 步骤 | 任务 |
|------|------|
| 4.1 | 添加项目配置缓存机制（避免重复查询） |
| 4.2 | 添加错误重试机制（网络异常、token过期自动刷新） |
| 4.3 | 支持更多操作（评论、附件、工作流状态变更） |
| 4.4 | 支持批量操作（批量创建/编辑任务） |

---

## 6. 关键技术细节

### 6.1 Token 提取策略

登录页面 token 是 JWT 格式，嵌入在页面中。提取策略：

```python
async def get_login_token(client: httpx.AsyncClient) -> tuple[str, str]:
    """从登录页面提取 token 和 client_id"""
    resp = await client.get(f"{BASE_URL}/login")
    html = resp.text
    
    # 方案1：从隐藏表单字段提取
    # <input type="hidden" name="token" value="eyJ...">
    
    # 方案2：从 JavaScript 变量提取
    # window.__config = { token: "eyJ...", client_id: "6c85..." }
    
    # 方案3：client_id 固定，仅提取 token
    client_id = "6c857900-4e22-11e6-9048-612818fa8b4c"
    token = re.search(r'token["\']?\s*[:=]\s*["\']([^"\']+)', html).group(1)
    
    return token, client_id
```

### 6.2 项目配置缓存

创建任务需要多步查询项目配置，缓存可显著减少请求：

```python
class ProjectConfigCache:
    """项目配置缓存，避免重复查询"""
    
    def __init__(self):
        self._cache: dict[str, dict] = {}
    
    async def get_config(self, project_id: str, client: httpx.AsyncClient) -> dict:
        if project_id not in self._cache:
            config = await self._fetch_config(project_id, client)
            self._cache[project_id] = config
        return self._cache[project_id]
    
    async def _fetch_config(self, project_id: str, client: httpx.AsyncClient) -> dict:
        # 并发查询 tasklist、scenariofield、taskflow
        tasklists, scenario, ... = await asyncio.gather(
            client.get(f"/api/tasklists?_projectId={project_id}"),
            client.get(f"/api/v2/projects/{project_id}/scenariofieldconfigs"),
            ...
        )
        return { "tasklistId": ..., "stageId": ..., "customFields": ... }
```

### 6.3 错误处理策略

| 错误类型 | 处理方式 |
|---------|---------|
| 未登录（401/403） | 自动重新登录一次 |
| Token 过期 | 重新获取 token 后登录 |
| 网络超时 | 重试最多3次，指数退避 |
| 参数错误（400） | 返回详细错误信息给 Agent |
| 项目/任务不存在（404） | 返回友好提示 |

### 6.4 安全考虑

1. **密码存储**：密码通过工具参数传入，不持久化到磁盘
2. **Cookie 管理**：httpx CookieJar 仅在内存中，进程结束即清除
3. **HTTPS**：所有请求通过 HTTPS 加密传输
4. **日志脱敏**：日志中不打印密码和 Cookie 值

---

## 7. MCP 配置示例

### 7.1 Claude Desktop / VS Code 配置

```json
{
  "mcpServers": {
    "teambition": {
      "command": "python",
      "args": ["/Users/caizhijian/ai/teambition/scripts/teambition_mcp_server.py"],
      "env": {
        "TB_BASE_URL": "https://i2m.gdalpha.com:4431",
        "TB_ORG_ID": "5be50c1ebe825b60a7ad0894"
      }
    }
  }
}
```

### 7.2 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| TB_BASE_URL | Teambition 服务地址 | `https://i2m.gdalpha.com:4431` |
| TB_ORG_ID | 组织ID | `5be50c1ebe825b60a7ad0894` |
| TB_VERIFY_SSL | 是否验证 SSL 证书 | `true` |

---

## 8. 常用项目 ID 速查

| 项目名称 | 项目ID | 前缀 |
|---------|--------|------|
| 奥飞业务中台系统 | `65efbd2d7ad8b6f61a7516a1` | WDIS |
| 奥飞财经系统 | `693907787ad8b6f61a76a0a6` | WUFN |

> 完整的53个项目列表见 `teambition接口文档.md` 第2.8节。

---

## 9. 预期使用场景

### 场景1：创建需求

```
用户：在奥飞业务中台系统下创建一个需求"修复授信审批流程异常"，提出人是李光华

Agent 执行：
1. login(email, password)
2. create_task(project_id="65efbd2d7ad8b6f61a7516a1", content="修复授信审批流程异常", custom_fields='{"提出人": "李光华"}')
```

### 场景2：查看待办任务

```
用户：查看奥飞业务中台系统下我的待办任务

Agent 执行：
1. login(email, password)
2. list_tasks(project_id="65efbd2d7ad8b6f61a7516a1", is_done=False)
```

### 场景3：完成后清理测试任务

```
用户：删除任务 WDIS-1776

Agent 执行：
1. login(email, password)
2. list_tasks(project_id="65efbd2d7ad8b6f61a7516a1", keyword="WDIS-1776")
3. delete_task(task_id="69d4938e8e2e9a001c178cdc", project_id="65efbd2d7ad8b6f61a7516a1")
```
