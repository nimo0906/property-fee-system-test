#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSRF protection integration tests."""

import http.client
import re
import urllib.parse

from tests.integration_base import IntegrationTestBase, TEST_PORT, BASE_URL, http_get, http_post, http_post_multipart
from tests.conftest import create_owner, create_room, create_bill


def _csrf_from_html(html):
    match = re.search(r'name="_csrf_token" value="([^"]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    return match.group(1) if match else ''


def _post_with_header(path, data, cookie, token, port=TEST_PORT):
    conn = http.client.HTTPConnection(BASE_URL, port)
    params = urllib.parse.urlencode(data)
    conn.request('POST', path, params, {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': cookie,
        'X-CSRF-Token': token,
    })
    resp = conn.getresponse()
    body = resp.read().decode('utf-8')
    location = resp.getheader('Location', '')
    conn.close()
    return resp.status, body, location


def _post_without_csrf(path, data, cookie, port=TEST_PORT):
    conn = http.client.HTTPConnection(BASE_URL, port)
    params = urllib.parse.urlencode(data)
    conn.request('POST', path, params, {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': cookie,
    })
    resp = conn.getresponse()
    body = resp.read().decode('utf-8')
    location = resp.getheader('Location', '')
    conn.close()
    return resp.status, body, location


def _multipart_without_csrf(path, fields, files, cookie, port=TEST_PORT):
    boundary = '----PropertyNoCsrfBoundary'
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
    conn.request('POST', path, body, {
        'Cookie': cookie,
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body)),
    })
    resp = conn.getresponse()
    text = resp.read().decode('utf-8', errors='ignore')
    loc = resp.getheader('Location', '')
    conn.close()
    return resp.status, text, loc


class TestCsrfProtection(IntegrationTestBase):
    def test_backend_post_without_csrf_token_is_rejected(self):
        status, body, loc = _post_without_csrf('/owners/create', {
            'name': '无令牌业主',
            'phone': '13900009901',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 403)
        self.assertIn('CSRF', body)

    def test_backend_form_includes_token_and_accepts_it(self):
        status, html = http_get('/owners/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        token = _csrf_from_html(html)
        self.assertTrue(token)

        status, body, loc = http_post('/owners/create', {
            '_csrf_token': token,
            'name': '有令牌业主',
            'phone': '13900009902',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('/owners', loc)

    def test_api_post_requires_header_token_and_accepts_it(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, 'CSRF接口业主', '13900009903')
        room_id = create_room(db, building='CSRFAPI', room_number='101', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, owner_id=owner_id, amount=30, status='unpaid')
        db.close()

        status, body, _ = _post_without_csrf('/api/v1/payments/preview', {
            'bill_id': str(bill_id),
            'amount': '10.0',
            'method': 'cash',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 403)
        self.assertIn('csrf', body.lower())

        _, owners_html = http_get('/owners', self.cookie, TEST_PORT)
        token = _csrf_from_html(owners_html)
        status, body, _ = _post_with_header('/api/v1/payments/preview', {
            'bill_id': str(bill_id),
            'amount': '10.0',
            'method': 'cash',
        }, self.cookie, token, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('"ok": true', body)

    def test_login_is_not_blocked_by_csrf(self):
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        resp.read()
        cookie = resp.getheader('Set-Cookie', '')
        conn.close()

        self.assertEqual(resp.status, 302)
        self.assertIn('session_token=', cookie)

    def test_multipart_upload_requires_csrf_token(self):
        status, body, loc = _multipart_without_csrf('/import/upload',
            {'mode': 'preview', 'data_type': 'owners'},
            {'file': ('owners.csv', 'text/csv', '姓名,电话\n令牌上传业主,13900009904\n'.encode('utf-8'))},
            self.cookie,
            TEST_PORT,
        )
        self.assertEqual(status, 403)
        self.assertIn('CSRF', body)

        _, import_html = http_get('/import', self.cookie, TEST_PORT)
        token = _csrf_from_html(import_html)
        status, body, loc = http_post_multipart('/import/upload',
            {'_csrf_token': token, 'mode': 'preview', 'data_type': 'owners'},
            {'file': ('owners.csv', 'text/csv', '姓名,电话\n令牌上传业主,13900009904\n'.encode('utf-8'))},
            self.cookie,
            TEST_PORT,
        )
        self.assertEqual(status, 200)
        self.assertIn('令牌上传业主', body)
