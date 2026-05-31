# v2.0 Payment Create API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authenticated `POST /api/v1/payments` to create real payment records through `PaymentService` while preserving desktop-app safety requirements.

**Architecture:** Extend `ApiMixin._api_post` with a write endpoint. The API blocks readonly users, creates an automatic backup before writing, calls `PaymentService.create_payment()`, records an audit log through the existing handler helper, and returns structured JSON. No database schema is changed; `idempotency_key` is accepted as a future field but not persisted until a separate schema design is approved.

**Tech Stack:** Python standard library, existing `server.services.PaymentService`, existing `server.backups.create_db_backup`, SQLite, `pytest`.

---

## Files

- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/api.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_integration.py`

## Task 1: Add failing integration tests

- [ ] Add tests for:
  - readonly user cannot call `POST /api/v1/payments`
  - admin/operator can create payment and update bill status
  - endpoint creates `auto_before_api_payment_*.db` backup before writing
  - endpoint records audit log
  - overpay still returns JSON validation error and does not write
- [ ] Run focused tests and confirm failure before implementation.

## Task 2: Implement create-payment API

- [ ] Import `Actor` and `create_db_backup` in `server/api.py`.
- [ ] Add readonly guard only for `POST /api/v1/payments`, not preview.
- [ ] Create backup with prefix `auto_before_api_payment` before `PaymentService.create_payment()`.
- [ ] Call `_audit('api_payment_create', 'payment', payment_id, ...)` after success.
- [ ] Return `backup_name` and accepted `idempotency_key` in response.

## Task 3: Verify and commit

- [ ] Run focused integration tests.
- [ ] Run full tests.
- [ ] Run py_compile.
- [ ] Commit with `feat: 增加收款写入JSON接口`.
