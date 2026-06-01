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
        tables = {r['name'] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table in ('invoice_requests', 'payments', 'invoices', 'bills', 'rooms', 'owners'):
            if table in tables:
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

    def test_billing_generation_preview_uses_shared_billing_rules_and_filters(self):
        commercial_owner = self.db.execute("INSERT INTO owners (name) VALUES ('商业预览业主')").lastrowid
        commercial_room = self.db.execute(
            "INSERT INTO rooms (building, unit, room_number, floor, category, area, owner_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ('B座', '1单元', '1901', 19, '商户', 50, commercial_owner),
        ).lastrowid
        resident_fee = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price, sort_order) VALUES (?, ?, ?, ?)",
            ('服务费(居民)', 'fixed', 99.0, 1),
        ).lastrowid
        household_fee = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price, sort_order) VALUES (?, ?, ?, ?)",
            ('按户测试费', 'household', 12.0, 2),
        ).lastrowid
        self.db.commit()

        from server.services import BillingService
        plan = BillingService().preview_generation({
            'period': '2026-06',
            'due_date': '2026-06-30',
            'fee_type_ids': [resident_fee, household_fee],
            'building': 'B座',
        })

        item_keys = {(x['room_id'], x['fee_type_id']) for x in plan['items']}
        self.assertNotIn((commercial_room, resident_fee), item_keys)
        self.assertIn((self.room_id, household_fee), item_keys)
        self.assertIn((commercial_room, household_fee), item_keys)
        amounts = {x['room_id']: x['amount'] for x in plan['items'] if x['fee_type_id'] == household_fee}
        self.assertEqual(amounts[self.room_id], '12.00')
        self.assertEqual(amounts[commercial_room], '12.00')

    def test_invoice_request_service_creates_pending_request_for_paid_bill(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试电子票据费', 'fixed', 120.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-09', 120.0, '2026-09-30', 'paid', 'BILL-INV-REQ-1'),
        ).lastrowid
        self.db.commit()

        from server.invoice_requests import InvoiceRequestService
        request = InvoiceRequestService().create_request({
            'bill_id': bill_id,
            'buyer_name': '张三',
            'buyer_tax_id': 'TAX-001',
            'idempotency_key': 'invoice-key-1',
        })

        row = self.db.execute('SELECT * FROM invoice_requests WHERE bill_id=?', (bill_id,)).fetchone()
        self.assertEqual(request['status'], 'pending')
        self.assertTrue(request['request_no'].startswith('IR'))
        self.assertEqual(request['amount'], '120.00')
        self.assertEqual(row['buyer_name'], '张三')
        self.assertEqual(row['status'], 'pending')

    def test_invoice_request_service_is_idempotent_by_key(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试电子票据幂等费', 'fixed', 80.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-10', 80.0, '2026-10-31', 'paid', 'BILL-INV-REQ-2'),
        ).lastrowid
        self.db.commit()

        from server.invoice_requests import InvoiceRequestService
        service = InvoiceRequestService()
        first = service.create_request({'bill_id': bill_id, 'idempotency_key': 'same-key'})
        second = service.create_request({'bill_id': bill_id, 'idempotency_key': 'same-key'})

        count = self.db.execute('SELECT COUNT(*) FROM invoice_requests WHERE bill_id=?', (bill_id,)).fetchone()[0]
        self.assertEqual(first['request_no'], second['request_no'])
        self.assertEqual(count, 1)

    def test_invoice_request_service_rejects_unpaid_bill(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试未缴票据费', 'fixed', 60.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-11', 60.0, '2026-11-30', 'unpaid', 'BILL-INV-REQ-3'),
        ).lastrowid
        self.db.commit()

        from server.invoice_requests import InvoiceRequestError, InvoiceRequestService
        with self.assertRaisesRegex(InvoiceRequestError, '仅已缴清账单可申请电子票据'):
            InvoiceRequestService().create_request({'bill_id': bill_id})


    def test_payment_preview_rejects_amount_greater_than_unpaid(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试停车费', 'fixed', 100.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-07', 100.0, '2026-07-31', 'unpaid', 'BILL-PAY-1'),
        ).lastrowid
        self.db.commit()

        from server.services import PaymentService, ServiceError
        with self.assertRaisesRegex(ServiceError, '收款金额不能超过欠费金额'):
            PaymentService().preview_payment({'bill_id': bill_id, 'amount': '120.00'})

    def test_payment_create_marks_bill_paid_when_fully_collected(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试垃圾费', 'fixed', 10.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-08', 10.0, '2026-08-31', 'unpaid', 'BILL-PAY-2'),
        ).lastrowid
        self.db.commit()

        from server.services import Actor, PaymentService
        result = PaymentService().create_payment(
            {'bill_id': bill_id, 'amount': '10.00', 'method': 'cash'},
            Actor(username='admin', role='admin'),
        )
        bill = self.db.execute('SELECT status, paid_at FROM bills WHERE id=?', (bill_id,)).fetchone()
        payment = self.db.execute('SELECT receipt_number, notes FROM payments WHERE id=?', (result['payment_id'],)).fetchone()

        self.assertEqual(result['amount'], '10.00')
        self.assertEqual(result['bill_status'], 'paid')
        self.assertEqual(bill['status'], 'paid')
        self.assertIsNotNone(bill['paid_at'])
        self.assertIsNone(payment['receipt_number'])

    def test_payment_create_accepts_receipt_and_notes_for_ui_collection(self):
        fee_type_id = self.db.execute(
            "INSERT INTO fee_types (name, calc_method, unit_price) VALUES (?, ?, ?)",
            ('测试收据费', 'fixed', 30.0),
        ).lastrowid
        bill_id = self.db.execute(
            "INSERT INTO bills (room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.room_id, self.owner_id, fee_type_id, '2026-09', 30.0, '2026-09-30', 'unpaid', 'BILL-PAY-RECEIPT'),
        ).lastrowid
        self.db.commit()

        from server.services import Actor, PaymentService
        result = PaymentService().create_payment(
            {'bill_id': bill_id, 'amount': '30.00', 'method': 'cash', 'receipt_number': 'RC-SVC-1', 'notes': '服务层收款'},
            Actor(username='cashier', role='operator'),
        )

        payment = self.db.execute('SELECT receipt_number, notes, operator FROM payments WHERE id=?', (result['payment_id'],)).fetchone()
        self.assertEqual(payment['receipt_number'], 'RC-SVC-1')
        self.assertEqual(payment['notes'], '服务层收款')
        self.assertEqual(payment['operator'], 'cashier')



if __name__ == '__main__':
    unittest.main()
