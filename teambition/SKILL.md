---
name: teambition
description: >
  Teambition 私有化部署项目管理 MCP 工具。支持登录认证、查询项目列表、
  查询/创建/编辑/删除任务。触发条件：用户提到 teambition、任务管理、项目管理、
  创建需求、创建任务、WDIS、WUFN 等项目前缀，或需要操作 Teambition 的场景。
triggers: [
  "teambition", "任务管理", "项目管理", "创建需求", "创建任务",
  "WDIS", "WUFN", "项目列表", "任务列表", "需求"
]
dependencies: python>=3.10, httpx>=0.24.0, mcp[cli]>=1.0.0
version: 2.2.0
---

# Teambition MCP Skill

操作 Teambition 私有化部署实例的 MCP 工具集。

## 快速开始

```bash
# 1. 安装依赖
pip install httpx "mcp[cli]"

# 2. 配置凭据（复制模板并填入实际值）
cp .env.example .env
# 编辑 .env 填入 TB_EMAIL 和 TB_PASSWORD

# 3. 启动 MCP Server
python scripts/teambition_mcp_server.py

# 4. 发布前检查（建议最少每日一次）
python scripts/run_daily_pre_release_checks.py
```

## 发布前文档一致性检查清单

- [ ] `SKILL.md` 的参数表与代码签名一致（重点：`project_id`、`issue_phenomenon`、`possible_reason`、`verification_items`、`dev_days`、`warnings`）
- [ ] `Teambition_Skill使用指南.md` 的示例调用与参数说明一致（含 `update_task/delete_task/add_involvers` 的 `project_id`）
- [ ] `Teambition_Skill设计方案.md` 的工具设计与当前实现一致（含 `create_task` 模板参数、`dev_days` 默认与 `warnings` 语义）
- [ ] `teambition接口文档.md` 已包含 MCP 约束说明（项目必填 + `create_task` 语义约定）
- [ ] 已执行发布前检查命令：`python scripts/run_daily_pre_release_checks.py`

## 必要参数引导

使用此 Skill 时，AI 应根据用户意图引导提供以下必要信息：

### 创建任务 (create_task)
| 参数 | 是否必填 | 引导提示 |
|------|---------|---------|
| 项目名称/ID | ✅ 必填 | "请问要在哪个项目中创建任务？（如：奥飞业务中台系统/奥飞财经系统）" |
| 任务标题 | ✅ 必填 | "请提供任务标题/需求名称" |
| 执行者 | ❌ 可选 | "是否需要指定执行者？" |
| 优先级 | ❌ 可选 | "是否设置优先级？（0=普通，1=紧急，2=非常紧急）" |
| 描述 | ❌ 可选 | "是否添加任务描述？" |
| 问题现象 | ❌ 可选 | "请描述问题现象（如：单据无法重新验证）" |
| 可能原因 | ❌ 可选 | "请描述可能原因（如：部分行未入账）" |
| 需要验证 | ❌ 可选 | "请提供需要验证的检查项（可多条）" |
| 开发人天 | ❌ 可选 | "是否指定开发人天？未指定默认1" |

> **默认规则**：
> - 未指定任务所属项目时，不执行任何任务操作，并返回提示要求先提供项目信息（强制）。
> - 未指定提出人时，按项目自动回填：
>   - 奥飞财经系统（WUFN）：默认提出人=古妙霞
>   - 奥飞业务中台系统（WDIS）：默认提出人=陈靖文
>   - 支持通过 `TB_DEFAULT_PROPOSER_BY_PROJECT_JSON` 使用数组配置（按 `project_name`），运行时自动解析 `project_id` / `member_id` / `user_id` / `proposer_custom_field_id`。
> - 参与者默认与提出人保持一致（未传 `involver_ids` 时自动添加默认提出人）。
> - 任务备注会自动补齐最少结构：`问题现象`、`可能原因`、`需要验证`。
> - 未指定开发人天时，默认回填为 `1`（项目存在“开发人天”字段时自动写入）。
> - 当 `dev_days <= 0` 或非法时，会强制回退为 `1` 并在返回JSON中给出 `warnings` 提示。

### 编辑任务 (update_task)
| 参数 | 是否必填 | 引导提示 |
|------|---------|---------|
| 项目名称/ID | ✅ 必填 | "请先确认任务所属项目（如：奥飞业务中台系统/奥飞财经系统）" |
| 任务ID或编号 | ✅ 必填 | "请提供要编辑的任务ID或编号（如 WDIS-1500）" |
| 修改内容 | ✅ 至少一项 | "请问要修改什么？（标题/描述/执行者/优先级/自定义字段）" |

### 查询任务 (list_tasks)
| 参数 | 是否必填 | 引导提示 |
|------|---------|---------|
| 项目名称/ID | ✅ 必填 | "请问要查询哪个项目的任务？" |
| 搜索关键词 | ❌ 可选 | "是否需要按关键词搜索？" |

### 删除任务 (delete_task)
| 参数 | 是否必填 | 引导提示 |
|------|---------|---------|
| 项目名称/ID | ✅ 必填 | "请先确认任务所属项目（如：奥飞业务中台系统/奥飞财经系统）" |
| 任务ID | ✅ 必填 | "请提供要删除的任务ID" |

### 添加参与者 (add_involvers)
| 参数 | 是否必填 | 引导提示 |
|------|---------|---------|
| 项目名称/ID | ✅ 必填 | "请先确认任务所属项目（如：奥飞业务中台系统/奥飞财经系统）" |
| 任务ID | ✅ 必填 | "请提供要添加参与者的任务ID" |
| 参与者用户ID列表 | ✅ 必填 | "请提供参与者用户ID，多个用逗号分隔" |

