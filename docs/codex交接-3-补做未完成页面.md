# Codex 交接 ③ — 补做未完成的页面 UI 升级

> 交接人：Claude（后端，已核查现状）　执行人：Codex（前端）　日期：2026-06-28
> 配套规范见 `docs/前后端分工规范.md`。

---

## 一、背景：UI 升级只做了一部分

上一轮 UI 升级实际只完成了**首页**和**交付中心**，其余几个核心页面的升级**漏做了**。这是用 `tests/test_integration_11.py::test_core_desktop_pages_include_refined_ui_sections` 核查出来的——该测试逐页检查"升级后应有的标志性结构 class/文案"，目前 `/bills`、`/billing`、`/users` 整页未升级，`/auto_billing` 差一个容器 class。

**这个测试就是本次任务的验收标准**：把它跑绿，就说明补做完成。

---

## 二、精确待办清单（已逐项核查现状）

| 页面 | 入口文件 | 现状 | 需补的标志 class / 文案 |
|------|----------|------|------------------------|
| `/bills` 账单管理 | `server/bill_list.py`（`_bills_review`，约 line 93）| ❌ 完全未升级 | `ledger-toolbar`、`ledger-summary-strip`、文案"按租户和房间折叠展示" |
| `/billing` 物业收费 | `server/billing_ui.py`（`_render_billing`，约 line 37）| ❌ 完全未升级 | `cashier-layout`、`cashier-object-card`、`cashier-fee-card` |
| `/users` 操作员管理 | `server/auth_part1.py`（`_users`，约 line 155）| ❌ 完全未升级 | `operator-console`、`role-guide-grid`、文案"超级管理员：admin 保留" |
| `/auto_billing` 自动出账 | `server/auto_billing_page.py` | 🟡 差一项 | 仅缺主容器 class `auto-billing-console`（`auto-filter-panel`、`auto-run-history` 已有）|

> `/`（首页）和 `/delivery_center`（交付中心）**已完成，不要动**。

---

## 三、参照首页的成功范式

首页升级的做法是：在原有容器 class 上**追加**一个标志性 class，作为升级标记 + 样式钩子。例如 `server/index_dashboard.py`：

```python
<section class="workbench-command-shell dashboard-focus-shell">
    ...
    <div class="workbench-command-actions workbench-primary-actions">{primary_actions}</div>
```

即：`原class + 新标志class` 并存。请按同样模式给上面 4 个页面补 class，并配套在 CSS 里给这些新 class 写样式（见下条）。

`/auto_billing` 最简单——只需给它的主容器加上 `auto-billing-console` class 即可（其它两个标志已存在）。

---

## 四、关键约束（避免重蹈覆辙）

1. **只动前端结构与样式**：可改 `server/*.py` 里的 **HTML 字符串部分**（加 class、调结构、加上面要求的文案），以及 `static/*.css`。**不要动**任何 `def` 里的 SQL/计算/金额逻辑（数据准备归后端 Claude）。
2. **CSS 不要再叠补丁**：新 class 的样式写进已有的 3 个合并文件（`app-base/overrides/components`）里合适的那个，**不允许新建 `app-*.css` 补丁文件**。能用现有工具类/复用现有样式就复用，少用 `!important`（当前全站已有 531 个，别再加）。
3. **文案要同步测试**：如果你又调整了任何用户可见文案/结构，**必须同步更新对应的测试断言**——上一轮就是因为漏了这步导致测试大面积变红。
4. **表格继续用统一组件**：这些页面里的列表表格，用 `server/ui_components.py` 的 `render_table`，不要手写表格外壳。

---

## 五、验收标准

1. `tests/test_integration_11.py` 全部通过（这是硬指标）。
2. 改动涉及的页面，相关集成测试不出现新的回归（建议至少跑 `test_integration_01/09/11/15` 等覆盖这些页面的文件，分文件跑避免端口冲突）。
3. 视觉上 `/bills`、`/billing`、`/users`、`/auto_billing` 与首页风格一致。
4. 浏览器控制台无报错、无新 CSS 404。
5. 桌面 App 打包资源若含 css/模板清单，同步更新。

---

## 六、测试运行提示

- 装 pytest：`pip install pytest --break-system-packages`
- 全量 pytest 会因端口冲突超时，**按文件单独跑**：`python3 -m pytest tests/test_integration_11.py -q`
- 改完每个页面就跑一次 int_11，逐页确认变绿。
