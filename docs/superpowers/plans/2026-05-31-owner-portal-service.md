# Owner Portal Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement owner portal schema and service-layer login/session primitives for later H5 and small-program APIs.

**Architecture:** Add owner portal tables in `db_init()` using additive `CREATE TABLE IF NOT EXISTS` statements. Create a focused `server/owner_portal.py` service module for verification code generation, hashing, login, session lookup, expiry, and repeated-phone safeguards. Keep this stage API-free except tests; API routes will be a later stage.

**Tech Stack:** Python standard library, SQLite, existing `server.db`, `unittest`/`pytest`.

---

## Files

- Modify: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/db.py`
- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/server/owner_portal.py`
- Create: `/Users/nimo/Documents/物业管理系统测试版本/测试版本/tests/test_owner_portal_service.py`

## Task 1: Schema tests and db_init tables

- [ ] Write failing test that `db_init()` creates `owner_portal_login_codes` and `owner_portal_sessions`.
- [ ] Run focused test and confirm failure.
- [ ] Add both tables to `db_init()`.
- [ ] Run focused test and confirm pass.

## Task 2: Verification code generation and hashing

- [ ] Write failing tests for `OwnerPortalService.send_code()` returning a 6-digit debug code, storing only a hash, and rejecting repeated-phone owners.
- [ ] Implement minimal service code.
- [ ] Run focused tests.

## Task 3: Login and session lifecycle

- [ ] Write failing tests for successful login, code reuse rejection, wrong-code attempt limit, expired-code rejection, and session lookup.
- [ ] Implement login and session lookup.
- [ ] Run focused tests.

## Task 4: Verification and publish

- [ ] Run `python3 -m pytest tests/test_owner_portal_service.py -q`.
- [ ] Run `python3 -m pytest -q`.
- [ ] Run `PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m py_compile server.py desktop_app.py desktop_runtime.py server/*.py`.
- [ ] Commit with `feat: 增加业主端身份服务`.
- [ ] Push `main`.
