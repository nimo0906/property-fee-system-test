# v2.0 Readonly JSON API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authenticated readonly `/api/v1` JSON endpoints for owner, room, and bill details using the new core services.

**Architecture:** Add a focused `ApiMixin` that owns JSON API response format and routes. `BaseHandler` delegates `/api/v1/...` requests to the mixin before normal HTML auth redirects so API clients receive JSON errors instead of login HTML. Existing desktop HTML routes remain unchanged.

**Tech Stack:** Python standard library `http.server`, existing `server.services`, SQLite, `pytest` integration tests.

---

## Files

- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/api.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/__init__.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/base.py`
- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_integration.py`

## Task 1: Add failing integration tests

- [ ] Add tests to `tests/test_integration.py` for:
  - unauthenticated `GET /api/v1/owners/1` returns `401` JSON `{ok:false,error:{code:"unauthorized"}}`
  - authenticated `GET /api/v1/owners/{id}` returns owner data with masked ID card and no raw `id_card`
  - authenticated `GET /api/v1/rooms/{id}` returns room and owner summary
  - authenticated `GET /api/v1/bills/{id}` returns amount breakdown
- [ ] Run `python3 -m pytest tests/test_integration.py -q` and confirm failure because API routes are missing.

## Task 2: Implement ApiMixin and route delegation

- [ ] Create `server/api.py` with `_api_json`, `_api_error`, and `_api_get`.
- [ ] Route:
  - `GET /api/v1/owners/<id>` -> `OwnerService().get_owner(id)`
  - `GET /api/v1/rooms/<id>` -> `RoomService().get_room(id)`
  - `GET /api/v1/bills/<id>` -> `BillingService().get_bill(id)`
- [ ] Add `ApiMixin` to `server/__init__.py` Handler before `BaseHandler`.
- [ ] Add `/api/v1/` early delegation in `BaseHandler.do_GET` before normal login redirect.
- [ ] Update the integration test local Handler to include `ApiMixin`.
- [ ] Run `python3 -m pytest tests/test_integration.py -q` and confirm pass.

## Task 3: Verify and commit

- [ ] Run `python3 -m pytest tests/test_core_services.py tests/test_integration.py -q`.
- [ ] Run `python3 -m pytest -q`.
- [ ] Run `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py`.
- [ ] Commit with `feat: 增加核心只读JSON接口`.
