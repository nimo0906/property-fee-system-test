# v2.0 Payment Preview API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authenticated `POST /api/v1/payments/preview` for H5/small-program payment confirmation without writing payment data.

**Architecture:** Extend existing `ApiMixin` with POST delegation and form/JSON body parsing. The API calls `PaymentService.preview_payment()` only, so it performs validation and returns payment impact without changing database state.

**Tech Stack:** Python standard library, existing `server.services.PaymentService`, `http.server`, `pytest`.

---

## Files

- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/api.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/base.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_integration.py`

## Task 1: Add failing tests

- [ ] Add integration tests for unauthenticated payment preview, successful preview, overpay rejection, and no database write.
- [ ] Run focused tests and verify failure because POST `/api/v1/payments/preview` is not routed.

## Task 2: Implement API POST preview

- [ ] Import `PaymentService` in `server/api.py`.
- [ ] Add `_api_post(path, data)` to `ApiMixin`.
- [ ] In `BaseHandler.do_POST`, route `/api/v1/` before normal HTML write permission checks.
- [ ] Map `ServiceError` to JSON `400 validation_error` for payment preview validation failures.

## Task 3: Verify and commit

- [ ] Run focused API tests.
- [ ] Run full tests.
- [ ] Run py_compile.
- [ ] Commit with `feat: 增加收款预览JSON接口`.
