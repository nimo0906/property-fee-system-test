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
from server.owner_portal import OwnerPortalService


class TestPaymentOrders(unittest.TestCase):
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
        for table in ('notification_events', 'payment_callbacks', 'payment_orders', 'owner_portal_sessions', 'owner_portal_login_codes', 'payments', 'bills', 'rooms', 'owners'):
            if table in tables:
                self.db.execute(f'DELETE FROM {table}')
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
        service = OwnerPortalService()
        code = service.send_code('13800135555')['debug_code']
        token = service.login('13800135555', code)['token']
        self.session = service.get_session(token)

    def tearDown(self):
        self.db.close()

    def test_db_init_creates_payment_order_tables(self):
        tables = {r['name'] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertIn('payment_orders', tables)
        self.assertIn('payment_callbacks', tables)
        self.assertIn('notification_events', tables)

    def test_create_order_uses_owner_bill_and_does_not_write_payment(self):
        from server.payment_orders import PaymentOrderService

        result = PaymentOrderService().create_order(self.session, {
            'bill_id': str(self.bill_id),
            'amount': '70.00',
            'channel': 'mock',
            'idempotency_key': 'client-key-1',
        })
        count = self.db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (self.bill_id,)).fetchone()[0]

        self.assertTrue(result['order_no'].startswith('PO'))
        self.assertEqual(result['amount'], '70.00')
        self.assertEqual(result['status'], 'created')
        self.assertEqual(count, 0)

    def test_mock_paid_writes_payment_and_marks_order_paid_once(self):
        from server.payment_orders import PaymentOrderError, PaymentOrderService
        service = PaymentOrderService()
        order = service.create_order(self.session, {'bill_id': str(self.bill_id), 'amount': '100.00', 'channel': 'mock'})

        paid = service.mark_mock_paid(self.session, order['order_no'])
        payment_count = self.db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (self.bill_id,)).fetchone()[0]
        status = self.db.execute('SELECT status FROM bills WHERE id=?', (self.bill_id,)).fetchone()['status']

        self.assertEqual(paid['status'], 'paid')
        self.assertEqual(payment_count, 1)
        self.assertEqual(status, 'paid')
        with self.assertRaisesRegex(PaymentOrderError, '订单已支付'):
            service.mark_mock_paid(self.session, order['order_no'])
        payment_count_after = self.db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (self.bill_id,)).fetchone()[0]
        self.assertEqual(payment_count_after, 1)

    def test_list_orders_returns_owned_orders_with_bill_summary(self):
        from server.payment_orders import PaymentOrderService
        service = PaymentOrderService()
        order = service.create_order(self.session, {'bill_id': str(self.bill_id), 'amount': '80.00', 'channel': 'mock'})

        result = service.list_orders(self.session)

        self.assertEqual(len(result['items']), 1)
        item = result['items'][0]
        self.assertEqual(item['order_no'], order['order_no'])
        self.assertEqual(item['amount'], '80.00')
        self.assertEqual(item['status'], 'created')
        self.assertEqual(item['bill_number'], 'PAY-ORDER-BILL')
        self.assertEqual(item['period'], '2027-04')
        self.assertEqual(item['room_number'], '2801')

    def test_get_order_rejects_other_owner_order(self):
        from server.payment_orders import PaymentOrderError, PaymentOrderService
        service = PaymentOrderService()
        order = service.create_order(self.session, {'bill_id': str(self.bill_id), 'amount': '80.00', 'channel': 'mock'})
        other_owner_id = self.db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", ('其他业主', '13800135556')).lastrowid
        self.db.commit()
        other_session = {'owner_id': other_owner_id, 'phone': '13800135556', 'name': '其他业主'}

        with self.assertRaisesRegex(PaymentOrderError, '订单不存在'):
            service.get_order(other_session, order['order_no'])

    def test_create_order_returns_channel_preparation_payload(self):
        from server.payment_orders import PaymentOrderService

        order = PaymentOrderService().create_order(self.session, {
            'bill_id': str(self.bill_id),
            'amount': '70.00',
            'channel': 'mock',
        })

        self.assertEqual(order['channel_payload']['channel'], 'mock')
        self.assertEqual(order['channel_payload']['provider_status'], 'ready')
        self.assertIn('mock_pay_url', order['channel_payload'])

    def test_process_mock_callback_records_event_and_is_idempotent(self):
        from server.payment_orders import PaymentOrderService
        service = PaymentOrderService()
        order = service.create_order(self.session, {'bill_id': str(self.bill_id), 'amount': '100.00', 'channel': 'mock'})

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
        order = service.create_order(self.session, {'bill_id': str(self.bill_id), 'amount': '100.00', 'channel': 'mock'})

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

    def test_process_callback_rejects_invalid_signature_before_recording(self):
        from server.payment_orders import PaymentOrderError, PaymentOrderService
        service = PaymentOrderService()
        order = service.create_order(self.session, {'bill_id': str(self.bill_id), 'amount': '100.00', 'channel': 'mock'})

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
