# Owner Portal H5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal mobile-friendly owner portal H5 flow for login, dashboard, bills, bill detail, and payment history.

**Architecture:** Add an `OwnerPortalMixin` for server-rendered H5 pages under `/owner-portal/...`. Pages use the existing `OwnerPortalService` and `owner_portal_token` cookie. Keep the H5 isolated from backend operator pages and reuse Bootstrap CDN for low-risk styling.

**Tech Stack:** Python `http.server`, existing service layer, server-rendered HTML, Bootstrap 5, pytest HTTP integration tests.

---

## Files

- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/owner_portal_pages.py`
- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/templates/owner_portal_base.html`
- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/templates/owner_portal_login.html`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/__init__.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/base.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_integration.py`
- Modify: PyInstaller specs to include new templates through existing `templates` folder inclusion; no spec change expected.

## Tasks

- [ ] Add failing HTTP tests for owner portal login page, login flow, dashboard, bills, bill detail, payments, and auth redirect.
- [ ] Implement owner portal page mixin and templates.
- [ ] Route `/owner-portal/...` in `BaseHandler` and register mixin in `Handler`.
- [ ] Verify focused tests, full suite, py_compile.
- [ ] Commit with `feat: 增加业主端H5最小页面` and push.
