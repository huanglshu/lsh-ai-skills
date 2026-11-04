---
name: weaver-oa-form-js-sdk
description: 处理泛微 OA 流程表单 JS 代码块、WfForm API、custompage、自定义事件、字段联动和明细表逻辑时，优先检索本地 SDK 文档并按表单代码块场景输出可直接使用的 JS 方案。
---

# Weaver OA Form JS SDK

泛微 E9 流程表单前端低代码开发。

## 何时使用

- 编写或修改泛微 OA 表单 JS 代码块 / custompage。
- 用户提到 `WfForm`、`代码块`、`字段联动`、`明细表`、`注册事件`、`浏览按钮`、`EM7`、`移动端兼容`。
- 流程表单前端调试、字段控制、事件拦截、联动渲染。

## 必须遵循的参考路径

- 默认参考文档：`./sdk-doc/泛微在线文档前端SDK.html`（相对于 skill 根目录）
- 若该路径不存在，明确说明本地 SDK 文档缺失，再退回通用经验分析。

---

## 0. 需求不明确时先问，不要猜

**猜测的代价远高于提问。** 一次错误猜测会导致整套代码重写，而且猜错的方向往往看起来很像对的，用户可能直接拿去用。宁可多问一轮。

### 0.1 该自己查的，不要问用户

这些信息能从数据库或页面得到，**提问之前先自己查**：

| 信息 | 查法 |
| --- | --- |
| 字段是否存在、fieldId、字段类型 | `workflow_billfield`（见第 6 节） |
| 字段属于主表还是哪张明细表 | `workflow_billfield.DETAILTABLE` |
| 明细表序号对应关系 | `workflow_billdetailtable.ORDERID` → `detail_1`/`detail_2` |
| 选择框选项的**真实入库值** | `workflow_selectitem` |
| 节点上字段是只读/可编辑/必填 | `workflow_nodeform.ISEDIT` / `ISMANDATORY` |
| 是否已配显示属性联动 | `workflow_viewattrlinkage` |
| 明细表所在行 id（`#r6` 这类） | `workflow_nodehtmllayout.DATAJSON` 的 `rowattrs` |

问用户这些本该自己查的信息，说明功课没做。

### 0.2 必须问用户的，不要替他决定

| 必须确认 | 为什么不能猜 |
| --- | --- |
| **哪个选项值对应哪个状态** | 选择框可能存 `1`/`2`，也可能是字符串或 `0`，语义只有业务知道 |
| **初始态期望** | 字段为空时应该「全部隐藏」还是「全部显示」？猜错就是首屏显示错误 |
| **作用节点范围** | 只创建节点，还是所有节点都要？影响是否需要节点判断 |
| **控制的是哪种效果** | 只读 / 必填 / 可编辑 / 隐藏标签 / 隐藏整行 / 整块显隐，粒度完全不同 |
| **隐藏后的数据怎么处理** | 隐藏明细里已有数据是否清空？涉及数据丢失，不能默认 |
| **是否需要移动端** | EM7 走独立模板，PC 的代码不一定适用 |
| **验收标准** | 用户看到什么才算对，决定验证方式 |

### 0.3 用户描述现象时的取数方法

用户说「按钮不见了」「两个明细都显示了」这类**视觉现象**时，最有效的不是猜代码，而是**要真实页面**：

> 请在该页面按 `Ctrl+S` 保存完整网页，把 HTML 和同名资源目录发我。

拿到渲染后的 DOM 后可以直接检索，判断元素存不存在、class 是什么、`display` 是什么。这比反复猜「是不是初始化时机问题」快一个数量级，而且结论是确定的。

同理，「字段值不对」类问题优先查库确认实际入库值，不要只读代码推断。

### 0.4 提问方式

