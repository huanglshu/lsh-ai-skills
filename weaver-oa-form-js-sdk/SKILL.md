---
name: weaver-oa-form-js-sdk
description: 处理泛微 OA 流程表单 JS 代码块、WfForm API、custompage、自定义事件、字段联动和明细表逻辑时，优先检索本地 SDK 文档并按表单代码块场景输出可直接使用的 JS 方案。
---

# Weaver OA Form JS SDK

用于处理泛微 OA 流程表单前端低代码开发中的 JS 代码块问题。

## 何时使用

- 用户要求编写或修改泛微 OA 表单 JS 代码块。
- 用户提到 `WfForm`、`custompage`、`代码块`、`字段联动`、`明细表`、`注册事件`、`浏览按钮`、`EM7`、`移动端兼容`。
- 用户要做流程表单前端调试、字段控制、事件拦截、联动渲染。

## 必须遵循的参考路径

- 默认参考文档：`./sdk-doc/泛微在线文档前端SDK.html`（相对于 skill 根目录）
- 若该路径不存在，明确说明本地 SDK 文档缺失，再退回通用经验分析。

## 工作流

1. 先确认用户需求属于哪类：
   - 字段基础操作
   - 自定义事件
   - 字段绑定/渲染
   - 明细表操作
   - 全局接口
   - 特定字段类型接口
2. 优先执行：

```bash
python3 scripts/search_sdk.py 关键词1 关键词2
```

3. 依据命中的 SDK 片段选择 `WfForm` 官方接口，不直接建议原生 DOM 操作。
4. 输出时优先给：
   - 可直接粘贴到代码块的 JS 示例
   - 适用场景说明
   - PC/移动端差异
   - **字段标识格式：`field${fieldId}`（主表）、`field${fieldId}_${rowIndex}`（明细表），fieldId 必须通过 `WfForm.convertFieldNameToId(fieldName, detailMark)` 从数据库字段名动态转换，禁止硬编码**

## 强制约束

- 优先使用 `window.WfForm` 官方 API。
- **字段标识必须从数据库字段名转换**：禁止在脚本中硬编码 `fieldId`（如 `field27584`），因为 fieldId 在不同环境（SIT/UAT/生产）不一致。必须使用 `WfForm.convertFieldNameToId(fieldName, detailMark)` 将数据库字段名动态转换为 fieldId。脚本中只暴露数据库字段名作为配置项。
- 不推荐 jQuery；禁止建议直接操作表单底层 DOM 结构，除非用户明确要求兼容历史代码。
- 遇到移动端相关场景，先判断 `WfForm.isMobile()`。
- 如果是路径管理 `custompage` 场景，提醒：
  - 方式二、方式三禁止引入 `init_wev8.js`
  - 全局 custompage 避免定义 `ready`、`checkCustomize` 等全局函数壳

## 最佳实践

### 1. 字段标识

- 配置项永远使用**数据库字段名**（如 `"contractCode"`），不用 fieldId
- 代码内部通过 `WfForm.convertFieldNameToId(fieldName, detailMark)` 运行时转换
- 主表字段用 `"main"` 作为第二个参数：`convertFieldNameToId("fieldName", "main")`
- 明细表字段用 `"detail_1"` 等：`convertFieldNameToId("fieldName", "detail_1")`

### 2. 测试先行

- 涉及行号判断的逻辑（如行权限），先写**测试模式**（奇偶行控制），验证事件绑定、渲染时机正确后，再切换正式逻辑
- 测试模式用 `var TEST_MODE = true` 开关，一键切换

### 3. 批量操作优于逐行

- 设置勾选框状态：先 `"all", false` 释放全部，再对目标行批量设置，避免逐行调用 API
- 明细行遍历：用 `getDetailAllRowIndexStr` 获取所有行标，一次性遍历

### 4. 初始化时机

- 页面加载用 `setTimeout(fn, 200)` 延迟执行，确保明细表 DOM 渲染完毕
- 同时监听 `registerAction(ACTION_ADDROW, fn)`，如果明细表先渲染完则提前触发初始化

### 5. 编辑权限 ≠ 删除权限

- 控制字段编辑：`changeFieldAttr(fieldMark, 1/2)` → 1=只读，2=可编辑
- 控制行删除：`controlDetailRowDisableCheck(detailMark, rowIndex, true/false)` → 禁用/启用勾选框
- 不可编辑的行通常也应不可删除，两者需分别控制

### 6. 新增行默认状态

- 新增行时，字段值通常为空，应默认设为只读 + 禁删
- 正式模式下，监听经办人等关键字段的 `bindDetailFieldChangeEvent`，值变化时重新校验

