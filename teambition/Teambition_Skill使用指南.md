# Teambition MCP Skill 使用指南

> **版本**: v2.2.0 | **最后更新**: 2026-04-08

## 1. 概述

Teambition MCP Skill 是一个基于 MCP (Model Context Protocol) 的工具集，让 AI 助手能够直接操作奥飞的 Teambition 私有化部署实例。无需打开浏览器，通过自然语言对话即可完成项目管理操作。

### 支持的操作

| 操作 | 工具名 | 说明 |
|------|--------|------|
| 登录认证 | `login` | 邮箱/密码登录，获取 Session |
| 查看项目 | `list_projects` | 列出当前用户参与的所有项目 |
| 查看任务 | `list_tasks` | 按项目查询任务列表，支持关键词搜索 |
| 创建任务 | `create_task` | 在指定项目下创建任务/需求 |
| 编辑任务 | `update_task` | 修改任务标题、描述、执行人、自定义字段等 |
| 删除任务 | `delete_task` | 将任务归档到回收站（软删除） |
| 添加参与者 | `add_involvers` | 为任务添加参与者成员 |

### 重要约束（强制）

- 除 `list_projects` 外，所有任务相关操作都必须提供 `project_id`（包含 `list_tasks`、`create_task`、`update_task`、`delete_task`、`add_involvers`）。
- 未提供 `project_id` 时，工具会直接返回错误并拒绝执行，防止跨项目误操作。
- `create_task` 在未指定提出人时，会按项目自动设置默认提出人并同步参与者：
  - 奥飞财经系统（WUFN）：古妙霞
  - 奥飞业务中台系统（WDIS）：陈靖文
- `create_task` 未指定 `dev_days` 时默认回填为 `1`；`dev_days <= 0` 或非法值也会强制回退为 `1` 并返回 `warnings`。
- 任务备注会自动补齐最少结构：`问题现象`、`可能原因`、`需要验证`。

---

## 2. 安装与配置

### 2.1 前置条件

- Python 3.10+
- 网络可访问 `https://i2m.gdalpha.com:4431`

### 2.2 安装依赖

```bash
pip install httpx "mcp[cli]"
```

### 2.3 配置凭据

在 `/Users/caizhijian/ai/teambition` 目录下创建 `.env` 文件：

```
TB_EMAIL=你的邮箱@163.com
TB_PASSWORD=你的密码
TB_BASE_URL=https://i2m.gdalpha.com:4431
TB_ORG_ID=5be50c1ebe825b60a7ad0894
TB_VERIFY_SSL=false
# 可选：项目默认提出人映射（JSON 单行），不填则使用内置兜底映射
# 推荐使用数组格式，不写 project_id；程序会按 project_name 自动解析 project_id
# proposer_custom_field_name 支持对象：字段名称 -> 取值规则（如 提出人=name、参与者=name和executorname）
# TB_DEFAULT_PROPOSER_BY_PROJECT_JSON=[{"project_name":"奥飞财经系统","name":"古妙霞","executorname":"登录用户","proposer_custom_field_name":{"提出人":"name","备注":"根据任务内容扩展，包括问题的现象，问题的分析，问题的验证等","开发人天":"1","参与者":"name和executorname"}},{"project_name":"奥飞业务中台系统","name":"陈靖文","executorname":"登录用户","proposer_custom_field_name":{"提出人":"name","备注":"根据任务内容扩展，包括问题的现象，问题的分析，问题的验证等","优先级":"普通","产品经理":"颜华艳","业务签字人":"李炎","经营单位":"奥迪","参与者":"name和executorname"}}]
```

说明：`TB_DEFAULT_PROPOSER_BY_PROJECT_JSON` 会在运行时自动解析 `project_id`、`member_id`、`user_id` 与提出人字段ID（`proposer_custom_field_id`），无需手工维护这些技术ID。

字段含义（数组中每个对象）：

| 字段 | 是否必填 | 含义 |
|------|---------|------|
| `project_name` | 是 | 项目名称（程序按此自动解析项目ID） |
| `name` | 是 | 默认提出人姓名（程序自动解析成员ID与用户ID） |
| `executorname` | 否 | 默认执行者姓名，`登录用户` 表示当前登录用户 |
| `proposer_custom_field_name` | 否 | 字段规则对象（字段名 -> 规则值），默认使用 `提出人` 字段 |