## 配置

| 项 | 值 |
|----|-----|
| 服务地址 | `https://i2m.gdalpha.com:4431` |
| 组织ID | `5be50c1ebe825b60a7ad0894` |
| 组织名称 | 奥飞娱乐 |

## 工具总览

| 工具 | 功能 | 前置条件 |
|------|------|---------|
| `login` | 邮箱/密码登录获取Session | 无 |
| `list_projects` | 查询当前用户参与的项目列表 | 已登录 |
| `list_tasks` | 查询指定项目下的任务列表 | 已登录 |
| `create_task` | 在指定项目下创建任务/需求 | 已登录 |
| `update_task` | 编辑任务属性（标题/自定义字段等） | 已登录 |
| `delete_task` | 将任务移到回收站（软删除） | 已登录 |
| `add_involvers` | 为任务添加参与者 | 已登录 |

## 常用项目 ID

| 项目名称 | 项目ID | 前缀 |
|---------|--------|------|
| 奥飞业务中台系统 | `65efbd2d7ad8b6f61a7516a1` | WDIS |
| 奥飞财经系统 | `693907787ad8b6f61a76a0a6` | WUFN |

> 完整项目列表：调用 `list_projects` 工具获取。

## 典型用法

### 登录 → 查询项目 → 查询任务

```
1. login(email="user@example.com", password="xxx")
2. list_projects()
3. list_tasks(project_id="65efbd2d7ad8b6f61a7516a1")
```

### 创建任务

```
1. login(...)
2. create_task(project_id="65efbd2d7ad8b6f61a7516a1", content="修复授信审批流程异常")
```

## API 详细文档

如需了解 Teambition API 请求/响应格式详情，参见 [teambition接口文档.md](teambition接口文档.md)。

## 环境变量

配置在 `.env` 文件中（参考 `.env.example`）：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TB_BASE_URL` | Teambition 服务地址 | `https://i2m.gdalpha.com:4431` |
| `TB_ORG_ID` | 组织ID | `5be50c1ebe825b60a7ad0894` |
| `TB_VERIFY_SSL` | 是否验证SSL证书 | `false` |
| `TB_COOKIE` | 已登录浏览器复制的 Cookie 请求头；优先使用，过期时回退账号密码 | （可选） |
| `TB_EMAIL` | 登录邮箱（未配置有效 Cookie 时使用） | （可选） |
| `TB_PASSWORD` | 登录密码（未配置有效 Cookie 时使用） | （可选） |
| `TB_DEFAULT_PROPOSER_BY_PROJECT_JSON` | 项目默认提出人映射(JSON单行)。推荐使用数组并按 `project_name` 配置，支持 `executorname` 与 `proposer_custom_field_name` 字段规则对象；技术ID均自动解析；为空时使用代码兜底 | （可选） |

## 工具参数详情

### login
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | str | ✅ | 登录邮箱或手机号 |
| password | str | ✅ | 登录密码 |

### list_projects
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page_size | int | ❌ | 每页数量，默认50 |
| fetch_all | bool | ❌ | 是否自动分页获取全部，默认True |

### list_tasks
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | str | ✅ | 项目ID |
| page_size | int | ❌ | 每页数量，默认30 |
| is_done | bool | ❌ | 查已完成任务，默认False |
| keyword | str | ❌ | 搜索关键词 |

### create_task
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | str | ✅ | 项目ID |
| content | str | ✅ | 任务标题 |
| executor_id | str | ❌ | 执行者用户ID（不传或空白时默认当前登录用户） |
| note | str | ❌ | 任务描述（会自动补齐“问题现象/可能原因/需要验证”结构） |
| priority | int | ❌ | 优先级(0=普通,1=紧急,2=非常紧急) |
| involver_ids | str | ❌ | 参与者用户ID，多个用逗号分隔（如提出者ID）；不传时按项目默认提出人自动添加参与者 |
| dev_days | float | ❌ | 开发人天，不传默认1 |
| issue_phenomenon | str | ❌ | 模板化备注参数：问题现象 |
| possible_reason | str | ❌ | 模板化备注参数：可能原因 |
| verification_items | str | ❌ | 模板化备注参数：需要验证（可多行） |

### update_task
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | str | ✅ | 任务ID |
| project_id | str | ✅ | 所属项目ID（必填） |
| content | str | ❌ | 新标题 |
| note | str | ❌ | 新描述 |
| executor_id | str | ❌ | 新执行者用户ID |
| priority | int | ❌ | 新优先级 |
| custom_field_id | str | ❌ | 自定义字段ID |
| custom_field_type | str | ❌ | 自定义字段类型 |
| custom_field_value | str | ❌ | 自定义字段值(JSON) |

### delete_task
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | str | ✅ | 任务ID |
| project_id | str | ✅ | 所属项目ID（必填） |

### add_involvers
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | str | ✅ | 任务ID |
| user_ids | str | ✅ | 参与者用户ID，多个用逗号分隔 |
| project_id | str | ✅ | 所属项目ID（必填） |

## 特性

- **Session 持久化**：httpx.Client 自动管理 Cookie
- **项目配置缓存**：tasklist/taskflow/scenariofieldconfig 按项目缓存，30 分钟过期
- **错误重试**：网络连接超时自动重试 2 次
- **SSL 可配置**：支持自签名证书的私有化部署