- **一次问一组完整的，不要挤牙膏。** 先按 0.2 列清单，把缺的一次性问清。
- **每个问题给出选项和推荐值**，降低用户回答成本。
- **说明为什么需要这个信息**，用户才知道该给到什么粒度。
- **已经能自己查到的，不要混进问题里**，否则显得没做功课。

### 0.5 禁止的表述

- 「应该是 xxx 字段」「大概是这个值」——不要用推测冒充事实。
- 一次给三四个方案让用户选，却不指出哪个推荐、为什么。
- 拿到模糊需求就直接产出完整代码，把不确定性留到用户上线时才发现。
- 把自己没验证的推断写成结论，不标注「待确认」。

---

## 1. 铁律

### 1.1 只用 WfForm，禁止碰 DOM

SDK 原文（1.1 / 9.6 / 9.7）：

> 表单字段相关操作，**不推荐使用 jQuery，禁止原生 JS 直接操作 DOM 结构**！
> 9.6 少用 jQuery 操作 —— 不推荐使用
> 9.7 禁止 JS 原生操作 —— **不允许，会引发各种不可控异常**

判断顺序：**先找 `WfForm` 有没有对应接口 → 没有才考虑 DOM → 用 DOM 必须在注释里标注「受控例外」并说明为什么没有官方接口。**

禁止的典型写法：

| 反模式 | 为什么不行 | 官方替代 |
| --- | --- | --- |
| `document.getElementById("field111").value = x` | SDK 9.7 明令禁止 | `changeFieldValue("field111", {value:x})` |
| `jQuery("#field111").val()` | SDK 9.6 不推荐，且绕过产品状态管理 | 同上 |
| `document.getElementById(mark+"span")` + `addClass("wf-input-required")` 手补红星 | 依赖产品私有 class，升级即失效 | `changeFieldAttr(mark, 3)` 自带红星 |
| jQuery 改 `td`/`div` 的 `position`、`display` 修布局 | 直接改产品结构，不可控 | 回表单设计器调模板 |
| 遍历字段自己判空做必填校验 | 重复产品能力，提示还定位不准 | `changeFieldAttr(mark, 3)`，框架自己拦 |

### 1.2 字段标识必须从数据库字段名转换

- 配置项只写**数据库字段名**，代码内用 `convertFieldNameToId(fieldName, detailMark)` 转换。
- **禁止硬编码 `field27584`** —— fieldId 跨环境（SIT/UAT/生产）不一致。
- 主表第二个参数传 `"main"`，明细传 `"detail_1"` / `"detail_2"`。
- 返回 null 要判空；`changeFieldAttr` 操作不存在的行会抛异常，需 try-catch。
- **同名不同 id 陷阱**：同一字段名可能存在于多张明细表且 fieldId 完全不同（实例：`ssgs` 在 dt1=26582、dt2=160399）。必须带 `detail_N`，否则操作错表。

### 1.3 唯一受控例外：明细表区块整体显隐

SDK **没有**「整个明细表区块显示/隐藏」的接口。`changeFieldAttr(…,4/5)` 隐藏标签/整行**只支持主表**。

唯一可行做法：设计器里给明细表所在行设 id → 前端得到 `<tr id="r6">` → `jQuery("#r6").show()/hide()`。

必须在注释中标注这是受控例外。除此之外不要用 jQuery 操作表单。

### 1.4 别信「不生效」传言

代码注释或历史代码里说某个官方 API「不生效」时，**先写最小验证代码实测，再决定要不要绕**。

一套绕行方案的成本远高于一次 5 分钟实测。绕行时必须把「为什么必须绕」和「验证方法」写进注释，不要只写结论。

---

## 2. 需求 → 函数速查

### 2.1 取值

