#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP integration tests — starts a real server and tests via HTTP.

Covers:
  1. Server startup and page accessibility (21 pages)
  2. Login/logout flow
  3. Room CRUD
  4. Owner CRUD
  5. Bill generation and payment
  6. API endpoints
  7. CSV export
  8. Backup/restore

NOTE: Each test gets its own fresh cookie (setUp re-logs in).
"""

import unittest, os, sys, http.server, threading, time, json, tempfile, urllib.parse, re, http.client

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from datetime import date, timedelta
from unittest import mock
from tests.conftest import (
    BASE_URL, TEST_PORT,
    login_and_get_client, http_get, http_post, csrf_header_for_cookie,
    create_owner, create_room, create_bill, create_payment,
)


def http_get_with_location(path, cookie, port=TEST_PORT):
    conn = http.client.HTTPConnection(BASE_URL, port)
    conn.request('GET', path, headers={'Cookie': cookie})
    resp = conn.getresponse()
    body = resp.read().decode('utf-8')
    location = resp.getheader('Location', '')
    conn.close()
    return resp.status, body, location


def http_post_multipart(path, fields, files, cookie, port=TEST_PORT):
    boundary = '----PropertyTestBoundary'
    chunks = []
    for name, value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, file_info in files.items():
        filename, content_type, content = file_info
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f'Content-Type: {content_type}\r\n\r\n'.encode() + content + b'\r\n'
        )
    chunks.append(f'--{boundary}--\r\n'.encode())
    body = b''.join(chunks)
    conn = http.client.HTTPConnection(BASE_URL, port)
    headers = {
        'Cookie': cookie,
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body)),
    }
    headers['X-CSRF-Token'] = csrf_header_for_cookie(cookie)
    conn.request('POST', path, body, headers)
    resp = conn.getresponse()
    text = resp.read().decode('utf-8', errors='ignore')
    loc = resp.getheader('Location', '')
    conn.close()
    return resp.status, text, loc


def _start_server():
    """Start the server once for the whole test class."""
    os.environ['PM_DB_PATH'] = os.path.join(
        tempfile.gettempdir(), f'test_integration_{int(time.time())}.db'
    )

    import server.db as db_module
    db_module.DB_PATH = os.environ['PM_DB_PATH']
    db_module.BACKUP_DIR = os.path.join(os.path.dirname(db_module.DB_PATH), 'backups')

    from server import Handler, db_init

    db_init()
    srv = http.server.ThreadingHTTPServer((BASE_URL, TEST_PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    return srv


class IntegrationTestBase(unittest.TestCase):
    """Full-stack HTTP integration tests."""

    @classmethod
    def setUpClass(cls):
        cls.server = _start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.server_close()
        time.sleep(0.1)

    def setUp(self):
        """Get a fresh cookie before each test."""
        self.cookie = login_and_get_client(TEST_PORT)


    def _create_user_and_login(self, username, password, role, display_name='测试用户'):
        http_post('/users/create', {
            'username': username,
            'password': password,
            'display_name': display_name,
            'role': role,
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': username, 'password': password})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        resp.read()
        cookie = resp.getheader('Set-Cookie', '').split(';')[0]
        conn.close()
        return cookie

    def _ensure_room_for_billing(self):
        """Helper: create a room if none exists."""
        _, body = http_get('/rooms', self.cookie, TEST_PORT)
        if '暂无房间' in body:
            http_post('/rooms/create', {
                'building': 'B座', 'unit': 'A座', 'room_number': '801',
                'floor': '8', 'category': '居民', 'area': '100',
            }, self.cookie, TEST_PORT)

    def _create_api_payment_bill(self, bill_number, amount=90.0):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", (bill_number + '业主', '13800138004')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('PAYAPI座', '1单元', bill_number[-4:], 12, '商户', 90, owner_id),
        ).lastrowid
        fee_type_id = db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", (bill_number + '费用', 'fixed', amount)).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_type_id, '2026-12', amount, '2026-12-31', 'unpaid', bill_number),
        ).lastrowid
        db.commit()
        db.close()
        return owner_id, room_id, fee_type_id, bill_id

    def _cleanup_api_payment_bill(self, owner_id, room_id, fee_type_id, bill_id):
        import server.db as db_module
        db = db_module.get_db()
        db.execute('DELETE FROM audit_logs WHERE entity_type=? AND entity_id IN (SELECT id FROM payments WHERE bill_id=?)', ('payment', bill_id))
        db.execute('DELETE FROM payments WHERE bill_id=?', (bill_id,))
        db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
        db.execute('DELETE FROM fee_types WHERE id=?', (fee_type_id,))
        db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
        db.commit()
        db.close()

