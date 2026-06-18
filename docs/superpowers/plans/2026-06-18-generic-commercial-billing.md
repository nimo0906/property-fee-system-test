# Generic Commercial Billing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the old mall-specific commercial billing entry into a generic commercial billing flow usable by any property company.

**Architecture:** Keep the existing `/commercial_billing` route and data schema. Generalize commercial scope from `unit='商场' AND category IN ('商户','商业')` to `category IN ('商户','商业')`, and update user-facing copy from mall-specific wording to generic commercial wording.

**Tech Stack:** Python BaseHTTPRequestHandler app, SQLite, existing pytest integration tests.

---

### Task 1: Billing page commercial scope

**Files:**
- Modify: `server/billing_ui.py`
- Test: `tests/test_integration_18.py`

- [x] Add a regression test that creates one commercial room in a non-mall unit and confirms it appears in `/commercial_billing` but not `/billing`.
- [x] Change commercial room query to `r.category IN ('商户','商业')`.
- [x] Change property room query to exclude `r.category IN ('商户','商业')`.
- [x] Update mode note to remove mall-only wording.

### Task 2: Batch bill generation commercial scope

**Files:**
- Modify: `server/bill_generation_part1_group1.py`
- Modify: `server/bill_generation_part1_group2.py`
- Test: `tests/test_integration_18.py`

- [x] Add a regression test that submits `/bills/generate` with `mode_scope=commercial` for a non-mall commercial room.
- [x] Remove hidden default unit `商场` from commercial mode.
- [x] Change commercial generation filter to `category IN ('商户','商业')` only.
- [x] Update commercial generation help copy.

### Task 3: User-facing generic copy

**Files:**
- Modify small copy in `server/rooms.py`, `server/delivery_center.py`, `server/delivery_staff_guide.py`, `server/auto_billing_scope.py`, `server/reports_shared.py` as needed.

- [x] Replace mall-only wording with generic commercial wording where it is visible to ordinary users.
- [x] Do not remove historical tests or archived real-data docs in this task.

### Task 4: Verification

- [x] Run focused pytest for commercial billing tests.
- [x] Run broader integration tests if focused tests pass.
- [x] Report any failures honestly.
