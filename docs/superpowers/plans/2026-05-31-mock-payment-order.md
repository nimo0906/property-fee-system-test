# Mock Payment Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement local mock payment order flow so owner H5 can create a payment order and simulate successful payment without real WeChat/Alipay.

**Architecture:** Add additive schema for `payment_orders` and `payment_callbacks`; add `PaymentOrderService`; expose owner-portal JSON APIs; upgrade bill detail page to create a mock order and mark it paid. Mock paid uses `PaymentService.create_payment()` and refuses repeated payment for already-paid orders.

**Tech Stack:** Python standard library, SQLite, existing OwnerPortalService and PaymentService, server-rendered H5, pytest.

---

## Files

- Modify: `server/db.py`
- Create: `server/payment_orders.py`
- Modify: `server/api.py`
- Modify: `server/owner_portal_pages.py`
- Modify: `server/base.py`
- Create: `tests/test_payment_orders.py`
- Modify: `tests/test_integration.py`

## Tasks

- [ ] Add failing service tests for schema, create order, mock paid, and duplicate mock paid protection.
- [ ] Implement schema and `PaymentOrderService`.
- [ ] Add owner portal APIs for create order and mock paid.
- [ ] Add H5 bill detail order creation and mock payment success actions.
- [ ] Run focused tests, full suite, py_compile.
- [ ] Commit with `feat: 增加模拟支付订单闭环` and push.
