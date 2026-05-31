#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for owner portal login and session service."""

import os
import tempfile
import time
import unittest

_db_path = os.path.join(tempfile.gettempdir(), f'test_owner_portal_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups')

from server.db import db_init, get_db


class TestOwnerPortalSchema(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for suffix in ('', '-wal', '-shm'):
            path = _db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def test_db_init_creates_owner_portal_tables(self):
        db_init()
        db = get_db()
        try:
            tables = {
                row['name']
                for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            self.assertIn('owner_portal_login_codes', tables)
            self.assertIn('owner_portal_sessions', tables)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()

class TestOwnerPortalService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_init()

    def setUp(self):
        self.db = get_db()
        for table in ('owner_portal_sessions', 'owner_portal_login_codes', 'payments', 'invoices', 'bill_adjustments', 'bills', 'meter_readings', 'deposits', 'parking_spots', 'repairs', 'rooms', 'owners'):
            self.db.execute(f'DELETE FROM {table}')
        self.owner_id = self.db.execute(
            "INSERT INTO owners(name, phone, id_card) VALUES(?,?,?)",
            ('业主端测试', '13800138009', '610100199001011234'),
        ).lastrowid
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_send_code_returns_debug_code_and_stores_only_hash(self):
        from server.owner_portal import OwnerPortalService

        result = OwnerPortalService().send_code('13800138009')
        row = self.db.execute(
            'SELECT phone, code_hash, used_at, attempt_count FROM owner_portal_login_codes WHERE phone=?',
            ('13800138009',),
        ).fetchone()

        self.assertEqual(result['message'], '验证码已发送')
        self.assertRegex(result['debug_code'], r'^\d{6}$')
        self.assertEqual(row['phone'], '13800138009')
        self.assertNotEqual(row['code_hash'], result['debug_code'])
        self.assertIsNone(row['used_at'])
        self.assertEqual(row['attempt_count'], 0)

    def test_send_code_rejects_phone_bound_to_multiple_owners(self):
        self.db.execute("INSERT INTO owners(name, phone) VALUES(?,?)", ('重复业主', '13800138009'))
        self.db.commit()

        from server.owner_portal import OwnerPortalError, OwnerPortalService
        with self.assertRaisesRegex(OwnerPortalError, '手机号绑定多个业主'):
            OwnerPortalService().send_code('13800138009')

    def test_login_creates_session_and_get_session_returns_owner(self):
        from server.owner_portal import OwnerPortalService
        service = OwnerPortalService()
        code = service.send_code('13800138009')['debug_code']

        result = service.login('13800138009', code)
        session = service.get_session(result['token'])
        used = self.db.execute(
            'SELECT used_at FROM owner_portal_login_codes WHERE phone=? ORDER BY id DESC LIMIT 1',
            ('13800138009',),
        ).fetchone()

        self.assertEqual(result['owner_id'], self.owner_id)
        self.assertEqual(result['name'], '业主端测试')
        self.assertTrue(result['token'])
        self.assertIsNotNone(used['used_at'])
        self.assertEqual(session['owner_id'], self.owner_id)
        self.assertEqual(session['phone'], '13800138009')

    def test_login_rejects_code_reuse(self):
        from server.owner_portal import OwnerPortalError, OwnerPortalService
        service = OwnerPortalService()
        code = service.send_code('13800138009')['debug_code']
        service.login('13800138009', code)

        with self.assertRaisesRegex(OwnerPortalError, '验证码无效'):
            service.login('13800138009', code)

    def test_login_rejects_wrong_code_after_five_attempts(self):
        from server.owner_portal import OwnerPortalError, OwnerPortalService
        service = OwnerPortalService()
        service.send_code('13800138009')

        for _ in range(5):
            with self.assertRaisesRegex(OwnerPortalError, '验证码错误'):
                service.login('13800138009', '000000')
        with self.assertRaisesRegex(OwnerPortalError, '验证码无效'):
            service.login('13800138009', '000000')

    def test_login_rejects_expired_code(self):
        from server.owner_portal import OwnerPortalError, OwnerPortalService
        service = OwnerPortalService()
        code = service.send_code('13800138009')['debug_code']
        self.db.execute(
            "UPDATE owner_portal_login_codes SET expires_at='2000-01-01 00:00:00' WHERE phone=?",
            ('13800138009',),
        )
        self.db.commit()

        with self.assertRaisesRegex(OwnerPortalError, '验证码已过期'):
            service.login('13800138009', code)

    def test_get_session_rejects_expired_or_revoked_session(self):
        from server.owner_portal import OwnerPortalError, OwnerPortalService
        service = OwnerPortalService()
        code = service.send_code('13800138009')['debug_code']
        token = service.login('13800138009', code)['token']
        self.db.execute(
            "UPDATE owner_portal_sessions SET expires_at='2000-01-01 00:00:00' WHERE token=?",
            (token,),
        )
        self.db.commit()

        with self.assertRaisesRegex(OwnerPortalError, '登录已失效'):
            service.get_session(token)