| 我要做什么 | 函数 | 关键点 |
| --- | --- | --- |
| 取主表字段值 | `getFieldValue(mark)` | 浏览框返回主键 id 串 |
| 取明细字段值 | `getFieldValue(mark + "_" + rowIndex)` | rowIndex 从 `getDetailAllRowIndexStr` 取 |
| 取浏览框显示名 | `getBrowserShowValue(mark)` 或 `getFieldValueObj(mark).specialobj` | 需要显示文本时用 |
| 取字段**后台配置** | `getFieldInfo(fieldId)` | 入参不带 `field` 前缀；返回 `viewattr`/`htmltype`/`fieldname`/`fieldlabel` |
| 取字段**实时属性** | `getFieldCurViewAttr(mark)` | 含联动、代码改动、已办；已办全部返回 1 |
| 取所有明细行号 | `getDetailAllRowIndexStr(detailMark)` | 返回 `"1,3"` 字符串，**必须 split(",")，不能当循环下标** |
| 取明细总行数 | `getDetailRowCount(detailMark)` | 只代表数量，**不能用作循环** |
| 取明细行数据库主键 | `getDetailRowKey(mark)` | 仅已有行有效，新增行返回 `-1` |
| 取明细行序号（第几行） | `getDetailRowSerailNum(mark, rowIndex)` | 用于提示「第 N 行有误」 |
| 取当前请求信息 | `getBaseInfo()` | workflowid / nodeid / formid / requestid / isbill |
| 取当前登录人 | `getGlobalStore().commonParam` | currentUserid / lastname / workcode / loginid |

### 2.2 赋值

| 我要做什么 | 函数 | 关键点 |
| --- | --- | --- |
| 改单个字段值 | `changeFieldValue(mark, {value:x})` | 会自动触发联动/格式化 |
| 给浏览框赋值 | `changeFieldValue(mark, {value:"2,3", specialobj:[{id:"2",name:"张三"}]})` | **必须有 specialobj 数组** |
| 只读时显示值与入库值不同 | `changeFieldValue(mark, {value:"真实值", specialobj:{showhtml:"显示值"}})` | 仅单行文本类型有效 |
| 改值同时改属性 | `changeSingleField(mark, {value:x}, {viewAttr:3})` | 一步完成 |
| 批量改值/属性 | `changeMoreField({fieldA:{value:x}}, {fieldA:{viewAttr:2}})` | key 为主表字段标识；明细仍需带行号 |
| 加明细行并给初始值 | `addDetailRow(detailMark, {field111:{value:"x"}})` | key **不带下划线**、不带行号 |
| 新行默认复制上一行 | `setDetailAddUseCopy(detailMark, true)` | 须在 ready 中调用 |

> ⚠️ **SDK 3.3 明文禁止**：后台设为只读的字段，`changeFieldValue` 改写其值在非创建时刻**属于篡改数据**，无法入库。要显示只读但能赋值，应设为可编辑 + 前端禁止手工编辑。

### 2.3 属性控制（只读 / 必填 / 隐藏）

核心接口只有一个：`changeFieldAttr(fieldMark, viewAttr)`

| viewAttr | 含义 |
| --- | --- |
| `1` | 只读 |
| `2` | 可编辑 |
| `3` | 必填 |
| `4` | 隐藏字段标签及内容（**只支持主表**） |
| `5` | 隐藏字段所在行（**只支持主表**，且行内不能有行合并） |

约束：

- **取消必填用 `2`**，没有单独的枚举值。
- **明细字段必须带行号**：`field${字段ID}_${明细行号}`。SDK 里唯一支持「明细字段不带行号、对所有行生效」的是 `bindFieldAction`，那是绑事件的，**不能设属性**。所以明细必填只能遍历行。
- **新增行不继承 viewAttr**，必须 `registerAction(ACTION_ADDROW + n)` 重新设一遍，否则新行没有红星。
- **只读字段上调用会被平台忽略**（实测，见第 5 节），不需要额外写只读判断。

### 2.4 事件与拦截