`proposer_custom_field_name` 常用规则值：

| 规则键 | 示例值 | 作用 |
|--------|--------|------|
| `提出人` | `name` | 使用默认提出人填充“提出人”字段 |
| `参与者` | `name和executorname` | 自动加入提出人和执行者为参与者 |
| `备注` | 文本说明 | 备注规范提示（实际备注仍以 `create_task` 入参和模板逻辑为准） |
| `开发人天` | `1` | 开发人天默认语义（最终由 `dev_days` 规则执行） |

### 2.4 注册到 VS Code

在 VS Code 的 `settings.json` 中添加 MCP Server 配置：

```json
{
  "mcp": {
    "servers": {
      "teambition": {
        "command": "python",
        "args": ["/Users/caizhijian/ai/teambition/scripts/teambition_mcp_server.py"],
        "type": "stdio"
      }
    }
  }
}
```

### 2.5 注册到 Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "teambition": {
      "command": "python",
      "args": ["/Users/caizhijian/ai/teambition/scripts/teambition_mcp_server.py"]
    }
  }
}
```

---

## 3. 基础用法

### 3.1 登录认证

> **注意**：如果已配置 `.env` 文件，工具会在首次调用时自动登录，无需手动调用 login。

**手动登录**（当 .env 未配置或需要切换账号时）：

```
请帮我登录 Teambition，邮箱是 xxx@163.com，密码是 xxx
```

AI 会调用:
```
login(email="xxx@163.com", password="xxx")
```

返回示例:
```
登录成功：李光华（5bea5a57be825b33ab9afacb）
```

### 3.2 查看项目列表

```
帮我看一下 Teambition 上有哪些项目
```

AI 会调用:
```
list_projects()
```

返回示例:
```json
{
  "total": 15,
  "projects": [
    {"name": "奥飞业务中台系统", "_id": "65efbd2d7ad8b6f61a7516a1"},
    {"name": "奥飞财经系统", "_id": "693907787ad8b6f61a76a0a6"},
    ...
  ]
}
```

### 3.3 查看任务列表

```
帮我看看奥飞财经系统项目的待办任务
```

AI 会调用:
```
list_tasks(project_id="693907787ad8b6f61a76a0a6")
```

**按关键词搜索**：

```
在奥飞业务中台系统里搜索"授信"相关的任务
```

AI 会调用:
```
list_tasks(project_id="65efbd2d7ad8b6f61a7516a1", keyword="授信")
```

---

## 4. 创建任务（最常用场景）

### 4.1 简单创建

```
在奥飞财经系统创建一个任务：修复付款发票J260200037无法撤销付款问题
```

AI 会调用:
```
create_task(
    project_id="693907787ad8b6f61a76a0a6",
    content="修复付款发票J260200037无法撤销付款问题"
)
```

> **提示**：`project_id` 为强制参数，未指定项目时不会执行创建。

### 4.2 指定执行人和描述

```
在奥飞业务中台系统创建一个任务：
标题：授信申请导入同客户合并主单
描述：当导入授信申请时，同一客户的多条记录需要合并为一个主单
执行人：李光华
优先级：紧急
```

AI 会调用:
```
create_task(
    project_id="65efbd2d7ad8b6f61a7516a1",
    content="授信申请导入同客户合并主单",
    note="当导入授信申请时，同一客户的多条记录需要合并为一个主单",
    executor_id="5bea5a57be825b33ab9afacb",
    priority=1
)
```

### 4.3 完整创建（含自定义字段）

这是最完整的使用场景，以实际案例说明。

**场景**：古妙霞提出一个 ERP 问题，需要在奥飞财经系统创建任务。

```
在奥飞财经系统创建一个任务：
- 标题：付款发票1002(J260200037)已付款无法撤销付款问题
- 提出人：古妙霞
- 系统：ERP
- 开发人天：1
```

AI 的执行步骤：

**Step 1**：创建基础任务
```
create_task(
    project_id="693907787ad8b6f61a76a0a6",
    content="付款发票1002(J260200037)已付款无法撤销付款问题",
    executor_id="5bea5a57be825b33ab9afacb",  # 默认当前用户
  dev_days=1,
  issue_phenomenon="付款发票1002(J260200037)已付款后，系统不允许撤销付款",
  possible_reason="付款状态与可撤销状态判断逻辑不一致",
  verification_items="1. 校验付款后撤销按钮权限\n2. 校验撤销后状态回写"
)
```

**Step 2**：逐个设置自定义字段（AI 会自动调用 `update_task`）

```
# 设置提出人
update_task(
    task_id="<任务ID>",
  project_id="693907787ad8b6f61a76a0a6",
    custom_field_id="693910667ad8b6f61a76a0fd",
    custom_field_type="lookup",
    custom_field_value='[{"_id":"665d864aeddf7ef85e0e4c14","title":"古妙霞"}]'
)

