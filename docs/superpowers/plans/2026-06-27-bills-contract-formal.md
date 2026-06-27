# Bills and Contract Formal Proposal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the bills page and merchant contracts page read like a formal, production-ready proposal version while preserving the existing desktop workflow and business semantics.

**Architecture:** Keep the current server-side rendering flow and only adjust the bills and contracts presentation surfaces. Tighten labels, add a proposal-style summary area, add clearer grouping anchors, and keep the list interactions unchanged so the workflow stays familiar.

**Tech Stack:** Python, SQLite, server-rendered HTML, Bootstrap-like utility classes, browser QA via local Chromium

---

### Task 1: Clarify bill list semantics and row text

**Files:**
- Modify: `server/bill_list.py`
- Modify: `templates/bills.html`
- Test: `tests/test_integration_12.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration_12.py

def test_bills_page_shows_scope_label_and_room_labels():
    status, body = http_get('/bills?period=2037-06', self.cookie, TEST_PORT)
    self.assertEqual(status, 200)
    self.assertIn('收费公司', body)
    self.assertIn('物业公司收费', body)
    self.assertIn('商业公司收费', body)
    self.assertIn('BILLSCOPE-B座-901', body)
    self.assertIn('商场-BILLS-SPACE-01', body)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q tests/test_integration_12.py::TestIntegration12::test_bills_page_shows_scope_label_and_room_labels`
Expected: FAIL before the row-label changes are present.

- [ ] **Step 3: Write minimal implementation**

```python
# server/bill_list.py

def _bill_scope_label(row):
    if row['commercial_space_id']:
        return '商业公司收费'
    if row['building'] == '商场' or row['unit'] == '商场':
        return '商业公司收费'
    return '物业公司收费'


def _bill_room_label(row):
    if row['commercial_space_id']:
        return f"商场-{row['space_no'] or ''}"
    return f"{row['building'] or ''}-{row['unit'] or ''}-{row['room_number'] or ''}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q tests/test_integration_12.py::TestIntegration12::test_bills_page_shows_scope_label_and_room_labels`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/bill_list.py templates/bills.html tests/test_integration_12.py
git commit -m "feat: 优化账单页正式展示"
```

### Task 2: Add formal contract overview and anchors

**Files:**
- Modify: `server/merchant_contracts_part1_group1.py`
- Test: `tests/test_integration_12.py`
- Test: `tests/test_integration_13.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration_12.py

def test_merchant_contract_list_shows_formal_group_nav_and_summary_cards():
    status, body = http_get('/merchant_contracts', self.cookie, TEST_PORT)
    self.assertEqual(status, 200)
    self.assertIn('合同档案总览', body)
    self.assertIn('id="property-contracts"', body)
    self.assertIn('id="commercial-contracts"', body)

# tests/test_integration_13.py

def test_contract_group_details_keep_stable_open_markup():
    status, page = http_get('/merchant_contracts', self.cookie, TEST_PORT)
    self.assertEqual(status, 200)
    self.assertIn('<details class="contract-group" open id="property-contracts">', page)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q tests/test_integration_12.py::TestIntegration12::test_merchant_contract_list_shows_formal_group_nav_and_summary_cards tests/test_integration_13.py::TestIntegration13::test_contract_group_details_keep_stable_open_markup`
Expected: FAIL until the overview cards and anchor ids exist.

- [ ] **Step 3: Write minimal implementation**

```python
# server/merchant_contracts_part1_group1.py

def group(title, icon, items, open_attr, anchor):
    body = ''.join(row_html(r) for r in items) or '<tr><td colspan="11" class="text-center text-muted py-4">暂无合同档案</td></tr>'
    return f'''<details class="contract-group" {open_attr} id="{anchor}">
      <summary><span><i class="bi {icon}"></i> {title}</span><span class="badge status-info">{len(items)} 份</span></summary>
      <div class="table-responsive"><table class="table table-hover align-middle mb-0">{headers}<tbody>{body}</tbody></table></div>
    </details>'''
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q tests/test_integration_12.py::TestIntegration12::test_merchant_contract_list_shows_formal_group_nav_and_summary_cards tests/test_integration_13.py::TestIntegration13::test_contract_group_details_keep_stable_open_markup`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/merchant_contracts_part1_group1.py tests/test_integration_12.py tests/test_integration_13.py
git commit -m "feat: 优化合同页正式展示"
```

### Task 3: Validate end-to-end pages in browser and tests

**Files:**
- Verify: `server/bill_list.py`
- Verify: `server/merchant_contracts_part1_group1.py`
- Verify: `templates/bills.html`

- [ ] **Step 1: Run the focused test set**

Run: `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest -q tests/test_integration_12.py tests/test_integration_13.py`
Expected: PASS.

- [ ] **Step 2: Open the live app and inspect the real pages**

Run the app, then open:
- `http://127.0.0.1:5001/bills`
- `http://127.0.0.1:5001/merchant_contracts`

Expected: the bills page uses the formal ledger layout and the contracts page shows the summary cards plus anchor navigation.

- [ ] **Step 3: Commit verification notes if any UI issue remains**

If browser inspection reveals any overflow, truncation, or contrast issue, patch the smallest possible HTML/CSS snippet and re-run the focused tests before finishing.
