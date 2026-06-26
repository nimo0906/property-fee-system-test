# Codex 交接 ② — 表格/表单收敛（含接口规范）

> 交接人：Claude（后端，已定接口规范）　执行人：Codex（前端实现+迁移）　日期：2026-06-25
> 配套规范见 `docs/前后端分工规范.md`。**先做完交接①（CSS合并）再做本项。**

---

## 一、任务目标

系统里 `<table>` 出现 **131 处 / 57 文件**、`<form>` 出现 **109 处 / 56 文件**，每处都手写整段表格/表单"外壳"。这是"改一处漏十处"痛点的最大来源——比如想给所有列表加个统一的空状态提示、或调整表格响应式行为，现在得改 57 个文件。

目标：提供**统一的表格/表单外壳辅助函数**，把分散的外壳收敛为一份。**注意：不是做"全自动组件"，而是收敛"外壳"，数据行仍由各页面自己拼**——这样迁移成本低、风险可控。

---

## 二、现状（好消息：不算太乱）

表格已经普遍用 Bootstrap 类（`table table-sm`、`table-hover`、`table-responsive align-middle`），视觉基本统一。真正的问题只是**"外壳结构每处手写"**：
- `<div class="table-responsive">` 包裹（71 处各写各的）
- `<table class="...">` + `<thead><tr><th>...</th></tr></thead>` 表头（列定义散落）
- 空数据时的"暂无数据"提示，每处写法不一（有的没有）

`templates/owners.html` 是较好的范式，可参考。

---

## 三、接口规范（Claude 已定，Codex 照此实现）

在 `server/ui_components.py`（新建）里实现以下两个辅助函数。**函数签名和行为按下面定义，不要改接口，便于全局统一调用。**

### 3.1 表格外壳

```python
def render_table(headers, body_rows_html, *,
                 table_class='table table-hover align-middle',
                 responsive=True,
                 empty_text='暂无数据',
                 col_count=None):
    """生成统一的表格外壳。

    headers: 列表，每项是表头单元格。支持两种写法：
             - 字符串 '姓名'
             - 元组 ('面积', 'text-end')  第二项是该列的 css class（如右对齐）
    body_rows_html: 已拼好的 <tr>...</tr> 字符串（各页面自己拼数据行，保留现有逻辑）。
             若为空字符串，则自动渲染一行 empty_text（跨 col_count 列居中）。
    table_class: 表格 class，默认 'table table-hover align-middle'，特殊页面可传别的。
    responsive: 是否用 <div class="table-responsive"> 包裹，默认 True。
    empty_text: 无数据时的提示文案。
    col_count: 空状态占几列，默认取 len(headers)。
    返回：完整的表格 HTML 字符串。
    """
```

**用法示例**（迁移前后对比）：

迁移前（owners 列表，手写）：
```python
html = '''<div class="table-responsive"><table class="table table-hover align-middle">
<thead><tr><th>姓名</th><th>电话</th><th class="text-end">面积</th><th>操作</th></tr></thead>
<tbody>''' + rows + '''</tbody></table></div>'''
```

迁移后（调用统一函数）：
```python
from server.ui_components import render_table
html = render_table(
    ['姓名', '电话', ('面积', 'text-end'), '操作'],
    rows,                      # rows 还是各页面原来拼的 <tr> 字符串，逻辑不变
)
```

### 3.2 表单外壳

```python
def render_form(fields_html, *, action, method='POST',
                submit_text='保存', cancel_url=None,
                form_class='row g-3'):
    """生成统一的表单外壳（含 CSRF、提交/取消按钮）。

    fields_html: 已拼好的字段 HTML（<div class="col-md-4">...<input>...</div> 等），
             各页面自己拼，保留现有逻辑。
    action: 表单提交地址。
    method: 默认 POST。
    submit_text: 提交按钮文案，默认 '保存'。
    cancel_url: 若提供，渲染一个"取消"链接指向它。
    form_class: 表单 class，默认 'row g-3'。
    返回：完整 <form>...</form>，自动包含 CSRF（注意：项目已有 CSRF 注入机制见
          base_part1.py 的 inject_csrf_fields，确认外壳不要重复注入/不要漏注入）。
    """
```

> ⚠️ CSRF 注意：项目通过 `base_part1.py` 的 `inject_csrf_fields` 在 `_html()` 出口统一注入 CSRF。`render_form` **不要自己再注入 CSRF token**，避免重复。只需保证生成的是标准 `<form method=POST>`，让既有机制注入即可。实现后务必测一个表单提交，确认 CSRF 校验仍通过（参考 `tests/test_csrf_protection.py`）。

---

## 四、迁移策略：路过就修，不搞大爆炸

**不要求一次迁移全部 131+109 处。** 那样风险太大、review 困难。规则：

1. **先实现** `render_table` / `render_form` 两个函数 + 给它们写单元测试。
2. **挑 2-3 个高频页面试点迁移**（建议：账单列表、收款记录、业主管理），验证函数好用、视觉无变化。
3. 之后**谁改到哪个页面，就顺手把那个页面的表格/表单迁过去**（"路过就修"）。新页面一律用统一函数。
4. 每迁一处，跑该页面相关测试，确认无回归。

这样几个迭代后自然收敛，不会因一次性大改引入难查的 bug。

---

## 五、边界：哪些不要迁

- **打印/收据/发票里的表格**：它们有专用版式（见 `print_helper.py`、发票/收据打印页），**不要**套用通用 `render_table`。
- **import 核对表、抄表录入表**等带复杂交互（行内编辑、sticky 列）的特殊表格：先不迁，保持原样。
- 判断标准：普通"列表展示型"表格才迁；带专属版式或复杂交互的留着。

---

## 六、验收标准

1. `server/ui_components.py` 实现两个函数，有对应单元测试。
2. 试点页面（账单列表/收款/业主）迁移后，视觉和功能零回归，相关 pytest 通过。
3. 表单试点迁移后，CSRF 校验仍正常（`tests/test_csrf_protection.py` 通过）。
4. 迁移过的页面，表格外壳不再手写 `<div class="table-responsive"><table>...<thead>`。
5. 空数据列表能正确显示"暂无数据"。

---

## 七、和后端（Claude）的协作点

- 这两个函数放在 `server/ui_components.py`，属于"前端外壳"，由 Codex 维护。
- 但函数会被各 `server/*.py` 调用——如果迁移中发现某页面的**数据准备逻辑**（SQL、计算）有问题，不要自己改，记下来交给 Claude（后端边界见分工规范）。
- 数据行 `<tr>` 的拼接逻辑（含 `customer_name()`、金额 `m()` 等）属于既有逻辑，迁移时**原样保留**，不要改动。