| 我要做什么 | 函数 | 回调签名 / 关键点 |
| --- | --- | --- |
| 主表字段值变化 | `bindFieldChangeEvent(markStr, fn)` | `fn(obj, id, value)`；可逗号拼多个字段 |
| 明细字段值变化 | `bindDetailFieldChangeEvent(markStr, fn)` | `fn(id, rowIndex, value)`；**字段标识不能带下划线**，对所有行生效 |
| 单元格区域动作 | `bindFieldAction(type, fieldids, fn)` | `type`: onblur/onfocus/onclick/ondblclick/mouseover/mouseout；`fn(fieldid, rowIndex)` |
| 加行后（钩子） | `registerAction(ACTION_ADDROW + 表序号, fn)` | `fn(index)`，index 是新行下标 |
| 删行后（钩子） | `registerAction(ACTION_DELROW + 表序号, fn)` | `fn(arg)`，arg 是行下标数组 |
| 保存/提交**前**拦截 | `registerCheckEvent(OPER_SAVE + "," + OPER_SUBMIT, fn)` | `fn(callback)`；**不调 callback() 即阻断**，调了才放行 |
| 加行/删行**前**拦截 | `registerCheckEvent(OPER_ADDROW + 表序号, fn)` | 可用来限制行数上限、禁止删除 |
| 必填校验前 | `registerCheckEvent(OPER_BEFOREVERIFY, fn)` | 配合 `getFirstRequiredEmptyField()` 自定义提示 |

常用 `OPER_*`：`SAVE` `SUBMIT` `SUBMITCONFIRM` `REJECT` `FORWARD` `TAKEBACK` `DELETE` `ADDROW` `DELROW` `PRINTPREVIEW` `EDITDETAILROW` `BEFOREVERIFY` `TURNREAD` `WITHDRAW` `CLOSE`

> ⚠️ `registerCheckEvent` 只用于**产品做不到**的规则（跨表比对、合计校验、行数下限）。字段级必填一律交给 `changeFieldAttr(…,3)`，不要自己遍历判空。

### 2.5 明细行操作

| 我要做什么 | 函数 | 关键点 |
| --- | --- | --- |
| 显示/隐藏明细数据行 | `controlDetailRowDisplay(detailMark, rowIndexMark, needHide)` | 只是界面效果，序号不断层重排 |
| 禁用/启用行勾选框（禁删） | `controlDetailRowDisableCheck(detailMark, rowIndexMark, disable)` | 后台配置的置灰行不支持此 API 改 |
| 选中行 | `checkDetailRow(detailMark, rowIndexMark, needClearBefore)` | 传 `""` + `true` 可清空所有选中 |
| 删除行 | `delDetailRow(detailMark, rowIndexMark)` | **无确认框**，直接删 |
| 监听增删行后逻辑 | `registerAction(ACTION_ADDROW/ACTION_DELROW + n, fn)` | 见 2.4 |

以上 `rowIndexMark` 都支持 `"all"` 或 `"1,2,3"`。批量优先于逐行。

编辑权限 ≠ 删除权限：前者用 `changeFieldAttr(mark, 1/2)`，后者用 `controlDetailRowDisableCheck`，两者需分别控制。

### 2.6 提示与全局

| 我要做什么 | 函数 | 关键点 |
| --- | --- | --- |
| 提示信息 | `showMessage(msg, type, duration)` | type：`1`=警告 `2`=错误 `3`=成功 `4`=一般；**校验提示用 1**，duration 单位秒，默认 1.5 |
| 确认框 | `showConfirm(content, okEvent, cancelEvent, otherInfo)` | 兼容移动端，可自定义按钮文案 |
| 按钮置灰 | `controlBtnDisabled(isDisabled)` | 提交中防重复点击 |
| 刷新表单 | `reloadPage(params)` | |
| 扩展提交参数 | `appendSubmitParam(obj)` | 自定义参数以 `cus_` 开头 |
| 判断终端 | `isMobile()` | true=EM7/微信/钉钉 |

---

## 3. 先判断：能不能不写代码

**能配就不写。** 配置稳定可维护、升级不失效；代码块是最后手段。