# 设置系统=ERP
update_task(
    task_id="<任务ID>",
  project_id="693907787ad8b6f61a76a0a6",
    custom_field_id="693922107ad8b6f61a76a168",
    custom_field_type="dropDown",
    custom_field_value='[{"_id":"693922107ad8b6f61a76a169","title":"ERP"}]'
)

# 设置开发人天=1
update_task(
    task_id="<任务ID>",
  project_id="693907787ad8b6f61a76a0a6",
    custom_field_id="69b3e4407ad8b6f61a76ef3e",
    custom_field_type="number",
    custom_field_value='[{"title":"1"}]'
)

# 设置上线时间（自动计算：当前时间 + 开发人天 + 0.5天）
update_task(
    task_id="<任务ID>",
  project_id="693907787ad8b6f61a76a0a6",
    custom_field_id="69b21bbf7ad8b6f61a76ebe1",
    custom_field_type="date",
    custom_field_value='[{"title":"2026-04-08T10:00:00.000Z"}]'
)
```

### 4.4 模板化备注参数（推荐）

如果你不想手写 `note`，可以直接传模板参数，系统会自动生成标准三段式备注。

```
在奥飞财经系统创建任务：
- 标题：付款发票已付款无法撤销
- 问题现象：付款发票1002已付款后无法撤销
- 可能原因：付款状态校验异常
- 需要验证：
  1. 撤销按钮显示逻辑
  2. 撤销后状态回写
