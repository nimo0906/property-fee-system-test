#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for mock payment order flow."""

import os
import tempfile
import time
import unittest

_db_path = os.path.join(tempfile.gettempdir(), f'test_payment_orders_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups')

from server.db import db_init, get_db


class TestPaymentOrders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_module.DB_PATH = _db_path
        os.environ['PM_DB_PATH'] = _db_path
        db_init()

    @classmethod
    def tearDownClass(cls):
        for suffix in ('', '-wal', '-shm'):
            path = _db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def setUp(self):
        db_module.DB_PATH = _db_path
        os.environ['PM_DB_PATH'] = _db_path
        self.db = get_db()
        self.db.execute('PRAGMA foreign_keys=OFF')
        tables = {r['name'] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table in (
            'invoice_requests', 'notification_events', 'payment_callbacks', 'payment_orders',
            'payments', 'invoices', 'deposits', 'parking_spots', 'repairs', 'bill_adjustments',
            'meter_readings', 'bills', 'rooms', 'owners',
        ):
            if table in tables:
                self.db.execute(f'DELETE FROM {table}')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.owner_id = self.db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", ('支付订单业主', '13800135555')).lastrowid
        self.room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('支付座', '1单元', '2801', 28, '商户', 88, self.owner_id),
        ).lastrowid
        self.fee_type_id = self.db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", ('支付订单费', 'fixed', 100)).lastrowid
        self.bill_id = self.db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (self.room_id, self.owner_id, self.fee_type_id, '2027-04', 100, '2027-04-30', 'unpaid', 'PAY-ORDER-BILL'),
        ).lastrowid
        self.db.commit()
        self.order_no = 'PO202704010001'
        self.db.execute(
            "INSERT INTO payment_orders(order_no, owner_id, bill_id, amount, channel, status) VALUES(?,?,?,?,?,?)",
            (self.order_no, self.owner_id, self.bill_id, 100.0, 'mock', 'created'),
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_db_init_creates_payment_order_tables(self):
        tables = {r['name'] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertIn('payment_orders', tables)
        self.assertIn('payment_callbacks', tables)
        self.assertIn('notification_events', tables)

    def test_payment_order_service_no_longer_exposes_owner_portal_creation(self):
        from server.payment_orders import PaymentOrderService

        service = PaymentOrderService()

        self.assertFalse(hasattr(service, 'create_order'))
        self.assertFalse(hasattr(service, 'mark_mock_paid'))
        self.assertFalse(hasattr(service, 'list_orders'))
        self.assertFalse(hasattr(service, 'get_order'))

    def test_process_mock_callback_records_event_and_is_idempotent(self):
        from server.payment_orders import PaymentOrderService
        service = PaymentOrderService()
        order = {'order_no': self.order_no}

        first = service.process_callback({
            'channel': 'mock',
            'external_event_id': 'evt-001',
            'order_no': order['order_no'],
            'amount': '100.00',
            'raw_summary': 'mock callback success',
            'signature': 'mock-signature',
        })
        second = service.process_callback({
            'channel': 'mock',
            'external_event_id': 'evt-001',
            'order_no': order['order_no'],
            'amount': '100.00',
            'raw_summary': 'mock callback duplicate',
            'signature': 'mock-signature',
        })

        payment_count = self.db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (self.bill_id,)).fetchone()[0]
        callback_count = self.db.execute('SELECT COUNT(*) FROM payment_callbacks WHERE order_no=?', (order['order_no'],)).fetchone()[0]
        order_status = self.db.execute('SELECT status FROM payment_orders WHERE order_no=?', (order['order_no'],)).fetchone()['status']
        self.assertEqual(first['status'], 'processed')
        self.assertTrue(second['duplicate'])
        self.assertEqual(payment_count, 1)
        self.assertEqual(callback_count, 1)
        self.assertEqual(order_status, 'paid')


    def test_process_mock_callback_emits_payment_success_notification_event(self):
        from server.payment_orders import PaymentOrderService
        service = PaymentOrderService()
        order = {'order_no': self.order_no}

        service.process_callback({
            'channel': 'mock',
            'external_event_id': 'evt-notify-001',
            'order_no': order['order_no'],
            'amount': '100.00',
            'raw_summary': 'mock callback success',
            'signature': 'mock-signature',
        })

        rows = self.db.execute(
            "SELECT * FROM notification_events WHERE owner_id=? AND bill_id=? ORDER BY id",
            (self.owner_id, self.bill_id),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        event = rows[0]
        self.assertEqual(event['event_type'], 'payment_success')
        self.assertEqual(event['channel'], 'in_app')
        self.assertEqual(event['target'], '13800135555')
        self.assertEqual(event['status'], 'pending')
        self.assertIn(order['order_no'], event['payload'])


    def test_reconcile_order_summarizes_order_payment_and_callbacks(self):
        from server.payment_orders import PaymentOrderService
        service = PaymentOrderService()
        order = {'order_no': self.order_no}
        service.process_callback({
            'channel': 'mock',
            'external_event_id': 'evt-reconcile-001',
            'order_no': order['order_no'],
            'amount': '100.00',
            'signature': 'mock-signature',
        })

        result = service.reconcile_order(order['order_no'])

        self.assertEqual(result['order_no'], order['order_no'])
        self.assertEqual(result['order_status'], 'paid')
        self.assertEqual(result['payment_count'], 1)
        self.assertEqual(result['callback_count'], 1)
        self.assertEqual(result['expected_amount'], '100.00')
        self.assertEqual(result['paid_amount'], '100.00')
        self.assertEqual(result['reconcile_status'], 'matched')

    def test_process_callback_rejects_invalid_signature_before_recording(self):
        from server.payment_orders import PaymentOrderError, PaymentOrderService
        service = PaymentOrderService()
        order = {'order_no': self.order_no}

        with self.assertRaisesRegex(PaymentOrderError, '回调签名校验失败'):
            service.process_callback({
                'channel': 'mock',
                'external_event_id': 'evt-bad-sign',
                'order_no': order['order_no'],
                'amount': '100.00',
                'signature': 'bad-signature',
            })

        callback_count = self.db.execute('SELECT COUNT(*) FROM payment_callbacks WHERE order_no=?', (order['order_no'],)).fetchone()[0]
        payment_count = self.db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (self.bill_id,)).fetchone()[0]
        self.assertEqual(callback_count, 0)
        self.assertEqual(payment_count, 0)


if __name__ == '__main__':
    unittest.main()