| 需求 | 优先方案 | 要不要写代码 |
| --- | --- | --- |
| 主表字段 A 的值影响主表字段 B 的显隐/必填/只读 | 设计器「显示属性联动」（`workflow_viewattrlinkage`） | 不写 |
| 字段默认值、简单赋值 | 字段默认值 / 公式 | 不写 |
| 节点字段必填 | 节点字段属性勾「必填」（`workflow_nodeform.ISMANDATORY`） | 不写 |
| **明细表**字段的显隐/必填随主表变化 | 显示属性联动**只支持主表**，配不了明细 → 写代码 | 写 |
| **整个明细表区块**显隐 | 无官方 API → 写代码（受控例外） | 写 |
| 跨表业务规则（合计、行数下限、互斥） | 产品必填校验做不到 → 写代码 | 写 |

> **关键事实：`workflow_viewattrlinkage`（显示属性联动）只支持主表。** 明细表的显隐/必填联动必须走代码块。

---

## 4. 接口使用的通用原则

三条，适用于所有场景：

1. **空值要显式处理。** 不要写「空值就什么都不做」——先想清楚空值时的期望状态。若期望是「全部隐藏」，就要遍历所有分支主动设置，否则页面初始态会显示不该显示的内容。
2. **初始时机要延后。** 明细表可能晚于 `ready` 渲染，首次执行用 `setTimeout(fn, 400)` 兜底，别在 `ready` 里同步跑。同时注册 `ACTION_ADDROW` 钩子。
3. **诊断不要静默。** `if ($x.length && ...)` 这种写法会让「元素根本不存在」这种情况静默通过。要显式区分「不存在」和「不可见」两种情况，分别输出不同日志。

其他：

- **判空规则**：不要把 `"0"` 当空 —— 选择框「否」常存 0。
- **测试先行**：涉及行号判断（如奇偶行权限）先写 `var TEST_MODE = true` 验证事件绑定与渲染时机，再切正式逻辑。
- **移动端**：EM7 与 PC 共用 `custompage` 但**模板不同**，PC 模板里的行 id 在移动模板里不存在。
- **custompage**：方式二、方式三禁止引入 `init_wev8.js`；全局 custompage 避免定义 `ready`、`checkCustomize` 等全局函数壳。
- **调试出口**：给一个 `window.__xxxDbg()` 函数，一次性打印字段属性、明细行、区块状态，比零散日志高效。

---

## 5. 已验证的关键事实

以下为 E9 实测结论，可直接依赖：

| 事实 | 说明 |
| --- | --- |
| **只读字段上 `changeFieldAttr` 被平台忽略** | 设为 3 仍是 1，设为 2 仍是 1。不会造成「只读+必填」死锁，也不会把审批人的只读字段变成可编辑，**不需要写只读判断** |
| **`changeFieldAttr(3)` 确实拦截提交** | 明细字段同样生效，框架原生拦，无需自定义校验 |
| **`getDetailAllRowIndexStr` 返回值就是 rowIndex** | 返回 `"0"` 时 DOM 里是 `field160388_0`，可直接拼 fieldMark，不会错位 |
| **明细行视觉序号 ≠ fieldMark 的 rowIndex** | 单元格 class `detail_2_3_3` 中的 3 是模板行列坐标，fieldMark 的 `_0` 是数据行索引，两套编号本来就不相等 |
| **明细表按钮单元格是 `etype_10`** | `etype_0` 是空白单元格。这个差异从数据库 `DATAJSON` 看不出来，只有渲染后的 DOM 才暴露 |
| **明细字段必须带行号** | `changeFieldAttr` 无「不带行号对所有行生效」的写法 |
| **新增行不继承 viewAttr** | 必须 `registerAction(ACTION_ADDROW)` 重新设置 |
| **`getFieldCurViewAttr` 已办全部返回 1** | 需区分「实时属性」和「后台配置」，后者用 `getFieldInfo().viewattr` |

