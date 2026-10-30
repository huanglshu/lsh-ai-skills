# Teambition 接口文档

> 文档生成时间：2026-04-07  
> 基础域名：`https://i2m.gdalpha.com:4431`  
> 组织ID：`5be50c1ebe825b60a7ad0894`（奥飞娱乐）

---

## 1. 页面导航

### 1.1 我的项目页面

- **URL**: `https://i2m.gdalpha.com:4431/organization/5be50c1ebe825b60a7ad0894`
- **说明**: 点击左侧菜单"我的项目"后跳转的页面，展示星标项目、项目分组和我参与的项目列表

### 1.2 项目任务页面

- **URL模板**: `https://i2m.gdalpha.com:4431/project/{projectId}/tasks/view/all`
- **示例**: `https://i2m.gdalpha.com:4431/project/65efbd2d7ad8b6f61a7516a1/tasks/view/all`（奥飞业务中台系统）

### 1.3 MCP 封装调用约束（项目必填）

当以上 HTTP API 被封装为 Teambition MCP 工具时，需统一遵循以下规则：

| MCP工具 | project_id 是否必填 | 说明 |
|--------|----------------------|------|
| `list_tasks` | 是 | 查询任务前必须明确所属项目 |
| `create_task` | 是 | 未指定项目时禁止创建任务 |
| `update_task` | 是 | 未指定项目时禁止更新任务 |
| `delete_task` | 是 | 未指定项目时禁止删除任务 |
| `add_involvers` | 是 | 未指定项目时禁止添加参与者 |

> 目的：防止跨项目误操作，确保所有任务写操作都在明确项目上下文中执行。

### 1.4 MCP create_task 语义约定（模板备注 + 人天默认 + warnings）

当使用 MCP `create_task` 封装接口时，除 HTTP 参数本身外，增加以下业务语义：

| 语义项 | 规则 |
|--------|------|
| 模板化备注参数 | 支持 `issue_phenomenon`、`possible_reason`、`verification_items`，自动组装到 `note` |
| 备注最少结构 | 无论是否传 `note`，最终备注需至少包含：`问题现象`、`可能原因`、`需要验证` |
| 默认提出人映射解析 | `TB_DEFAULT_PROPOSER_BY_PROJECT_JSON` 支持数组配置（按 `project_name`、`name`、可选 `executorname` 与字段规则对象），运行时自动解析 `project_id`、`member_id`、`user_id`、`proposer_custom_field_id` |
| dev_days 默认值 | 未传 `dev_days` 时，默认回填 `1` |
| dev_days 非法值回退 | `dev_days <= 0` 或非法值时，强制回退为 `1` |
| warnings 返回语义 | 发生回退时，在 MCP 返回 JSON 中增加 `warnings` 数组说明回退原因 |

> 说明：`warnings` 为 MCP 业务封装层返回字段，不属于 Teambition 原生 HTTP 接口字段。

---

## 2. API 接口

### 2.0 用户登录（获取Session）

