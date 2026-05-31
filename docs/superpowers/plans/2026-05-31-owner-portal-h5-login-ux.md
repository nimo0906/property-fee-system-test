# Owner Portal H5 Login UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make owner portal login usable without manual API calls by adding send-code action and logout.

**Architecture:** Keep server-rendered H5. Add `POST /owner-portal/send-code` to generate a debug code and re-render login page with the code for local testing. Add `/owner-portal/logout` to clear `owner_portal_token`. No external SMS integration.

**Tech Stack:** Python `http.server`, existing `OwnerPortalService`, server-rendered HTML, pytest integration tests.

---

## Files

- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/owner_portal_pages.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/base.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/templates/owner_portal_login.html`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/templates/owner_portal_base.html`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_integration.py`

## Tasks

- [ ] Add failing tests for H5 send-code showing debug code and logout clearing cookie.
- [ ] Implement send-code POST route and logout route.
- [ ] Update login/base templates with send-code and logout links.
- [ ] Verify focused tests, full suite, py_compile.
- [ ] Commit with `feat: 完善业主端验证码和退出登录` and push.