区分「改属性」与「写值」：只读字段上 `changeFieldAttr` 被忽略（安全），但 `changeFieldValue` 改写只读字段值属于**篡改数据**（SDK 3.3 禁止）。两件事不要混为一谈。

---

## 6. 写代码前核实表单真实配置

不要凭字段名猜。很多「必填不生效」「字段找不到」的问题在这一步就能定位。

```
workflow_base (ID=workflowid)           → FORMID
  workflow_bill (ID=FORMID)             → TABLENAME
  workflow_billfield (BILLID=FORMID)    → FIELDNAME / DETAILTABLE / FIELDHTMLTYPE
  workflow_billdetailtable (BILLID)     → 明细表 ORDERID（对应 detail_1/detail_2）
  workflow_nodeform (NODEID, FIELDID)   → ISVIEW / ISEDIT / ISMANDATORY
  workflow_viewattrlinkage (WORKFLOWID) → 显示属性联动是否已配（只支持主表）
  workflow_selectitem (FIELDID)         → 选择框选项的真实入库值
```

必查项：

- `workflow_billdetailtable.ORDERID` 决定 `detail_1` / `detail_2` 的对应关系，**别按字段顺序猜**。
- `workflow_selectitem` 确认选项**真实入库值**（可能是 `1`/`2`，也可能是字符串或 `0`）。
- `workflow_nodeform.ISMANDATORY` 为 NULL 说明**模板层本来就没有必填**。若代码在讨论「隐藏表的原生必填会拦提交」，这个前提不成立，先核实再写。
- 明细表数据关联主表用 `MAINID = formtable_main_XXX.ID`，**不是 requestid**。按 requestid 直查明细表会得到空结果。
- `workflow_nodehtmllayout.SCRIPTSTR` 是加密串，读不出明文代码，不要试图解密。

---

## 7. 示例：主表选择框切换明细表显隐与必填

> 这是**一个具体场景的示例**，不是通用规则。其他联动需求的实现思路相同，但字段、分组、延时值都要按实际调整。

需求：主表选择框「客户主体类型」切换，控制两张明细表的显示隐藏与必填。

