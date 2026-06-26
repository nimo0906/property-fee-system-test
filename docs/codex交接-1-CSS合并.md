# Codex 交接 ① — CSS 补丁文件合并

> 交接人：Claude（后端）　执行人：Codex（前端）　日期：2026-06-25
> 这是前后端分工后的第一个前端任务，独立、不碰后端，用来磨合分工流程。
> 配套规范见 `docs/前后端分工规范.md`。

---

## 一、任务目标

把 `static/` 下 **18 个 `app-*.css` 补丁文件**（共 3476 行）合并为 **2–3 个按职责划分的文件**，消除"补丁叠补丁、冗余 7.7 倍"的污染。完成后：CSS 总行数显著下降，同一选择器不再散落在多个文件，今后改样式只需动一处。

**目标不是重写样式，是无损合并 + 去重。** 页面视觉效果在合并前后必须保持一致。

---

## 二、为什么要做（背景）

- `static/` 下 18 个 `app-*.css` 全靠 `static/app.css` 的 `@import` 串联加载。
- 同一个类被反复重定义：`.sidebar` 被定义 **47 次**、`.card` 37 次、`.workbench-hero` 33 次、`.summary-tile` 31 次。最终哪条生效，全靠 `@import` 的先后顺序。
- 文件名暴露了"补丁"性质：`redesign-1/2`、`polish`、`readability-1/2`、`brand-polish` —— 都是"改了又改"时新加的覆盖层，而不是按模块拆分。
- `core-1-1 / core-1-2` 这种是**一个文件被机械切成两半**（为满足"单文件≤300行"），core-1-1 结尾正好停在 `.topbar {` 规则中间。合并它们就是还原。

---

## 三、⚠️ 最重要的铁律：保持层叠顺序

CSS 是"后加载覆盖先加载"。当前 `app.css` 的 `@import` 顺序就是最终样式的**唯一正确顺序**，合并时**绝对不能打乱**。

当前加载顺序（必须按此顺序拼接）：
```
1.  app-core-1-1.css      ← core 系列(布局骨架)
2.  app-core-1-2.css
3.  app-core-2-1.css
4.  app-core-2-2.css
5.  app-core-3-1.css
6.  app-core-3-2.css
7.  app-core-4.css
8.  app-polish.css         ← 补丁/覆盖层(覆盖 core)
9.  app-redesign-1.css
10. app-redesign-2.css
11. app-readability-1.css
12. app-readability-2.css
13. app-command-1-1.css    ← command 系列(组件/按钮)
14. app-command-1-2.css
15. app-command-2-1.css
16. app-command-2-2.css
17. app-command-3.css
18. app-brand-polish.css
```

---

## 四、推荐的合并方案（3 个文件）

按上面的顺序，分成 3 段，**段内按原顺序拼接**：

| 新文件 | 由哪些旧文件合并（按序） | 职责 |
|--------|------------------------|------|
| `app-base.css` | core-1-1 → 1-2 → 2-1 → 2-2 → 3-1 → 3-2 → 4 | 布局骨架：sidebar/topbar/main-content/card 等 |
| `app-overrides.css` | polish → redesign-1 → redesign-2 → readability-1 → readability-2 | 覆盖层：对 base 的视觉调整 |
| `app-components.css` | command-1-1 → 1-2 → 2-1 → 2-2 → 3 → brand-polish | 组件：按钮/工具栏/summary-tile/品牌 |

然后 `app.css` 改成只 import 这 3 个（保持顺序）：
```css
@import url('/static/app-base.css?v=20260625merge');
@import url('/static/app-overrides.css?v=20260625merge');
@import url('/static/app-components.css?v=20260625merge');
/* report_refine.css 保留原样，它有独立语义 */
@import url('/static/report_refine.css?v=20260614reports');
```

**第一步可以先只做"物理合并"（按序拼接成 3 个文件，内容一字不改）**——这一步零风险，视觉 100% 不变，因为加载顺序完全没动。

**第二步再做"去重"**（可选、谨慎）：在合并后的文件内，对同一选择器的多次定义做合并。**但只能合并完全重复的；只要有任何属性不同，必须保留靠后的那条**（因为它本来就在覆盖前面的）。拿不准就不合并，留着也只是冗余、不影响正确性。

---

## 五、不要动的文件

- `app.css`：只改它的 @import 列表，不删
- `report_refine.css`、`billing_ui_extras.css`、`date_picker.css`、`auth.css`：有独立语义，保留原样
- `vendor/` 下的 bootstrap 等：第三方库，不动

## 六、铁律：禁止再新增补丁文件

这次合并的根本目的，就是终结"出问题就新加一个 css 盖住"的循环。**今后样式有问题，改对应选择器的源头定义，不允许再新建 `app-fix-N.css` / `app-polishN.css` 之类的覆盖文件。**

---

## 七、验收标准

1. **视觉零回归**：合并前后，逐个主要页面（工作台、账单列表、收款、报表、商业收费、抄表）肉眼对比，布局/颜色/间距一致。建议合并前后各截一组图对比。
2. `static/` 下 `app-*.css` 文件数从 18 降到 3。
3. `.sidebar` / `.card` / `.workbench-hero` / `.summary-tile` 等热点选择器，定义处数明显下降。
4. 浏览器控制台无 404（@import 路径都对）、无新的样式报错。
5. 桌面 App 打包资源若含 css 清单，同步更新（见 codex.md 的打包规范）。

---

## 八、建议执行顺序

1. 先做第四节"第一步：物理合并"（3 文件、内容不改、改 app.css 的 import）→ 截图验收视觉零回归。
2. 验收通过后，再考虑"第二步：去重"（谨慎，逐个热点选择器处理）。
3. 不要一步到位边合并边大改，分两步走，每步都能独立验证。
