#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared test fixtures and helpers.

Usage:
    from tests.conftest import (
        TestCaseWithDB,        # TestCase with a fresh test database
        TestCaseWithServer,    # TestCase with a running HTTP server + cookie
        create_room, create_owner, create_bill, create_payment,
        login_and_get_cookie, BASE_URL,
    )
"""

import os, sys, json, http.client, urllib.parse, threading, time, tempfile, shutil
from server.csrf import csrf_token_for_session, session_token_from_cookie

# ── Ensure project root is on path ──────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DB_PATH_OVERRIDE = None  # set by TestCaseWithDB

# ── HTTP test constants ─────────────────────────────────────────
BASE_URL = '127.0.0.1'
TEST_PORT = 15999


def login_and_get_client(port=TEST_PORT):
    """Login as admin, return http.client.HTTPSession-like object (cookie string)."""
    conn = http.client.HTTPConnection(BASE_URL, port)
    params = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'})
    conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
    resp = conn.getresponse()
    resp.read()
    cookie = resp.getheader('Set-Cookie', '').split(';')[0]
    conn.close()
    return cookie


def http_get(path, cookie, port=TEST_PORT):
    """Make authenticated GET request, return (status, body_str)."""
    conn = http.client.HTTPConnection(BASE_URL, port)
    conn.request('GET', path, headers={'Cookie': cookie})
    resp = conn.getresponse()
    body = resp.read().decode('utf-8')
    conn.close()
    return resp.status, body


def csrf_header_for_cookie(cookie):
    return csrf_token_for_session(session_token_from_cookie(cookie or ''))


def http_post(path, data, cookie, port=TEST_PORT):
    """Make authenticated POST request, return (status, body_str, redirect_url)."""
    conn = http.client.HTTPConnection(BASE_URL, port)
    params = urllib.parse.urlencode(data)
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': cookie,
    }
    if path not in ('/login', '/register'):
        headers['X-CSRF-Token'] = csrf_header_for_cookie(cookie)
    conn.request('POST', path, params, headers)
    resp = conn.getresponse()
    body = resp.read().decode('utf-8')
    location = resp.getheader('Location', '')
    conn.close()
    return resp.status, body, location


def create_room(db, building='B座', unit='A座', room_number='701',
                floor=7, category='居民', area=100.0, owner_id=None):
    """Helper: insert a test room and return its id."""
    c = db.execute(
        "INSERT INTO rooms (building, unit, room_number, floor, category, area, owner_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (building, unit, room_number, floor, category, area, owner_id)
    )
    db.commit()
    return c.lastrowid


def create_owner(db, name='测试业主', phone='13800138000'):
    """Helper: insert a test owner and return its id."""
    c = db.execute("INSERT INTO owners (name, phone) VALUES (?, ?)", (name, phone))
    db.commit()
    return c.lastrowid


def create_bill(db, room_id=1, fee_type_id=1, period='2026-05',
                amount=100.0, status='unpaid', owner_id=None):
    """Helper: insert a test bill and return its id."""
    bn = f"TEST_{room_id}_{fee_type_id}_{period}_{int(time.time())}"
    c = db.execute(
        "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (room_id, owner_id, fee_type_id, period, amount, '2026-05-28', status, bn)
    )
    db.commit()
    return c.lastrowid


def create_payment(db, bill_id=1, amount=100.0, method='cash', operator='测试'):
    """Helper: insert a test payment."""
    c = db.execute(
        "INSERT INTO payments (bill_id, amount_paid, payment_date, payment_method, operator) "
        "VALUES (?, ?, datetime('now','localtime'), ?, ?)",
        (bill_id, amount, method, operator)
    )
    db.commit()
    return c.lastrowid