```javascript
jQuery(document).ready(function () {
    var SUBJ = WfForm.convertFieldNameToId("customerSubjectType", "main");
    if (!SUBJ) { console.warn("[联动] 主表字段未找到，已终止"); return; }

    // key = 选择框入库值；row = 设计器里给明细表所在行设的 id
    var G = {
        "1": { label: "企业", row: "r6", table: "detail_1", req: "ssgs,khmc,nssbh,khdz,phone" },
        "2": { label: "个人", row: "r7", table: "detail_2", req: "ssgs,khmc2,sfzhm,txdz,lxdh" }
    };

    // 预解析必填字段标识（必须带明细表标识：同名 ssgs 在两张表里 fieldId 不同）
    for (var k in G) {
        if (!G.hasOwnProperty(k)) continue;
        var g = G[k];
        g.ids = [];
        var names = g.req.split(",");
        for (var i = 0; i < names.length; i++) {
            var fid = WfForm.convertFieldNameToId(names[i], g.table);
            if (fid) g.ids.push(fid);
        }
    }

    function setBlock(g, on) {
        var $r = jQuery("#" + g.row);
        if (!$r.length) {
            console.warn("[联动] 未找到明细区块 #" + g.row + "，请核对设计器里给明细表所在行设的 id");
            return;
        }
        if (on) $r.show(); else $r.hide();
        if (on) {
            setTimeout(function () {
                var $btn = $r.find(".detailButtonDiv");
                if (!$btn.length) {
                    // 区分「模板漏配」和「被隐藏」：前者脚本改不出来
                    console.warn("[联动] " + g.row + " 内无 .detailButtonDiv —— 该明细表模板可能未配置按钮行，" +
                        "请到设计器给顶部控制行插入按钮控件（应为 etype_10）");
                } else if (!$btn.is(":visible")) {
                    $btn.show();
                }
            }, 60);
        }
    }

    function setRequired(g, on) {
        if (!g.ids.length) return;
        var rows = (WfForm.getDetailAllRowIndexStr(g.table) || "").split(",");
        for (var i = 0; i < rows.length; i++) {
            if (!rows[i]) continue;
            for (var j = 0; j < g.ids.length; j++) {
                try { WfForm.changeFieldAttr(g.ids[j] + "_" + rows[i], on ? 3 : 2); } catch (e) {}
            }
        }
    }

    function apply() {
        var v;
        try { v = WfForm.getFieldValue(SUBJ); } catch (e) { v = ""; }
        v = (v === null || v === undefined) ? "" : String(v);

        // 未选择 / 未知值：全部隐藏（不能「什么都不做」，否则初始态两张都显示）
        if (!v || !G[v]) {
            for (var k in G) {
                if (!G.hasOwnProperty(k)) continue;
                setBlock(G[k], false);
                setRequired(G[k], false);
            }
            return;
        }

        for (var k2 in G) {
            if (!G.hasOwnProperty(k2)) continue;
            var on = (k2 === v);
            setBlock(G[k2], on);
            setRequired(G[k2], on);
        }
    }

    // 首次延后：等明细渲染完再隐藏，避免按钮不渲染
    setTimeout(apply, 400);
    setTimeout(apply, 1200);
    WfForm.bindFieldChangeEvent(SUBJ, function () { setTimeout(apply, 0); });
    WfForm.registerAction(WfForm.ACTION_ADDROW + "1", function () { setTimeout(apply, 100); });
    WfForm.registerAction(WfForm.ACTION_ADDROW + "2", function () { setTimeout(apply, 100); });
});
```

该示例涉及的、可复用到其他场景的要点：

- 不做节点判断，只看字段值（打开时已选值就按值联动，没选就等选择）。
- 空值分支显式全部隐藏。
- 首次执行延后 400ms。
- 明细区块显隐用 jQuery（受控例外）；明细字段属性用 `changeFieldAttr`。
- 按钮缺失优先怀疑模板配置，不是脚本问题。

排查「明细表按钮不显示」的方法：

```javascript
// 每个区块内按钮数量，0 = 模板漏配
["r6", "r7"].forEach(function (r) {
    console.log(r, "按钮数:", jQuery("#" + r).find(".detailButtonDiv").length);
});
```

按钮数 ≥ 1 → 是脚本或显隐时机问题；按钮数 = 0 → 模板设计器里没给该明细表配按钮行，脚本改不出来。

---

## 8. 其他场景速查

| 场景 | 核心 API |
| --- | --- |
| 明细表行权限控制 | `changeFieldAttr` + `controlDetailRowDisableCheck` + `registerAction(ACTION_ADDROW/DELROW)` + `bindDetailFieldChangeEvent` + `getGlobalStore().commonParam` |
| 明细表合计校验 | `getFieldValue` + `getDetailAllRowIndexStr` + `bindDetailFieldChangeEvent` + `registerCheckEvent` + `showMessage` |
| 主表字段联动明细表默认值 | `bindFieldChangeEvent` + `registerAction(ACTION_ADDROW)` + `changeFieldValue` / `addDetailRow` + `setDetailAddUseCopy` |
| 跨表业务规则校验 | `registerCheckEvent` + `getDetailAllRowIndexStr` + `getFieldValue` + `showMessage(…, 1, 6)` |

---

## 9. 工作流

1. 判断需求类型：字段操作 / 事件 / 绑定渲染 / 明细表 / 全局 / 特定字段类型。
2. **检查信息是否充分（第 0 节）。**
   - 0.1 能自己查的，先查库核实，别问用户。
   - 0.2 必须用户决定的（选项语义、初始态、节点范围、控制粒度、数据处置、验收标准），一次性问清。
   - 信息不齐不要开始写代码。