```

AI 会调用:
```
create_task(
  project_id="693907787ad8b6f61a76a0a6",
  content="付款发票已付款无法撤销",
  issue_phenomenon="付款发票1002已付款后无法撤销",
  possible_reason="付款状态校验异常",
  verification_items="1. 撤销按钮显示逻辑\n2. 撤销后状态回写",
  dev_days=1
)
```

> **补充**：`dev_days` 不传时默认值是 `1`。

---

## 5. 编辑任务

### 5.1 修改标题

```
把任务 69d4db3b798759002a5ae842 的标题改成"修复付款发票撤销功能"
```

AI 会调用:
```
update_task(
  task_id="69d4db3b798759002a5ae842",
  project_id="693907787ad8b6f61a76a0a6",
  content="修复付款发票撤销功能"
)
```

### 5.2 修改执行人

```
把这个任务的执行人改成徐向荣
```

AI 会调用:
```
update_task(
  task_id="69d4db3b798759002a5ae842",
  project_id="693907787ad8b6f61a76a0a6",
  executor_id="5d071e50be825b283f9209d2"
)
```

### 5.3 修改自定义字段

```
把这个任务的开发人天改成2天
```

AI 会调用:
```
update_task(
    task_id="69d4db3b798759002a5ae842",
  project_id="693907787ad8b6f61a76a0a6",
    custom_field_id="69b3e4407ad8b6f61a76ef3e",
    custom_field_type="number",
    custom_field_value='[{"title":"2"}]'
)
```

---

## 6. 删除任务

```
把任务 69d4db3b798759002a5ae842 删除
```

AI 会调用:
```
delete_task(
  task_id="69d4db3b798759002a5ae842",
  project_id="693907787ad8b6f61a76a0a6"
)
```

> **注意**：删除是软删除（归档），任务会进入回收站，可以手动恢复。

---

## 7. 添加参与者

### 7.1 基本用法

```
帮我把古妙霞添加为任务 69d4db3b798759002a5ae842 的参与者
```

AI 会调用:
```
add_involvers(
    task_id="69d4db3b798759002a5ae842",
  user_ids="665d864abf5f11b187aa5279",
  project_id="693907787ad8b6f61a76a0a6"
)
```

### 7.2 添加多个参与者

```
把李光华和古妙霞都添加为这个任务的参与者
```

AI 会调用:
```
add_involvers(
    task_id="69d4db3b798759002a5ae842",
  user_ids="5bea5a57be825b33ab9afacb,665d864abf5f11b187aa5279",
  project_id="693907787ad8b6f61a76a0a6"
)
```

### 7.3 API 说明

| 项 | 值 |
|----|----|
| HTTP Method | PUT |
| URL | `/api/tasks/{taskId}/involveMembers` |
| 请求体 | `{"addInvolvers": ["userId1", "userId2"]}` |
| 响应 | 返回任务的 involveMembers 数组及 involvers 详情 |

> **注意**：用户在 involveMembers 中的 ID 可能与 customfield lookup 中的 ID 不同。例如古妙霞在 involveMembers 中是 `665d864abf5f11b187aa5279`，但在自定义字段提出人中是 `665d864aeddf7ef85e0e4c14`。

---

## 8. 常用 ID 速查表

### 7.1 项目 ID

| 项目名称 | 项目ID | 前缀 |
|---------|--------|------|
| 奥飞业务中台系统 | `65efbd2d7ad8b6f61a7516a1` | WDIS |
| 奥飞财经系统 | `693907787ad8b6f61a76a0a6` | WUFN |

> 其他项目 ID 可通过 `list_projects` 获取。

### 7.2 常用成员 ID

| 成员 | 用户ID |
|------|--------|
| 李光华 | `5bea5a57be825b33ab9afacb` |
| 徐向荣 | `5d071e50be825b283f9209d2` |
| 古妙霞 | `665d864aeddf7ef85e0e4c14` |

> 其他成员 ID 可通过 API `/api/organizations/{orgId}/members/search?q=姓名` 查询。

### 7.3 奥飞财经系统 (WUFN) 自定义字段

| 字段名 | _customfieldId | 类型 | 值格式 |
|--------|---------------|------|--------|
| 提出人 | `693910667ad8b6f61a76a0fd` | lookup | `[{"_id":"用户ID","title":"姓名"}]` |
| 系统 | `693922107ad8b6f61a76a168` | dropDown | `[{"_id":"选项ID","title":"选项名"}]` |
| 上线时间 | `69b21bbf7ad8b6f61a76ebe1` | date | `[{"title":"ISO日期字符串"}]` |
| 开发人天 | `69b3e4407ad8b6f61a76ef3e` | number | `[{"title":"数字"}]` |
| 业务价值 | `693793de7ad8b6f61a769edc` | text | `[{"title":"文本内容"}]` |
| 签字人 | `693793817ad8b6f61a769ed7` | text | `[{"title":"姓名"}]` |
| 需求分类 | `5d1b3638ce9f165cd5d980b5` | commongroup | - |

### 7.4 "系统"字段选项

| 选项 | 选项ID |
|------|--------|
| ERP | `693922107ad8b6f61a76a169` |
| 费控 | `693922107ad8b6f61a76a16a` |
| 资金 | `693922107ad8b6f61a76a16b` |

---

## 9. 自定义字段值格式说明

不同类型的自定义字段，`value` 格式不同：

| 类型 | 值格式 | 示例 |
|------|--------|------|
| **text** | `[{"title": "文本内容"}]` | `[{"title": "描述信息"}]` |
| **number** | `[{"title": "数字字符串"}]` | `[{"title": "1"}]` |
| **date** | `[{"title": "ISO日期"}]` | `[{"title": "2026-04-08T10:00:00.000Z"}]` |
| **dropDown** | `[{"_id": "选项ID", "title": "选项名"}]` | `[{"_id": "xxx", "title": "ERP"}]` |
| **lookup (member)** | `[{"_id": "用户ID", "title": "用户名"}]` | `[{"_id": "xxx", "title": "古妙霞"}]` |

> **重要**：dropDown 和 lookup 的 value 必须是对象数组，不能是字符串数组。

---

## 10. 实际案例：端到端创建任务

### 案例：古妙霞提出付款发票问题

**用户输入**：
```
在奥飞财经系统创建一个任务，付款发票1002(J260200037)已付款无法撤销付款问题，
是古妙霞提出的，系统是ERP，开发人天1天。
```

**AI 执行过程**：

1. 自动登录（通过 .env 凭据）
2. 查询 WUFN 项目配置（获取 tasklistId、stageId 等）
3. 创建任务（标题、备注、执行人=当前用户、截止日期=当前+1.5天）
4. 设置自定义字段：
   - 提出人 = 古妙霞
   - 系统 = ERP
   - 开发人天 = 1
  - 上线时间 = 当前 + 开发人天 + 0.5天
5. **自动添加参与者**：将提出者和执行者都设为参与者
**最终结果**：

```
✅ 任务创建成功！ID: 69d4db3b798759002a5ae842

