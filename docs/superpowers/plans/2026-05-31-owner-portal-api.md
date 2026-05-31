# Owner Portal API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add owner-facing JSON APIs for login, profile, rooms, bills, payments, and payment preview using owner portal session tokens.

**Architecture:** Extend `OwnerPortalService` with owner-scoped read methods and bill ownership validation. Extend `ApiMixin` with `/api/v1/owner-portal/...` routes that use `owner_portal_token` cookie, not backend operator session. Keep backend `/api/v1/...` routes unchanged.

**Tech Stack:** Python standard library, SQLite, existing `server.owner_portal`, existing `PaymentService`, `pytest` integration tests.

---

## Files

- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/owner_portal.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/api.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_integration.py`

## Tasks

- [ ] Add failing integration tests for send-code, login cookie, profile, rooms, bills, payments, owner-scoped payment preview, and cross-owner bill denial.
- [ ] Add service read helpers for profile, rooms, bills, payments, and payment preview with owner_id checks.
- [ ] Add owner portal routes to `ApiMixin`.
- [ ] Verify focused tests, full test suite, and py_compile.
- [ ] Commit with `feat: 增加业主端JSON接口` and push.