3. **按第 3 节判断能不能用配置做掉**，能配就不写代码。
4. 需要写代码时，按第 6 节查库核实字段名、明细表归属、节点属性、选项值。
5. 检索 SDK 原文：

```bash
python3 scripts/search_sdk.py 关键词1 关键词2
```

6. 按第 1、4 节约束写代码，逐段自问「是不是在重复产品功能」。
7. 输出时给出：
   - 可直接粘贴的完整代码块
   - 配置前提（明细表行 id、选项值等）
   - PC/移动端差异
   - 明确标出「受控例外」（非官方做法）及原因
   - **区分「已验证事实」和「代码推断 / 待确认项」**，不要把推断写成结论
   - 未实测部分单独列出并给出验证方法

8. 用户反馈异常现象时，优先索取真实页面（HTML 快照）或查库确认，不要凭代码猜（见 0.3）。

---

## 常用检索关键词

### 按功能分类

- 事件：`registerCheckEvent`, `registerAction`, `bindFieldChangeEvent`, `bindDetailFieldChangeEvent`, `bindFieldAction`, `拦截`, `钩子`
- 字段属性：`changeFieldAttr`, `只读`, `必填`, `可编辑`, `隐藏`
- 字段值：`changeFieldValue`, `getFieldValue`, `changeSingleField`, `changeMoreField`, `getFieldValueObj`
- 字段转换：`convertFieldNameToId`, `数据库字段名`, `fieldId`
- 属性查询：`getFieldCurViewAttr`, `getFieldInfo`, `viewattr`
- 明细行：`getDetailAllRowIndexStr`, `getDetailRowSerailNum`, `getDetailRowCount`, `getDetailRowKey`
- 明细控制：`controlDetailRowDisableCheck`, `controlDetailRowDisplay`, `checkDetailRow`, `delDetailRow`, `addDetailRow`
- 明细增删：`ACTION_ADDROW`, `ACTION_DELROW`, `OPER_ADDROW`, `OPER_DELROW`
- 明细复制：`setDetailAddUseCopy`
- 必填辅助：`getFirstRequiredEmptyField`, `verifyFormRequired`, `OPER_BEFOREVERIFY`
- 全局：`showMessage`, `showConfirm`, `getGlobalStore`, `getBaseInfo`, `reloadPage`, `appendSubmitParam`, `controlBtnDisabled`
- 登录人：`getGlobalStore().commonParam`, `currentUserid`, `workcode`, `loginid`, `lastname`
- 移动端：`isMobile`, `openLink`, `EM7`, `OPER_EDITDETAILROW`

### 按 API 名称速查

`convertFieldNameToId`, `changeFieldAttr`, `changeFieldValue`, `getFieldValue`, `getFieldValueObj`, `changeSingleField`, `changeMoreField`, `getFieldInfo`, `getFieldCurViewAttr`, `bindFieldChangeEvent`, `bindDetailFieldChangeEvent`, `bindFieldAction`, `registerCheckEvent`, `registerAction`, `getDetailAllRowIndexStr`, `getDetailRowSerailNum`, `getDetailRowCount`, `getDetailRowKey`, `controlDetailRowDisableCheck`, `controlDetailRowDisplay`, `checkDetailRow`, `delDetailRow`, `addDetailRow`, `setDetailAddUseCopy`, `showMessage`, `showConfirm`, `getGlobalStore`, `getBaseInfo`, `reloadPage`, `appendSubmitParam`, `controlBtnDisabled`, `getFirstRequiredEmptyField`, `verifyFormRequired`, `isMobile`, `openLink`

---

## 资源

- 本地 SDK 文档：`./sdk-doc/泛微在线文档前端SDK.html`（相对于 skill 根目录）
- 检索脚本：`scripts/search_sdk.py`