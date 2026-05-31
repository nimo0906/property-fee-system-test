# Owner Portal Payment Preview H5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the owner H5 check-before-pay flow by adding a payment preview form on bill detail pages.

**Architecture:** Add a POST page route `/owner-portal/bills/{id}/preview-payment` that validates owner session, calls `OwnerPortalService.preview_payment()`, and re-renders bill detail with preview result. No real payment is written.

**Tech Stack:** Python `http.server`, existing `OwnerPortalService`, server-rendered HTML, pytest integration tests.

---

## Files

- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/owner_portal_pages.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/base.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_integration.py`

## Tasks

- [ ] Add failing test for posting preview amount from H5 bill detail and showing unpaid-before/unpaid-after without writing payment.
- [ ] Implement preview POST route and render result.
- [ ] Verify focused tests, full suite, py_compile.
- [ ] Commit with `feat: 增加业主端支付前确认` and push.
