#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for v2.0 core service interfaces."""

import os
import tempfile
import time
import unittest

_db_path = os.path.join(tempfile.gettempdir(), f'test_services_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups')

from server.db import db_init, get_db
from server.services import OwnerService, RoomService


class TestOwnerAndRoomServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_init()

    @classmethod
    def tearDownClass(cls):
        for suffix in ('', '-wal', '-shm'):
            path = _db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def setUp(self):
        self.db = get_db()
        for table in ('payments', 'bills', 'rooms', 'owners'):
            self.db.execute(f'DELETE FROM {table}')
        self.owner_id = self.db.execute(
            "INSERT INTO owners (name, phone, id_card) VALUES (?, ?, ?)",
            ('张三', '13800138000', '610100199001011234'),
        ).lastrowid
        self.room_id = self.db.execute(
            "INSERT INTO rooms (building, unit, room_number, floor, category, area, owner_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ('B座', '1单元', '1801', 18, '商户', 88.5, self.owner_id),
        ).lastrowid
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_owner_detail_masks_sensitive_id_card_and_includes_rooms(self):
        owner = OwnerService().get_owner(self.owner_id)

        self.assertEqual(owner['id'], self.owner_id)
        self.assertEqual(owner['name'], '张三')
        self.assertEqual(owner['phone'], '13800138000')
        self.assertEqual(owner['id_card_masked'], '610100********1234')
        self.assertNotIn('id_card', owner)
        self.assertEqual(owner['rooms'][0]['room_number'], '1801')

    def test_room_detail_includes_owner_summary(self):
        room = RoomService().get_room(self.room_id)

        self.assertEqual(room['id'], self.room_id)
        self.assertEqual(room['building'], 'B座')
        self.assertEqual(room['area'], 88.5)
        self.assertEqual(room['owner']['id'], self.owner_id)
        self.assertEqual(room['owner']['name'], '张三')

    def test_billing_service_get_bill_returns_amount_breakdown(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试物业费', 'area', 2.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-05', 177.0, '2026-05-31', 'unpaid', 'BILL-SVC-1'),
        ).lastrowid
        self.db.execute(
            "INSERT INTO payments (bill_id, amount_paid, payment_date, payment_method, operator) "
            "VALUES (?, ?, datetime('now','localtime'), ?, ?)",
            (bill_id, 77.0, 'cash', 'admin'),
        )
        self.db.commit()

        from server.services import BillingService
        bill = BillingService().get_bill(bill_id)

        self.assertEqual(bill['id'], bill_id)
        self.assertEqual(bill['bill_number'], 'BILL-SVC-1')
        self.assertEqual(bill['amount'], '177.00')
        self.assertEqual(bill['paid_amount'], '77.00')
        self.assertEqual(bill['unpaid_amount'], '100.00')
        self.assertEqual(bill['room']['room_number'], '1801')
        self.assertEqual(bill['owner']['name'], '张三')

    def test_billing_generation_preview_does_not_write_bills(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试面积费', 'area', 3.0),
        ).lastrowid
        self.db.commit()

        from server.services import BillingService
        before = self.db.execute('SELECT COUNT(*) FROM bills').fetchone()[0]
        plan = BillingService().preview_generation({
            'period': '2026-06',
            'due_date': '2026-06-30',
            'fee_type_ids': [fee_type_id],
        })
        after = self.db.execute('SELECT COUNT(*) FROM bills').fetchone()[0]

        self.assertEqual(before, after)
        self.assertEqual(plan['period'], '2026-06')
        self.assertEqual(plan['items'][0]['room_id'], self.room_id)
        self.assertEqual(plan['items'][0]['amount'], '265.50')


if __name__ == '__main__':
    unittest.main()