### 7. 兜底处理

- `convertFieldNameToId` 可能因字段名错误返回 null，需要 try-catch + 空值校验
- `changeFieldAttr` 操作不存在的行会抛异常，需要 try-catch

## 常见场景模板

### 场景 A：明细表行权限控制

需求：根据明细表某字段值（如经办人工号）与当前登录人比对，控制行编辑和删除权限。

核心 API：
- `changeFieldAttr` — 控制字段只读/可编辑
- `controlDetailRowDisableCheck` — 控制行勾选框（不可删除）
- `getDetailRowSerailNum` — 获取行序号（测试模式奇偶判断）
- `getDetailAllRowIndexStr` — 遍历所有行
- `registerAction(ACTION_ADDROW)` — 新增行后设置权限
- `registerAction(ACTION_DELROW)` — 删除行后刷新权限
- `bindDetailFieldChangeEvent` — 关键字段值变化时重新校验
- `getGlobalStore().commonParam` — 获取当前登录人信息

### 场景 B：明细表合计校验

需求：明细表某字段合计与主表字段比对，不一致时弹框提示。

核心 API：
- `getFieldValue` — 获取主表字段值
- `getDetailAllRowIndexStr` — 遍历明细行累加
- `showMessage` — 弹框提示
- `bindDetailFieldChangeEvent` — 明细值变化时重新计算
- `registerAction(ACTION_ADDROW/ACTION_DELROW)` — 增删行时重新计算
- `registerCheckEvent(OPER_SAVE/OPER_SUBMIT)` — 提交时阻断

### 场景 C：主表字段联动明细表

需求：主表字段值变化时，明细表新增行自动带出默认值。

核心 API：
- `bindFieldChangeEvent` — 主表字段值变化触发
- `registerAction(ACTION_ADDROW)` — 新增行时设置默认值
- `changeFieldValue` — 给明细字段赋值
- `setDetailAddUseCopy` — 新增行复制上一行（可选）

### 场景 D：提交前校验

需求：提交/保存前校验明细表数据完整性。

核心 API：
- `registerCheckEvent(OPER_SAVE/OPER_SUBMIT, callback)` — 拦截提交，callback 放行，不调用阻断
- `getDetailAllRowIndexStr` — 遍历明细行校验
- `getFieldValue` — 获取字段值判断
- `showMessage` — 阻断时提示原因

## 常用检索关键词

### 按功能分类
- 事件：`registerCheckEvent`, `registerAction`, `bindFieldChangeEvent`, `bindDetailFieldChangeEvent`, `拦截`, `钩子`
- 字段属性：`changeFieldAttr`, `只读`, `必填`, `可编辑`, `隐藏`
- 字段值：`changeFieldValue`, `getFieldValue`, `changeSingleField`, `changeMoreField`
- 字段转换：`convertFieldNameToId`, `数据库字段名`, `fieldId`
- 明细行操作：`getDetailAllRowIndexStr`, `getDetailRowSerailNum`, `getDetailRowCount`, `getDetailRowKey`
- 明细增删：`registerAction`, `ACTION_ADDROW`, `ACTION_DELROW`, `添加行`, `删除行`
- 明细行控制：`controlDetailRowDisableCheck`, `controlDetailRowDisplay`, `checkDetailRow`
- 明细复制：`setDetailAddUseCopy`
- 全局：`showMessage`, `showConfirm`, `getGlobalStore`, `getBaseInfo`, `reloadPage`, `appendSubmitParam`
- 登录人：`getGlobalStore().commonParam`, `currentUserid`, `workcode`, `loginid`, `lastname`
- 移动端：`isMobile`, `openLink`, `EM7`, `OPER_EDITDETAILROW`

### 按 API 名称速查
`convertFieldNameToId`, `changeFieldAttr`, `changeFieldValue`, `getFieldValue`, `changeSingleField`, `changeMoreField`, `bindFieldChangeEvent`, `bindDetailFieldChangeEvent`, `registerCheckEvent`, `registerAction`, `getDetailAllRowIndexStr`, `getDetailRowSerailNum`, `getDetailRowCount`, `getDetailRowKey`, `controlDetailRowDisableCheck`, `controlDetailRowDisplay`, `checkDetailRow`, `setDetailAddUseCopy`, `showMessage`, `showConfirm`, `getGlobalStore`, `getBaseInfo`, `reloadPage`, `appendSubmitParam`, `isMobile`, `openLink`

## 资源

- 本地 SDK 文档：`./sdk-doc/泛微在线文档前端SDK.html`（相对于 skill 根目录）
- 检索脚本：`scripts/search_sdk.py`