- **请求方式**: `POST`
- **请求URL**: `/api/login/email`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/login/email
  ```
- **Content-Type**: `application/x-www-form-urlencoded; charset=UTF-8`

#### 请求头

| 请求头 | 值 |
|--------|-----|
| Accept | `*/*` |
| Content-Type | `application/x-www-form-urlencoded; charset=UTF-8` |
| X-Requested-With | `XMLHttpRequest` |
| Referer | `https://i2m.gdalpha.com:4431/login?next_url=...` |

#### 请求参数（form-urlencoded 格式）

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| phone | string | 否 | 手机号（与email二选一） |
| email | string | 否 | 工作邮箱（与phone二选一） |
| password | string | 是 | 登录密码 |
| next_url | string | 否 | 登录成功后的跳转地址，如 `https://i2m.gdalpha.com:4431/projects` |
| response_type | string | 是 | 固定值 `session` |
| token | string | 是 | JWT格式的CSRF token，从登录页面获取 |
| client_id | string | 是 | 客户端标识，固定值 `6c857900-4e22-11e6-9048-612818fa8b4c` |

> **说明**：
> - `phone` 和 `email` 二选一，可同时填写但至少填一个
> - `token` 为页面加载时动态生成的JWT token，有效期约1小时
> - `client_id` 为应用固定的客户端标识
> - `response_type=session` 表示登录后通过Cookie维护会话

#### 请求示例

```
phone=&email=user%40example.com&password=mypassword&next_url=https%3A%2F%2Fi2m.gdalpha.com%3A4431%2Fprojects&response_type=session&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...&client_id=6c857900-4e22-11e6-9048-612818fa8b4c
```

#### 响应格式

**登录成功（200）**：

登录成功后，响应体为JSON格式的用户基本信息（约302字节），响应头中包含 `Set-Cookie` 设置 httpOnly 会话Cookie。
登录成功后页面自动跳转到 `next_url` 指定的地址。

> **关于Cookie**：登录后设置的Cookie为 `httpOnly`，JavaScript 无法通过 `document.cookie` 读取，这是正确的安全设计。后续所有API请求浏览器自动携带该Cookie进行身份认证。

**登录失败（400）- 密码错误**：
```json
{
  "name": "PasswordUnmatch",
  "message": "WrongPassword",
  "status": 400
}
```

**登录失败（404）- 账号不存在**：
```json
{
  "name": "NotFound",
  "message": "UserNotFound",
  "status": 404
}
```

#### 已验证的请求示例（实际登录成功）

```
POST /api/login/email HTTP/1.1
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest

phone=&email=echizen_hua%40163.com&password=Hua902201%24&next_url=https%3A%2F%2Fi2m.gdalpha.com%3A4431%2Fprojects&response_type=session&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...&client_id=6c857900-4e22-11e6-9048-612818fa8b4c

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 302
```

#### 认证流程说明

1. 访问登录页面 `GET /login?next_url=...` 获取页面中的 `token` 和 `client_id`
2. 使用账号密码调用 `POST /api/login/email` 进行登录
3. 登录成功后，浏览器/客户端保存 httpOnly Cookie
4. 后续所有API请求自动携带Cookie进行身份认证（无需额外的Authorization Header）

---

### 2.0.1 获取当前登录用户信息

- **请求方式**: `GET`
- **请求URL**: `/api/users/me`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/users/me
  ```

#### 请求头

无需额外请求头，登录后的Cookie自动携带。

#### 响应格式（已验证）

```json
{
  "_id": "5bea5a57be825b33ab9afacb",
  "email": "echizen_hua@163.com",
  "name": "李光华",
  "avatarUrl": "https://i2mfile.gdalpha.com:4431/thumbnail/013p93c3d4cc63331da416dd9fdf8e74cf61/w/100/h/100",
  "created": null,
  "title": "",
  "birthday": null,
  "location": "",
  "phone": "",
  "isActive": false,
  "website": "",
  "pinyin": "li guang hua",
  "py": "lgh",
  "isNew": false,
  "plan": {},
  "notification": {
    "comment": { "mobile": true, "email": false },
    "newpost": { "mobile": true, "email": false },
    "newtask": { "mobile": true, "email": false },
    "newwork": { "mobile": true, "email": false },
    "newevent": { "mobile": true, "email": false },
    "involve": { "mobile": true, "email": false },
    "update": { "mobile": true, "email": false },
    "daily": { "email": true },
    "monthly": { "email": true }
  },
  "region": "",
  "lastEntered": {},
  "language": "zh",
  "aliens": [],
  "strikerAuth": "Bearer eyJhbGciOiJIUzI1NiJ9...",
  "phoneForLogin": "18702019391",
  "enabledGoogleTwoFactor": false,
  "emails": [
    {
      "_id": "5c171edbd709e761b1affe4d",
      "email": "echizen_hua@163.com",
      "state": 1
    }
  ],
  "snapperToken": "",
  "tcmToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "crossNotify": { "badge": 0 },
  "badge": 0,
  "normal": 0,
  "ated": 0,
  "later": 0,
  "private": 0,
  "hasNormal": false,
  "hasAted": false,
  "hasLater": false,
  "hasPrivate": false,
  "inbox": 0,
  "calLink": "webcal://i2m.gdalpha.com:4431/api/events/{token}.ics",
  "taskCalLink": "webcal://i2m.gdalpha.com:4431/api/tasks/{token}.ics",
  "joinedProjectsCount": 53
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 用户唯一ID |
| email | string | 邮箱地址 |
| name | string | 用户显示名称 |
| avatarUrl | string | 头像URL |
| phone | string | 手机号 |
| pinyin | string | 姓名拼音 |
| py | string | 姓名拼音首字母缩写 |
| isNew | boolean | 是否新用户 |
| language | string | 语言偏好 |
| notification | object | 通知设置（评论、新文章、新任务等） |
| strikerAuth | string | 文件上传认证Token（Bearer格式） |
| phoneForLogin | string | 绑定的登录手机号 |
| enabledGoogleTwoFactor | boolean | 是否启用Google双因素认证 |
| emails | array | 绑定的邮箱列表（含验证状态） |
| tcmToken | string | TCM服务认证Token |
| badge | number | 未读消息数 |
| joinedProjectsCount | number | 参与的项目数量 |

---

### 2.1 获取星标项目列表

- **请求方式**: `GET`
- **请求URL**: `/api/v2/projects/starred`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/projects/starred?pageSize=99&orderBy=name&_organizationId=5be50c1ebe825b60a7ad0894
  ```

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pageSize | number | 否 | 每页数量，默认99 |
| orderBy | string | 否 | 排序方式，如 `name` |
| _organizationId | string | 是 | 组织ID |

#### 响应格式

```json
{
  "nextPageToken": "",
  "result": [
    {
      "_id": "项目ID",
      "name": "项目名称",
      "_creatorId": "创建者ID",
      "logo": "项目Logo URL",
      "description": "项目描述",
      "category": "项目类别",
      "_organizationId": "所属组织ID",
      "visibility": "可见性",
      "isPublic": false,
      "created": "创建时间",
      "updated": "更新时间",
      "isArchived": false,
      "isSuspended": false
    }
  ]
}
```

#### 星标项目列表（9个）

| 序号 | 项目ID | 项目名称 | 创建时间 | 项目URL |
|------|--------|----------|----------|---------|
| 1 | `693907787ad8b6f61a76a0a6` | 奥飞财经系统 | 2025-12-10 | [链接](https://i2m.gdalpha.com:4431/project/693907787ad8b6f61a76a0a6/tasks/view/all) |
| 2 | `65efbd2d7ad8b6f61a7516a1` | 奥飞业务中台系统 | 2024-03-12 | [链接](https://i2m.gdalpha.com:4431/project/65efbd2d7ad8b6f61a7516a1/tasks/view/all) |
| 3 | `60ebdef68eb2da2a576f326a` | BIDATA | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebdef68eb2da2a576f326a/tasks/view/all) |
| 4 | `6209bdd57ae9a39620b1ab81` | DataGroup | 2022-02-14 | [链接](https://i2m.gdalpha.com:4431/project/6209bdd57ae9a39620b1ab81/tasks/view/all) |
| 5 | `60ebde348eb2da2a576f31b5` | EBS | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebde348eb2da2a576f31b5/tasks/view/all) |
| 6 | `5c4139485d1dcb645de14788` | 个人事项管理 | 2019-01-18 | [链接](https://i2m.gdalpha.com:4431/project/5c4139485d1dcb645de14788/tasks/view/all) |
| 7 | `60ebde818eb2da2a576f31f3` | HFM | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebde818eb2da2a576f31f3/tasks/view/all) |
| 8 | `60ebdecd8eb2da2a576f3231` | HEC | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebdecd8eb2da2a576f3231/tasks/view/all) |
| 9 | `5c53bcd35d1dcb645dfffe1c` | 技术中心人天登记 | 2019-02-01 | [链接](https://i2m.gdalpha.com:4431/project/5c53bcd35d1dcb645dfffe1c/tasks/view/all) |

---

### 2.2 获取我参与的项目列表

- **请求方式**: `GET`
- **请求URL**: `/api/v2/projects`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/projects?_organizationId=5be50c1ebe825b60a7ad0894&selectBy=joined&orderBy=name&pageToken=&pageSize=50
  ```

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| _organizationId | string | 是 | 组织ID |
| selectBy | string | 是 | 筛选条件，`joined` 表示我参与的项目 |
| orderBy | string | 否 | 排序方式，如 `name` |
| pageToken | string/number | 否 | 分页token，空字符串表示第一页；返回值中的 `nextPageToken` 用于下一页 |
| pageSize | number | 否 | 每页数量，默认20 |

#### 响应格式

```json
{
  "nextPageToken": 20,
  "result": [
    {
      "_id": "项目ID",
      "name": "项目名称",
      "_creatorId": "创建者ID",
      "logo": "项目Logo URL",
      "py": "拼音缩写",
      "pinyin": "完整拼音",
      "description": "项目描述",
      "category": "项目类别（如 blank project）",
      "_organizationId": "所属组织ID",
      "visibility": "可见性（project）",
      "isPublic": false,
      "created": "创建时间（ISO 8601）",
      "updated": "更新时间（ISO 8601）",
      "isArchived": false,
      "isSuspended": false,
      "_defaultRoleId": null,
      "_rootCollectionId": "根集合ID",
      "_sourceId": null,
      "_defaultCollectionId": "默认集合ID",
      "customfields": [],
      "sortMethod": "排序方式",
      "isTemplate": false,
      "startDate": null,
      "endDate": null,
      "tasksCount": 0,
      "postsCount": 0,
      "eventsCount": 0,
      "worksCount": 0,
      "tagsCount": 0,
      "membersCount": 0,
      "unreadCount": 0,
      "organization": {
        "name": "组织名称",
        "_id": "组织ID",
        "plan": {
          "status": "paid",
          "isExpired": false
        }
      },
      "permissionBinding": {
        "isJoined": true,
        "permissions": ["权限列表..."]
      }
    }
  ]
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| nextPageToken | string/number | 下一页的分页标记，空字符串表示无更多数据 |
| result | array | 项目数组 |
| result[]._id | string | 项目唯一ID（MongoDB ObjectId） |
| result[].name | string | 项目名称 |
| result[]._creatorId | string | 项目创建者用户ID |
| result[].logo | string | 项目Logo图片URL |
| result[].py | string | 项目名称拼音缩写 |
| result[].pinyin | string | 项目名称完整拼音 |
| result[].description | string | 项目描述 |
| result[].category | string | 项目类别 |
| result[]._organizationId | string | 所属组织ID |
| result[].visibility | string | 项目可见性 |
| result[].isPublic | boolean | 是否公开 |
| result[].created | string | 创建时间（ISO 8601格式） |
| result[].updated | string | 更新时间 |
| result[].isArchived | boolean | 是否已归档 |
| result[].isSuspended | boolean | 是否已暂停 |
| result[].isTemplate | boolean | 是否为模板项目 |
| result[].tasksCount | number | 任务数量 |
| result[].membersCount | number | 成员数量 |
| result[].unreadCount | number | 未读数量 |
| result[].organization | object | 所属组织信息 |
| result[].permissionBinding | object | 权限绑定信息 |

---

### 2.8 我参与的项目完整列表（53个）

| 序号 | 项目ID | 项目名称 | 创建时间 | 项目URL |
|------|--------|----------|----------|---------|
| 1 | `5e40b6ed2c2204030c85c41c` | 2020 DT工作 | 2020-02-10 | [链接](https://i2m.gdalpha.com:4431/project/5e40b6ed2c2204030c85c41c/tasks/view/all) |
| 2 | `5fed4b83a18b330de2e01d7a` | 2021项目与运维的项目 | 2020-12-31 | [链接](https://i2m.gdalpha.com:4431/project/5fed4b83a18b330de2e01d7a/tasks/view/all) |
| 3 | `61d3bb9c7ae9a39620b10724` | 奥迪澳贝拆分 | 2022-01-04 | [链接](https://i2m.gdalpha.com:4431/project/61d3bb9c7ae9a39620b10724/tasks/view/all) |
| 4 | `693907787ad8b6f61a76a0a6` | 奥飞财经系统 | 2025-12-10 | [链接](https://i2m.gdalpha.com:4431/project/693907787ad8b6f61a76a0a6/tasks/view/all) |
| 5 | `65efbd2d7ad8b6f61a7516a1` | 奥飞业务中台系统 | 2024-03-12 | [链接](https://i2m.gdalpha.com:4431/project/65efbd2d7ad8b6f61a7516a1/tasks/view/all) |
| 6 | `60ebdef68eb2da2a576f326a` | BIDATA | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebdef68eb2da2a576f326a/tasks/view/all) |
| 7 | `5c8a1a69147c5e26f84088a6` | BPIT部门团建 | 2019-03-14 | [链接](https://i2m.gdalpha.com:4431/project/5c8a1a69147c5e26f84088a6/tasks/view/all) |
| 8 | `5d7741736f3a7e735d31a9a3` | BPIT图书借阅管理 | 2019-09-10 | [链接](https://i2m.gdalpha.com:4431/project/5d7741736f3a7e735d31a9a3/tasks/view/all) |
| 9 | `5bebd5b321a70766c07a8bd0` | BPIT重点工作 | 2018-11-14 | [链接](https://i2m.gdalpha.com:4431/project/5bebd5b321a70766c07a8bd0/tasks/view/all) |
| 10 | `62539c937ae9a39620b27fe6` | 潮玩供应链改造 | 2022-04-11 | [链接](https://i2m.gdalpha.com:4431/project/62539c937ae9a39620b27fe6/tasks/view/all) |
| 11 | `5ce6201dc3fe1326865b73ec` | 财务信息化建设项目 | 2019-05-23 | [链接](https://i2m.gdalpha.com:4431/project/5ce6201dc3fe1326865b73ec/tasks/view/all) |
| 12 | `6209bdd57ae9a39620b1ab81` | DataGroup | 2022-02-14 | [链接](https://i2m.gdalpha.com:4431/project/6209bdd57ae9a39620b1ab81/tasks/view/all) |
| 13 | `63da30c77ae9a39620b3ef11` | 订货宝 | 2023-02-01 | [链接](https://i2m.gdalpha.com:4431/project/63da30c77ae9a39620b3ef11/tasks/view/all) |
| 14 | `6164f7e28eb2da2a57705412` | 电商平台经营大屏 | 2021-10-12 | [链接](https://i2m.gdalpha.com:4431/project/6164f7e28eb2da2a57705412/tasks/view/all) |
| 15 | `616e41858eb2da2a577073a5` | 电商运营指标 | 2021-10-19 | [链接](https://i2m.gdalpha.com:4431/project/616e41858eb2da2a577073a5/tasks/view/all) |
| 16 | `60e3f7898eb2da2a576f0a79` | EBS+FSSC+HFM | 2021-07-06 | [链接](https://i2m.gdalpha.com:4431/project/60e3f7898eb2da2a576f0a79/tasks/view/all) |
| 17 | `60ebde348eb2da2a576f31b5` | EBS | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebde348eb2da2a576f31b5/tasks/view/all) |
| 18 | `5bed148f0f372c66c1d010e2` | ERP系统运维 | 2018-11-15 | [链接](https://i2m.gdalpha.com:4431/project/5bed148f0f372c66c1d010e2/tasks/view/all) |
| 19 | `5bebdc7d0f372c66c1cf3e30` | 费控项目运维 | 2018-11-14 | [链接](https://i2m.gdalpha.com:4431/project/5bebdc7d0f372c66c1cf3e30/tasks/view/all) |
| 20 | `5c4139485d1dcb645de14788` | 个人事项管理 | 2019-01-18 | [链接](https://i2m.gdalpha.com:4431/project/5c4139485d1dcb645de14788/tasks/view/all) |
| 21 | `5ce4f838b401e8268d189cae` | 供应链财务部系统优化 | 2019-05-22 | [链接](https://i2m.gdalpha.com:4431/project/5ce4f838b401e8268d189cae/tasks/view/all) |
| 22 | `60ebde818eb2da2a576f31f3` | HFM | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebde818eb2da2a576f31f3/tasks/view/all) |
| 23 | `60ebdecd8eb2da2a576f3231` | HEC | 2021-07-12 | [链接](https://i2m.gdalpha.com:4431/project/60ebdecd8eb2da2a576f3231/tasks/view/all) |
| 24 | `5bebdaaa21a70766c07aa6e3` | 合同管理系统项目 | 2018-11-14 | [链接](https://i2m.gdalpha.com:4431/project/5bebdaaa21a70766c07aa6e3/tasks/view/all) |
| 25 | `5db7f542e694981bb97ee5cd` | 会员系统及全渠道系统建设项目（金蝶） | 2019-10-29 | [链接](https://i2m.gdalpha.com:4431/project/5db7f542e694981bb97ee5cd/tasks/view/all) |
| 26 | `5c4a682a038e6b64627341e1` | I2M (xTB) 系统运维项目 | 2019-01-25 | [链接](https://i2m.gdalpha.com:4431/project/5c4a682a038e6b64627341e1/tasks/view/all) |
| 27 | `5cf5e10cb401e8268d454644` | IT系统运维-架构组 | 2019-06-04 | [链接](https://i2m.gdalpha.com:4431/project/5cf5e10cb401e8268d454644/tasks/view/all) |
| 28 | `5c07217bfda34052baae6feb` | IT系统运维-OA | 2018-12-05 | [链接](https://i2m.gdalpha.com:4431/project/5c07217bfda34052baae6feb/tasks/view/all) |
| 29 | `5d76f7e6e694981bb90116c7` | 架构组协助工作 | 2019-09-10 | [链接](https://i2m.gdalpha.com:4431/project/5d76f7e6e694981bb90116c7/tasks/view/all) |
| 30 | `61deb50c7ae9a39620b136d4` | 技术开发组人天 | 2022-01-12 | [链接](https://i2m.gdalpha.com:4431/project/61deb50c7ae9a39620b136d4/tasks/view/all) |
| 31 | `619316908eb2da2a5770c10f` | 技术研发 | 2021-11-16 | [链接](https://i2m.gdalpha.com:4431/project/619316908eb2da2a5770c10f/tasks/view/all) |
| 32 | `619318a68eb2da2a5770c163` | 技术研发 | 2021-11-16 | [链接](https://i2m.gdalpha.com:4431/project/619318a68eb2da2a5770c163/tasks/view/all) |
| 33 | `61e778307ae9a39620b160cd` | 技术研发 | 2022-01-19 | [链接](https://i2m.gdalpha.com:4431/project/61e778307ae9a39620b160cd/tasks/view/all) |
| 34 | `60dd8c1d8eb2da2a576ef800` | 技术中心敏捷开发 | 2021-07-01 | [链接](https://i2m.gdalpha.com:4431/project/60dd8c1d8eb2da2a576ef800/tasks/view/all) |
| 35 | `5c53bcd35d1dcb645dfffe1c` | 技术中心人天登记 | 2019-02-01 | [链接](https://i2m.gdalpha.com:4431/project/5c53bcd35d1dcb645dfffe1c/tasks/view/all) |
| 36 | `5c636f2e5d1dcb645d093d23` | 流程与信息管理部文件 | 2019-02-13 | [链接](https://i2m.gdalpha.com:4431/project/5c636f2e5d1dcb645d093d23/tasks/view/all) |
| 37 | `60dd913e8eb2da2a576ef80d` | 敏捷开发 | 2021-07-01 | [链接](https://i2m.gdalpha.com:4431/project/60dd913e8eb2da2a576ef80d/tasks/view/all) |
| 38 | `60dd92bd8eb2da2a576ef826` | 敏捷开发测试 | 2021-07-01 | [链接](https://i2m.gdalpha.com:4431/project/60dd92bd8eb2da2a576ef826/tasks/view/all) |
| 39 | `5bec08ad21a70766c07b319c` | 内销订单系统优化项目 | 2018-11-14 | [链接](https://i2m.gdalpha.com:4431/project/5bec08ad21a70766c07b319c/tasks/view/all) |
| 40 | `61d3bc9d7ae9a39620b107a1` | PS大屏 | 2022-01-04 | [链接](https://i2m.gdalpha.com:4431/project/61d3bc9d7ae9a39620b107a1/tasks/view/all) |
| 41 | `5bebde0e0f372c66c1cf4cb2` | 亲子乐园EBS对接 | 2018-11-14 | [链接](https://i2m.gdalpha.com:4431/project/5bebde0e0f372c66c1cf4cb2/tasks/view/all) |
| 42 | `64b8ff4f7ad8b6f61a746f07` | 售后系统 | 2023-07-20 | [链接](https://i2m.gdalpha.com:4431/project/64b8ff4f7ad8b6f61a746f07/tasks/view/all) |
| 43 | `5dedf2939c5ef56c10958404` | 商旅平台项目 | 2019-12-09 | [链接](https://i2m.gdalpha.com:4431/project/5dedf2939c5ef56c10958404/tasks/view/all) |
| 44 | `5c6e4cd0147c5e26f8031b6c` | SalesForce系统运维 | 2019-02-21 | [链接](https://i2m.gdalpha.com:4431/project/5c6e4cd0147c5e26f8031b6c/tasks/view/all) |
| 45 | `620b65f17ae9a39620b1bc4f` | 退货系统 | 2022-02-15 | [链接](https://i2m.gdalpha.com:4431/project/620b65f17ae9a39620b1bc4f/tasks/view/all) |
| 46 | `60e6912e8eb2da2a576f2abb` | 协同系统 | 2021-07-08 | [链接](https://i2m.gdalpha.com:4431/project/60e6912e8eb2da2a576f2abb/tasks/view/all) |
| 47 | `5f8e3efb2c2204030c3d2f65` | 新员工工作汇报 | 2020-10-20 | [链接](https://i2m.gdalpha.com:4431/project/5f8e3efb2c2204030c3d2f65/tasks/view/all) |
| 48 | `6524c4017ad8b6f61a74ae46` | 业务中台项目 | 2023-10-10 | [链接](https://i2m.gdalpha.com:4431/project/6524c4017ad8b6f61a74ae46/tasks/view/all) |
| 49 | `5c93499b147c5e26f8529953` | 运维组重点工作管理 | 2019-03-21 | [链接](https://i2m.gdalpha.com:4431/project/5c93499b147c5e26f8529953/tasks/view/all) |
| 50 | `619321fb8eb2da2a5770c254` | 自动补货系统 | 2021-11-16 | [链接](https://i2m.gdalpha.com:4431/project/619321fb8eb2da2a5770c254/tasks/view/all) |
| 51 | `5fb1dcdba18b330de28e1163` | 自动化测试项目 | 2020-11-16 | [链接](https://i2m.gdalpha.com:4431/project/5fb1dcdba18b330de28e1163/tasks/view/all) |
| 52 | `5bebd7ed0f372c66c1cf2250` | 资金系统运维 | 2018-11-14 | [链接](https://i2m.gdalpha.com:4431/project/5bebd7ed0f372c66c1cf2250/tasks/view/all) |
| 53 | `60dec2018eb2da2a576ef9c7` | 主题商业门户 | 2021-07-02 | [链接](https://i2m.gdalpha.com:4431/project/60dec2018eb2da2a576ef9c7/tasks/view/all) |

---

### 2.3 创建需求/任务（点击"完成"按钮触发）

- **请求方式**: `POST`
- **请求URL**: `/api/v2/tasks`
- **完整URL**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/tasks
  ```

#### 请求头

| 请求头 | 值 |
|--------|-----|
| Accept | `application/json, text/javascript, */*; q=0.01` |
| Content-Type | `application/json` |
| X-Requested-With | `XMLHttpRequest` |
| x-request-id | UUID格式请求标识 |

#### 请求体（Request Body）

```json
{
  "_projectId": "693907787ad8b6f61a76a0a6",
  "_tasklistId": "69390779798759002a458d74",
  "_stageId": "69390779798759002a458d75",
  "content": "测试",
  "_executorId": "5bea5a57be825b33ab9afacb",
  "dueDate": null,
  "priority": -10,
  "progress": 0,
  "recurrence": null,
  "reminders": [],
  "involveMembers": ["5bea5a57be825b33ab9afacb"],
  "involvers": [
    {
      "name": "李光华",
      "_id": "5bea5a57be825b33ab9afacb",
      "email": "echizen_hua@163.com",
      "avatarUrl": "..."
    }
  ],
  "visible": "members",
  "_scenariofieldconfigId": "693907797ad8b6f61a76a0be",
  "_taskflowstatusId": "69390779798759002a458d54",
  "tagIds": [],
  "note": "测试备注",
  "customfields": [
    {
      "type": "commongroup",
      "subtype": "story",
      "value": [{"_id": "69390779faa5ef001ad1912e", "title": "未分类需求"}],
      "_customfieldId": "5d1b3638ce9f165cd5d980b5"
    },
    {
      "value": [{"title": "测试"}],
      "_customfieldId": "693793de7ad8b6f61a769edc",
      "type": "text"
    },
    {
      "value": [{"_id": "665d864abf5f11b187aa5279", "title": "古妙霞", "description": "gumiaoxia@auldey.com"}],
      "_customfieldId": "693910667ad8b6f61a76a0fd",
      "type": "lookup"
    },
    {
      "value": [{"title": "6"}],
      "_customfieldId": "69b3e4407ad8b6f61a76ef3e",
      "type": "number"
    },
    {
      "value": [{"title": "2026-04-14T04:47:00.000Z"}],
      "_customfieldId": "69b21bbf7ad8b6f61a76ebe1",
      "type": "date"
    }
  ],
  "storyPoint": null,
  "workTime": {"totalTime": 0, "usedTime": 0, "unit": ""}
}
```

#### 请求参数说明

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| _projectId | string | 是 | 项目ID |
| _tasklistId | string | 是 | 任务列表ID |
| _stageId | string | 是 | 阶段ID |
| content | string | 是 | 需求标题/内容 |
| _executorId | string | 否 | 执行者用户ID |
| dueDate | string/null | 否 | 截止日期（ISO 8601格式） |
| priority | number | 否 | 优先级（-10=普通, 0=紧急, 1=非常紧急） |
| progress | number | 否 | 进度（0-100） |
| recurrence | string/null | 否 | 重复规则 |
| reminders | array | 否 | 提醒设置 |
| involveMembers | array | 否 | 参与者ID数组 |
| involvers | array | 否 | 参与者详细信息（含name, _id, email等） |
| visible | string | 否 | 可见性（`members`=仅成员可见） |
| _scenariofieldconfigId | string | 否 | 场景字段配置ID |
| _taskflowstatusId | string | 否 | 任务流程状态ID（如"待处理"） |
| tagIds | array | 否 | 标签ID数组 |
| note | string | 否 | 备注/描述 |
| customfields | array | 否 | 自定义字段数组 |
| storyPoint | number/null | 否 | 故事点数 |
| workTime | object | 否 | 工时信息 |

#### customfields 自定义字段说明

| _customfieldId | type | 说明 |
|----------------|------|------|
| `5d1b3638ce9f165cd5d980b5` | commongroup | 需求分类（如"未分类需求"） |
| `693793de7ad8b6f61a769edc` | text | 文本字段 |
| `693910667ad8b6f61a76a0fd` | lookup | 人员查找（关联人员，如"古妙霞"） |
| `69b3e4407ad8b6f61a76ef3e` | number | 数值字段 |
| `69b21bbf7ad8b6f61a76ebe1` | date | 日期字段 |

#### 响应格式

```json
{
  "_id": "69d48d6249a68c00312b5dd5",
  "_creatorId": "5bea5a57be825b33ab9afacb",
  "_executorId": "5bea5a57be825b33ab9afacb",
  "_projectId": "693907787ad8b6f61a76a0a6",
  "_tasklistId": "69390779798759002a458d74",
  "_stageId": "69390779798759002a458d75",
  "visible": "members",
  "involveMembers": ["5bea5a57be825b33ab9afacb"],
  "workTime": {"totalTime": 0, "usedTime": 0, "unit": "minute"},
  "updated": "2026-04-07T04:51:46.202Z",
  "created": "2026-04-07T04:51:46.202Z",
  "isArchived": false,
  "isDone": false,
  "priority": -10,
  "note": "测试备注",
  "content": "测试",
  "uniqueId": 365,
  "customfields": [...],
  "taskflowstatus": {
    "_id": "69390779798759002a458d54",
    "kind": "start",
    "name": "待处理"
  },
  "project": {
    "_id": "693907787ad8b6f61a76a0a6",
    "name": "奥飞财经系统"
  },
  "creator": {
    "_id": "5bea5a57be825b33ab9afacb",
    "name": "李光华"
  },
  "executor": {
    "_id": "5bea5a57be825b33ab9afacb",
    "name": "李光华"
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 新创建的任务/需求ID |
| _creatorId | string | 创建者ID |
| _executorId | string | 执行者ID |
| _projectId | string | 所属项目ID |
| _tasklistId | string | 所属任务列表ID |
| _stageId | string | 所属阶段ID |
| content | string | 需求标题 |
| note | string | 需求描述/备注 |
| isDone | boolean | 是否已完成 |
| priority | number | 优先级 |
| uniqueId | number | 项目内唯一编号 |
| created | string | 创建时间 |
| updated | string | 更新时间 |
| taskflowstatus | object | 当前工作流状态 |
| project | object | 所属项目信息 |
| creator | object | 创建者信息 |
| executor | object | 执行者信息 |
| customfields | array | 自定义字段值 |

---

### 2.4 创建需求/任务（点击"完成"按钮触发）

- **请求方式**: `POST`
- **请求URL**: `/api/v2/tasks`
- **完整URL**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/tasks
  ```

#### 请求头

| 请求头 | 值 |
|--------|-----|
| Accept | `application/json, text/javascript, */*; q=0.01` |
| Content-Type | `application/json` |
| X-Requested-With | `XMLHttpRequest` |
| x-request-id | UUID格式请求标识 |

#### 请求体（Request Body）

```json
{
  "_projectId": "693907787ad8b6f61a76a0a6",
  "_tasklistId": "69390779798759002a458d74",
  "_stageId": "69390779798759002a458d75",
  "content": "测试",
  "_executorId": "5bea5a57be825b33ab9afacb",
  "dueDate": null,
  "priority": -10,
  "progress": 0,
  "recurrence": null,
  "reminders": [],
  "involveMembers": ["5bea5a57be825b33ab9afacb"],
  "involvers": [
    {
      "name": "李光华",
      "_id": "5bea5a57be825b33ab9afacb",
      "email": "echizen_hua@163.com",
      "avatarUrl": "..."
    }
  ],
  "visible": "members",
  "_scenariofieldconfigId": "693907797ad8b6f61a76a0be",
  "_taskflowstatusId": "69390779798759002a458d54",
  "tagIds": [],
  "note": "测试备注",
  "customfields": [
    {
      "type": "commongroup",
      "subtype": "story",
      "value": [{"_id": "69390779faa5ef001ad1912e", "title": "未分类需求"}],
      "_customfieldId": "5d1b3638ce9f165cd5d980b5"
    },
    {
      "value": [{"title": "测试"}],
      "_customfieldId": "693793de7ad8b6f61a769edc",
      "type": "text"
    },
    {
      "value": [{"_id": "665d864abf5f11b187aa5279", "title": "古妙霞", "description": "gumiaoxia@auldey.com"}],
      "_customfieldId": "693910667ad8b6f61a76a0fd",
      "type": "lookup"
    },
    {
      "value": [{"title": "6"}],
      "_customfieldId": "69b3e4407ad8b6f61a76ef3e",
      "type": "number"
    },
    {
      "value": [{"title": "2026-04-14T04:47:00.000Z"}],
      "_customfieldId": "69b21bbf7ad8b6f61a76ebe1",
      "type": "date"
    }
  ],
  "storyPoint": null,
  "workTime": {"totalTime": 0, "usedTime": 0, "unit": ""}
}
```

#### 请求参数说明

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| _projectId | string | 是 | 项目ID |
| _tasklistId | string | 是 | 任务列表ID |
| _stageId | string | 是 | 阶段ID |
| content | string | 是 | 需求标题/内容 |
| _executorId | string | 否 | 执行者用户ID |
| dueDate | string/null | 否 | 截止日期（ISO 8601格式） |
| priority | number | 否 | 优先级（-10=普通, 0=紧急, 1=非常紧急） |
| progress | number | 否 | 进度（0-100） |
| recurrence | string/null | 否 | 重复规则 |
| reminders | array | 否 | 提醒设置 |
| involveMembers | array | 否 | 参与者ID数组 |
| involvers | array | 否 | 参与者详细信息（含name, _id, email等） |
| visible | string | 否 | 可见性（`members`=仅成员可见） |
| _scenariofieldconfigId | string | 否 | 场景字段配置ID |
| _taskflowstatusId | string | 否 | 任务流程状态ID（如"待处理"） |
| tagIds | array | 否 | 标签ID数组 |
| note | string | 否 | 备注/描述 |
| customfields | array | 否 | 自定义字段数组 |
| storyPoint | number/null | 否 | 故事点数 |
| workTime | object | 否 | 工时信息 |

#### customfields 自定义字段说明

| _customfieldId | type | 说明 |
|----------------|------|------|
| `5d1b3638ce9f165cd5d980b5` | commongroup | 需求分类（如"未分类需求"） |
| `693793de7ad8b6f61a769edc` | text | 文本字段 |
| `693910667ad8b6f61a76a0fd` | lookup | 人员查找（关联人员，如"古妙霞"） |
| `69b3e4407ad8b6f61a76ef3e` | number | 数值字段 |
| `69b21bbf7ad8b6f61a76ebe1` | date | 日期字段 |

#### 响应格式

```json
{
  "_id": "69d48d6249a68c00312b5dd5",
  "_creatorId": "5bea5a57be825b33ab9afacb",
  "_executorId": "5bea5a57be825b33ab9afacb",
  "_projectId": "693907787ad8b6f61a76a0a6",
  "_tasklistId": "69390779798759002a458d74",
  "_stageId": "69390779798759002a458d75",
  "visible": "members",
  "involveMembers": ["5bea5a57be825b33ab9afacb"],
  "workTime": {"totalTime": 0, "usedTime": 0, "unit": "minute"},
  "updated": "2026-04-07T04:51:46.202Z",
  "created": "2026-04-07T04:51:46.202Z",
  "isArchived": false,
  "isDone": false,
  "priority": -10,
  "note": "测试备注",
  "content": "测试",
  "uniqueId": 365,
  "customfields": [...],
  "taskflowstatus": {
    "_id": "69390779798759002a458d54",
    "kind": "start",
    "name": "待处理"
  },
  "project": {
    "_id": "693907787ad8b6f61a76a0a6",
    "name": "奥飞财经系统"
  },
  "creator": {
    "_id": "5bea5a57be825b33ab9afacb",
    "name": "李光华"
  },
  "executor": {
    "_id": "5bea5a57be825b33ab9afacb",
    "name": "李光华"
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 新创建的任务/需求ID |
| _creatorId | string | 创建者ID |
| _executorId | string | 执行者ID |
| _projectId | string | 所属项目ID |
| _tasklistId | string | 所属任务列表ID |
| _stageId | string | 所属阶段ID |
| content | string | 需求标题 |
| note | string | 需求描述/备注 |
| isDone | boolean | 是否已完成 |
| priority | number | 优先级 |
| uniqueId | number | 项目内唯一编号 |
| created | string | 创建时间 |
| updated | string | 更新时间 |
| taskflowstatus | object | 当前工作流状态 |
| project | object | 所属项目信息 |
| creator | object | 创建者信息 |
| executor | object | 执行者信息 |
| customfields | array | 自定义字段值 |

---

### 2.3.1 编辑需求自定义字段（点击"保存"按钮触发）

- **请求方式**: `PUT`
- **请求URL**: `/api/tasks/{taskId}/customfields`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/tasks/69d48e5a798759002a5aaccd/customfields
  ```

#### 请求头

| 请求头 | 值 |
|--------|-----|
| Accept | `application/json, text/javascript, */*; q=0.01` |
| Content-Type | `application/json` |
| X-Requested-With | `XMLHttpRequest` |
| x-request-id | UUID格式请求标识 |

#### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| taskId | string | 是 | 任务/需求ID |

#### 请求体（Request Body）

```json
{
  "value": [{"title": "6"}],
  "_customfieldId": "69b3e4407ad8b6f61a76ef3e"
}
```

#### 请求参数说明

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| value | array | 是 | 字段值数组，每个元素包含title（值内容） |
| _customfieldId | string | 是 | 自定义字段ID |

> **注意**：每次保存只提交被修改的那一个自定义字段，不需要提交全部字段。

#### 自定义字段ID对照表（奥飞财经系统项目）

| _customfieldId | type | 字段名称 | 值格式示例 |
|----------------|------|----------|-----------|
| `5d1b3638ce9f165cd5d980b5` | commongroup | 需求分类 | `[{"_id":"...", "title":"未分类需求"}]` |
| `693910667ad8b6f61a76a0fd` | lookup | 人员（如联系人） | `[{"_id":"...", "title":"古妙霞", "description":"邮箱"}]` |
| `69b21bbf7ad8b6f61a76ebe1` | date | 日期字段 | `[{"title":"2026-04-17T04:56:00.000Z"}]` |
| `693793de7ad8b6f61a769edc` | text | 文本字段 | `[{"title":"很高"}]` |
| `693922107ad8b6f61a76a168` | dropDown | 下拉选择（如系统类型） | `[{"_id":"...", "title":"ERP"}]` |
| `69b3e4407ad8b6f61a76ef3e` | number | 数值字段（如开发人天） | `[{"title":"6"}]` |

#### 响应格式

```json
{
  "customfields": [
    {
      "values": [],
      "value": [{"_id": "69390779faa5ef001ad1912e", "title": "未分类需求"}],
      "_customfieldId": "5d1b3638ce9f165cd5d980b5",
      "type": "commongroup"
    },
    {
      "values": [],
      "value": [{"_id": "665d864abf5f11b187aa5279", "title": "古妙霞", "description": "gumiaoxia@auldey.com"}],
      "_customfieldId": "693910667ad8b6f61a76a0fd",
      "type": "lookup"
    },
    {
      "values": ["2026-04-17T04:56:00.000Z"],
      "value": [{"title": "2026-04-17T04:56:00.000Z"}],
      "_customfieldId": "69b21bbf7ad8b6f61a76ebe1",
      "type": "date"
    },
    {
      "values": ["很高"],
      "value": [{"title": "很高"}],
      "_customfieldId": "693793de7ad8b6f61a769edc",
      "type": "text"
    },
    {
      "values": ["693922107ad8b6f61a76a169"],
      "value": [{"_id": "693922107ad8b6f61a76a169", "title": "ERP"}],
      "_customfieldId": "693922107ad8b6f61a76a168",
      "type": "dropDown"
    },
    {
      "values": ["6"],
      "value": [{"title": "6"}],
      "_customfieldId": "69b3e4407ad8b6f61a76ef3e",
      "type": "number"
    }
  ],
  "updated": "2026-04-07T05:01:37.187Z"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| customfields | array | 该任务所有自定义字段的最新值 |
| customfields[].values | array | 旧格式的值（向后兼容） |
| customfields[].value | array | 新格式的值（推荐使用） |
| customfields[]._customfieldId | string | 自定义字段ID |
| customfields[].type | string | 字段类型（commongroup/lookup/date/text/dropDown/number等） |
| updated | string | 更新时间（ISO 8601格式） |

---

### 2.3.2 查询任务/需求详情（点击任务标题触发）

- **请求方式**: `GET`
- **请求URL**: `/api/tasks/{taskId}`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/tasks/69d48e5a798759002a5aaccd
  ```

#### 请求头

| 请求头 | 值 |
|--------|-----|
| Accept | `application/json` |
| X-Requested-With | `XMLHttpRequest` |

#### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| taskId | string | 是 | 任务/需求ID |

#### 响应格式

```json
{
  "_id": "69d48e5a798759002a5aaccd",
  "_creatorId": "5bea5a57be825b33ab9afacb",
  "_executorId": "5bea5a57be825b33ab9afacb",
  "_projectId": "693907787ad8b6f61a76a0a6",
  "_tasklistId": "69390779798759002a458d74",
  "_organizationId": null,
  "tagIds": [],
  "_stageId": "69390779798759002a458d75",
  "visible": "members",
  "involveMembers": ["5bea5a57be825b33ab9afacb"],
  "workTime": {"totalTime": 0, "usedTime": 0, "unit": "minute"},
  "updated": "2026-04-07T05:01:37.187Z",
  "created": "2026-04-07T04:55:54.888Z",
  "isArchived": false,
  "isDone": false,
  "isTopInProject": false,
  "priority": -10,
  "pos": 7487488,
  "startDate": null,
  "dueDate": null,
  "accomplished": null,
  "note": "这是通过API直接调用创建的测试需求，用于验证接口文档的正确性",
  "content": "API测试需求-自动创建",
  "recurrence": null,
  "subtasks": [],
  "ancestorIds": [],
  "customfields": [
    {
      "values": [],
      "value": [{"_id": "69390779faa5ef001ad1912e", "title": "未分类需求"}],
      "_customfieldId": "5d1b3638ce9f165cd5d980b5",
      "type": "commongroup"
    },
    {
      "values": [],
      "value": [{"_id": "665d864abf5f11b187aa5279", "title": "古妙霞", "description": "gumiaoxia@auldey.com"}],
      "_customfieldId": "693910667ad8b6f61a76a0fd",
      "type": "lookup",
      "objectType": "teambition.member"
    },
    {
      "values": ["2026-04-17T04:56:00.000Z"],
      "value": [{"title": "2026-04-17T04:56:00.000Z"}],
      "_customfieldId": "69b21bbf7ad8b6f61a76ebe1",
      "type": "date"
    },
    {
      "values": ["很高"],
      "value": [{"title": "很高"}],
      "_customfieldId": "693793de7ad8b6f61a769edc",
      "type": "text"
    },
    {
      "values": ["693922107ad8b6f61a76a169"],
      "value": [{"_id": "693922107ad8b6f61a76a169", "title": "ERP"}],
      "_customfieldId": "693922107ad8b6f61a76a168",
      "type": "dropDown"
    },
    {
      "values": ["6"],
      "value": [{"title": "6"}],
      "_customfieldId": "69b3e4407ad8b6f61a76ef3e",
      "type": "number"
    }
  ],
  "commentsCount": 0,
  "attachmentsCount": 0,
  "likesCount": 0,
  "objectlinksCount": 0,
  "uniqueId": 366,
  "badges": {"commentsCount": 0, "attachmentsCount": 0, "likesCount": 0, "objectlinksCount": 0},
  "subtaskCount": {"total": 0, "done": 0},
  "reminder": {"type": "unset", "date": null, "memberRoles": [], "members": [], "method": "popup"},
  "storyPoint": null,
  "progress": 0,
  "rating": 0,
  "isFavorite": false,
  "_scenariofieldconfigId": "693907797ad8b6f61a76a0be",
  "shareStatus": 0,
  "_sprintId": null,
  "_taskflowstatusId": "69390779798759002a458d54",
  "effort": null,
  "objectType": "task",
  "source": "teambition",
  "labels": [],
  "relations": [],
  "project": {
    "_id": "693907787ad8b6f61a76a0a6",
    "name": "奥飞财经系统",
    "uniqueIdPrefix": "WUFN",
    "_organizationId": "5be50c1ebe825b60a7ad0894"
  },
  "stage": {"_id": "69390779798759002a458d75", "name": "默认列表"},
  "tasklist": {"_id": "69390779798759002a458d74", "title": "任务"},
  "taskflowstatus": {
    "_id": "69390779798759002a458d54",
    "name": "待处理",
    "kind": "start",
    "_taskflowId": "69390779798759002a458d51"
  },
  "scenariofieldconfig": {
    "_id": "693907797ad8b6f61a76a0be",
    "name": "需求",
    "icon": "requirement",
    "proTemplateConfigType": "story"
  },
  "creator": {"_id": "5bea5a57be825b33ab9afacb", "name": "李光华"},
  "executor": {"_id": "5bea5a57be825b33ab9afacb", "name": "李光华"},
  "involvers": [{"_id": "5bea5a57be825b33ab9afacb", "name": "李光华"}]
}
```

#### 响应字段说明

**基础字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 任务/需求唯一ID |
| _creatorId | string | 创建者用户ID |
| _executorId | string | 执行者用户ID |
| _projectId | string | 所属项目ID |
| _tasklistId | string | 所属任务列表ID |
| _stageId | string | 所属阶段ID |
| _organizationId | string/null | 所属组织ID |
| _scenariofieldconfigId | string | 场景字段配置ID（需求/任务/缺陷等） |
| _taskflowstatusId | string | 当前工作流状态ID |
| _sprintId | string/null | 所属迭代ID |

**内容字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | 任务标题 |
| note | string | 备注/描述 |
| uniqueId | number | 项目内唯一编号（如WUFN-366） |
| objectType | string | 对象类型（固定"task"） |
| source | string | 来源（如"teambition"） |

**状态字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| isDone | boolean | 是否已完成 |
| isArchived | boolean | 是否已归档 |
| isTopInProject | boolean | 是否置顶 |
| priority | number | 优先级（-10=较低, 0=普通, 1=紧急, 2=非常紧急） |
| progress | number | 进度（0-100） |
| pos | number | 排序位置 |

**时间字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| created | string | 创建时间（ISO 8601） |
| updated | string | 最后更新时间（ISO 8601） |
| startDate | string/null | 开始日期 |
| dueDate | string/null | 截止日期 |
| accomplished | string/null | 完成时间 |

**人员字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| visible | string | 可见性（members=仅成员） |
| involveMembers | array | 参与者ID数组 |
| tagIds | array | 标签ID数组 |
| creator | object | 创建者（含_id, name, avatarUrl） |
| executor | object | 执行者（含_id, name, avatarUrl） |
| involvers | array | 参与者详情数组 |

**关联对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| project | object | 所属项目（含_id, name, uniqueIdPrefix, _organizationId） |
| stage | object | 所属阶段（含_id, name） |
| tasklist | object | 所属任务列表（含_id, title） |
| taskflowstatus | object | 工作流状态（含_id, name, kind, _taskflowId） |
| scenariofieldconfig | object | 场景配置（含_id, name, icon, proTemplateConfigType） |
| subtasks | array | 子任务列表 |
| subtaskCount | object | 子任务统计（total, done） |

**自定义字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| customfields | array | 自定义字段数组（详见2.3.1节自定义字段ID对照表） |

**工时与统计**

| 字段 | 类型 | 说明 |
|------|------|------|
| workTime | object | 工时信息（totalTime, usedTime, unit） |
| storyPoint | number/null | 故事点数 |
| rating | number | 评分 |
| commentsCount | number | 评论数 |
| attachmentsCount | number | 附件数 |
| likesCount | number | 点赞数 |

**其他字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| isFavorite | boolean | 是否收藏 |
| shareStatus | number | 分享状态 |
| recurrence | string/null | 重复规则 |
| reminder | object | 提醒设置 |
| labels | array | 标签列表 |
| relations | array | 关联关系列表 |

> **使用提示**：查询到的字段可直接用于编辑接口。编辑基础字段使用 `PUT /api/tasks/{taskId}`，编辑自定义字段使用 `PUT /api/tasks/{taskId}/customfields`（见2.3.1节）。

---

### 2.3.3 删除任务/需求（移到回收站）

- **请求方式**: `POST`
- **请求URL**: `/api/tasks/{taskId}/archive`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/tasks/69d4938e8e2e9a001c178cdc/archive
  ```

#### 请求头

| 请求头 | 值 |
|--------|-----|
| Accept | `application/json, text/javascript, */*; q=0.01` |
| Content-Type | `application/json` |
| X-Requested-With | `XMLHttpRequest` |
| x-request-id | UUID格式请求标识 |

#### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| taskId | string | 是 | 任务/需求ID |

#### 请求体

```json
{}
```

> **注意**：请求体为空JSON对象。

#### 响应格式

```json
{
  "_id": "69d4938e8e2e9a001c178cdc",
  "isArchived": true,
  "_projectId": "65efbd2d7ad8b6f61a7516a1",
  "updated": "2026-04-07T05:24:14.112Z"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 被删除的任务ID |
| isArchived | boolean | 归档状态（true=已移到回收站） |
| _projectId | string | 所属项目ID |
| updated | string | 操作时间 |

> **说明**：此操作是"软删除"，任务移到回收站后可恢复。回收站中的任务在一定时间后会被永久删除。

---

### 2.3.3 删除任务/需求（移到回收站）

- **请求方式**: `POST`
- **请求URL**: `/api/tasks/{taskId}/archive`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/tasks/69d4938e8e2e9a001c178cdc/archive
  ```

#### 请求头

| 请求头 | 值 |
|--------|-----|
| Accept | `application/json, text/javascript, */*; q=0.01` |
| Content-Type | `application/json` |
| X-Requested-With | `XMLHttpRequest` |
| x-request-id | UUID格式请求标识 |

#### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| taskId | string | 是 | 任务/需求ID |

#### 请求体

```json
{}
```

> **注意**：请求体为空JSON对象。

#### 响应格式

```json
{
  "_id": "69d4938e8e2e9a001c178cdc",
  "isArchived": true,
  "_projectId": "65efbd2d7ad8b6f61a7516a1",
  "updated": "2026-04-07T05:24:14.112Z"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 被删除的任务ID |
| isArchived | boolean | 归档状态（true=已移到回收站） |
| _projectId | string | 所属项目ID |
| updated | string | 操作时间 |

> **说明**：此操作是"软删除"，任务移到回收站后可恢复。回收站中的任务在一定时间后会被永久删除。

---

### 2.4 获取权限列表

- **请求方式**: `GET`
- **请求URL**: `/api/permissions`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/permissions
  ```
- **响应格式**: JSON数组，包含当前用户拥有的所有权限字符串

---

### 2.5 获取项目订阅信息

- **请求方式**: `GET`
- **请求URL**: `/api/projects/subscribe`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/projects/subscribe
  ```

---

### 2.6 获取组织项目数量统计

- **请求方式**: `GET`
- **请求URL**: `/api/organizations/{orgId}/projects/count`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/organizations/5be50c1ebe825b60a7ad0894/projects/count
  ```

---

### 2.7 获取组织角色列表

- **请求方式**: `GET`
- **请求URL**: `/api/v2/roles`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/roles?type=organization
  ```

---

## 3. 请求头说明

所有API请求需要携带的通用请求头：

| 请求头 | 说明 |
|--------|------|
| Content-Type | `application/json` |
| accept | `application/json` |
| x-request-id | 请求唯一标识（UUID格式） |
| x-timezone | 时区偏移量，如 `8` |

> **认证方式**: 通过浏览器Cookie自动携带身份信息（Session-based authentication）

---

## 4. 分页机制

Teambition API 使用 `pageToken` 进行游标分页：

- 首次请求：`pageToken` 为空字符串
- 后续请求：使用上一次响应中的 `nextPageToken` 值
- 无更多数据：`nextPageToken` 为空字符串
- `pageSize` 控制每页返回数量

---

## 5. 项目配置查询API

### 5.1 获取项目任务列表

- **请求方式**: `GET`
- **请求URL**: `/api/tasklists?_projectId={projectId}`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/tasklists?_projectId=65efbd2d7ad8b6f61a7516a1
  ```

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| _projectId | string | 是 | 项目ID |

#### 响应示例

```json
[
  {
    "_id": "65efbd2fd4393f0057b6d710",
    "title": "任务",
    "_projectId": "65efbd2d7ad8b6f61a7516a1",
    "isArchived": false,
    "stageIds": ["65efbd2fd4393f0057b6d711"],
    "undoneCount": 366,
    "doneCount": 841,
    "totalCount": 1207,
    "hasStages": [
      {
        "_id": "65efbd2fd4393f0057b6d711",
        "name": "默认列表",
        "_tasklistId": "65efbd2fd4393f0057b6d710"
      }
    ]
  }
]
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 任务列表ID（创建任务时的 `_tasklistId`） |
| title | string | 列表名称 |
| stageIds | array | 阶段ID数组 |
| undoneCount | number | 未完成任务数 |
| doneCount | number | 已完成任务数 |
| hasStages | array | 阶段详情（含 `_id` 作为 `_stageId`） |

---

### 5.2 获取项目场景字段配置

- **请求方式**: `GET`
- **请求URL**: `/api/v2/projects/{projectId}/scenariofieldconfigs`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/projects/65efbd2d7ad8b6f61a7516a1/scenariofieldconfigs
  ```

#### 响应示例（关键字段）

```json
[
  {
    "_id": "65efbd2f7ad8b6f61a7516b9",
    "name": "需求",
    "icon": "requirement",
    "proTemplateConfigType": "story",
    "_taskflowId": "65efbd2ed4393f0057b6d6ed",
    "_appId": "5d1b36b0be825b3902a8710d",
    "basicfields": [
      {"fieldType": "executor", "required": false},
      {"fieldType": "startDate", "required": false},
      {"fieldType": "dueDate", "required": false}
    ],
    "scenariofields": [
      {
        "_customfieldId": "693793de7ad8b6f61a769edc",
        "fieldType": "customfield",
        "displayed": false,
        "required": true
      }
    ]
  },
  {
    "_id": "65efbd2f7ad8b6f61a7516c1",
    "name": "任务",
    "icon": "task",
    "proTemplateConfigType": "subtask"
  },
  {
    "_id": "65efbd2f7ad8b6f61a7516d4",
    "name": "缺陷",
    "icon": "bug",
    "proTemplateConfigType": "bug"
  }
]
```

#### 关键用途

| 字段 | 用于 |
|------|------|
| `_id` | 创建任务时的 `_scenariofieldconfigId` |
| `_taskflowId` | 查询工作流状态 |
| `scenariofields[].required` | 判断哪些自定义字段必填 |
| `scenariofields[]._customfieldId` | 关联自定义字段定义 |

---

### 5.3 获取自定义字段定义（含可选项）

- **请求方式**: `GET`
- **请求URL**: `/api/v2/customfields/{customfieldId}`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/customfields/69ca2ba47ad8b6f61a76ff2f
  ```

#### 响应示例

```json
{
  "_id": "69ca2ba47ad8b6f61a76ff2f",
  "name": "产品经理",
  "type": "dropDown",
  "description": "主题商业门户",
  "choices": [
    {"_id": "60e2782a8eb2da2a576efc3a", "value": "林树煌"},
    {"_id": "60e2782a8eb2da2a576efc3b", "value": "蔡智键"},
    {"_id": "60e2782a8eb2da2a576efc3c", "value": "李光华"},
    {"_id": "69046a377ad8b6f61a766c0e", "value": "颜华艳"},
    {"_id": "69046a377ad8b6f61a766c0f", "value": "聂春杰"}
  ],
  "_organizationId": "5be50c1ebe825b60a7ad0894"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | string | 自定义字段ID |
| name | string | 字段显示名称 |
| type | string | 字段类型（text/number/date/dropDown/multipleChoice/lookup/commongroup等） |
| description | string | 字段描述 |
| choices | array | 可选项列表（仅dropDown/multipleChoice类型） |
| choices[]._id | string | 选项ID（设置值时需要） |
| choices[].value | string | 选项显示文本 |

---

### 5.4 搜索组织成员

- **请求方式**: `GET`
- **请求URL**: `/api/v2/organizations/{orgId}/members`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/organizations/5be50c1ebe825b60a7ad0894/members?pageSize=200&keyword=徐向荣
  ```

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pageSize | number | 否 | 每页数量 |
| keyword | string | 否 | 搜索关键词（按姓名搜索） |

#### 响应示例

```json
[
  {
    "_id": "5d071e50be825b6b0a9f4cce",
    "_userId": "5d071e50be825b283f9209d2",
    "name": "徐向荣",
    "email": "m17611225737@163.com",
    "role": "member",
    "isDisabled": false,
    "profile": {
      "name": "徐向荣",
      "_id": "5d071e50be825b6b0a9f4cca",
      "email": "m17611225737@163.com"
    }
  }
]
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| _userId | string | 用户ID（用于lookup类型字段的 `_id` 值） |
| name | string | 成员姓名 |
| email | string | 邮箱 |
| role | string | 组织角色 |
| isDisabled | boolean | 是否禁用 |
| profile | object | 用户详细资料 |

---

### 5.5 获取工作流详情

- **请求方式**: `GET`
- **请求URL**: `/api/taskflows/{taskflowId}`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/taskflows/65efbd2ed4393f0057b6d6ed
  ```

#### 响应示例

```json
{
  "_id": "65efbd2ed4393f0057b6d6ed",
  "name": "任务",
  "boundToObjectType": "project",
  "_boundToObjectId": "65efbd2d7ad8b6f61a7516a1",
  "objectType": "task"
}
```

> **注意**: 工作流状态ID（`_taskflowstatusId`）目前无法通过独立API直接查询，需从已有任务的详情中获取。建议通过 `GET /api/v2/tasks?_projectId={id}&isDone=false&pageSize=1` 获取。

---

### 5.6 获取项目任务列表（分页查询）

- **请求方式**: `GET`
- **请求URL**: `/api/v2/tasks?_projectId={projectId}`
- **完整URL示例**: 
  ```
  https://i2m.gdalpha.com:4431/api/v2/tasks?_projectId=65efbd2d7ad8b6f61a7516a1&isDone=false&pageSize=1
  ```

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| _projectId | string | 是 | 项目ID |
| isDone | boolean | 否 | 是否已完成 |
| pageSize | number | 否 | 每页数量 |
| pageToken | string | 否 | 分页游标 |

#### 响应格式

```json
{
  "nextPageToken": "...",
  "count": 403,
  "result": [
    {
      "_id": "任务ID",
      "content": "任务标题",
      "_taskflowstatusId": "状态ID",
      "taskflowstatus": {"_id": "...", "name": "待开发", "kind": "start"},
      ...
    }
  ]
}
```

---

## 6. 跨项目创建任务完整流程

### 步骤说明

```
1. 确定目标项目ID（从 2.2 我参与的项目 或 2.8 项目列表中获取）
2. GET /api/tasklists?_projectId={id}           → 获取 _tasklistId 和 _stageId
3. GET /api/v2/projects/{id}/scenariofieldconfigs → 获取 _scenariofieldconfigId 和必填字段
4. GET /api/v2/customfields/{fieldId}            → 查看dropDown/multipleChoice的可选项
5. GET /api/v2/tasks?_projectId={id}&isDone=false&pageSize=1 → 获取 _taskflowstatusId
6. POST /api/v2/tasks                            → 创建任务
7. PUT /api/tasks/{taskId}/customfields           → 补充/修改自定义字段（可选）
```

### 不同项目的关键配置参数

| 项目 | projectId | tasklistId | stageId | scenariofieldconfigId | taskflowstatusId（初始） |
|------|-----------|------------|---------|----------------------|------------------------|
| 奥飞财经系统 | `693907787ad8b6f61a76a0a6` | `69390779798759002a458d74` | `69390779798759002a458d75` | `693907797ad8b6f61a76a0be` | `69390779798759002a458d54`（待处理） |
| 奥飞业务中台系统 | `65efbd2d7ad8b6f61a7516a1` | `65efbd2fd4393f0057b6d710` | `65efbd2fd4393f0057b6d711` | `65efbd2f7ad8b6f61a7516b9` | `690b252049a68c00310f4a54`（待开发） |