| 字段 | 值 |
|------|-----|
| 标题 | 付款发票1002(J260200037)已付款无法撤销付款问题 |
| 执行人 | 李光华 |
| 提出人 | 古妙霞 |
| 系统 | ERP |
| 开发人天 | 1 |
| 上线时间 | 2026-04-08 |
| 截止日期 | 2026-04-08 |
```

---

## 11. 高级用法

### 10.1 批量查询（查已完成任务）

```
帮我看看奥飞财经系统已经完成的任务
```

AI 会调用:
```
list_tasks(project_id="693907787ad8b6f61a76a0a6", is_done=true)
```

### 10.2 搜索特定任务

```
在奥飞业务中台系统里搜索发票相关的任务
```

AI 会调用:
```
list_tasks(project_id="65efbd2d7ad8b6f61a7516a1", keyword="发票")
```

### 10.3 创建后立即设置多个自定义字段

AI 会在创建任务后，自动连续调用 `update_task` 设置每个自定义字段。每次只设置一个字段，因为 API 要求单字段更新。

---

## 12. 常见问题

### Q1: 为什么不需要手动登录？
`.env` 文件配置了邮箱和密码后，Skill 会在首次调用任何工具时自动登录。Session 会在进程生命周期内保持有效。

### Q2: 创建任务时不知道项目 ID 怎么办？
直接说项目名称（如"奥飞财经系统"），AI 会自动匹配项目 ID。也可以先调用 `list_projects` 查看所有项目。

### Q3: 不知道用户 ID 怎么办？
直接说用户姓名（如"古妙霞"），AI 会通过搜索 API 查找对应的用户 ID。

### Q4: 自定义字段设置报 400 错误？
确认 value 格式正确：
- dropDown 和 lookup 的 value 必须是 `[{_id, title}]` 对象数组
- number 的 value 是 `[{title: "数字"}]`
- text 的 value 是 `[{title: "文本"}]`

### Q5: 如何查看任务在 Teambition 网页上的链接？
任务创建后，可以在浏览器访问：
```
https://i2m.gdalpha.com:4431/project/<项目ID>/works/task/<任务ID>
```

---

## 13. 技术架构

```
┌─────────────────┐     stdio      ┌──────────────────────┐     HTTPS      ┌────────────────┐
│   AI 助手       │ ◄─────────────► │   MCP Server         │ ◄────────────► │   Teambition   │
│ (Claude/Copilot)│                │   (Python + FastMCP)  │                │   私有化部署     │
└─────────────────┘                └──────────────────────┘                └────────────────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │   .env 文件   │
                                   │  (凭据配置)   │
                                   └──────────────┘
```

### 关键特性

| 特性 | 说明 |
|------|------|
| Session 持久化 | httpx.Client 自动管理 Cookie |
| 项目配置缓存 | tasklist/taskflow 按项目缓存，30 分钟过期 |
| 自动重试 | 网络超时自动重试 2 次 |
| 自动登录 | 检测到 .env 凭据，首次调用自动登录 |
| SSL 可配置 | 支持自签名证书 |

---

## 14. 发布前检查（建议每日）

执行以下命令，可快速验证关键回归规则（项目必填、备注模板、默认开发人天等）：

```bash
python scripts/run_daily_pre_release_checks.py
```

Windows 可使用：

```bat
scripts\run_daily_pre_release_checks.bat
```
