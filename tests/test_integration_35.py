#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 35."""

from tests.integration_base import *


class TestIntegration35(IntegrationTestBase):
    def test_api_v1_payment_preview_rejects_overpay_as_json_validation_error(self):
        import server.db as db_module

        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", ('超额业主', '13800138003')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('OVERPAY座', '1单元', '2401', 24, '商户', 80, owner_id),
        ).lastrowid
        fee_type_id = db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", ('超额测试费', 'fixed', 50)).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_type_id, '2026-11', 50, '2026-11-30', 'unpaid', 'API-PREVIEW-OVERPAY'),
        ).lastrowid
        db.commit()
        db.close()

        status, body, _ = http_post('/api/v1/payments/preview', {
            'bill_id': str(bill_id),
            'amount': '60.00',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'validation_error')
        self.assertIn('收款金额不能超过欠费金额', payload['error']['message'])

        db = db_module.get_db()
        db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
        db.execute('DELETE FROM fee_types WHERE id=?', (fee_type_id,))
        db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
        for table_name in ('payments', 'bills', 'fee_types', 'rooms', 'owners'):
            remaining = db.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
            if remaining == 0:
                db.execute('DELETE FROM sqlite_sequence WHERE name=?', (table_name,))
        db.commit()
        db.close()


    def test_api_v1_payment_create_rejects_readonly_user(self):
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('API-PAY-READONLY', 90.0)
        username = 'readonly_api_pay'
        http_post('/users/create', {
            'username': username,
            'password': 'readonly123',
            'display_name': '只读API测试',
            'role': 'readonly',
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': username, 'password': 'readonly123'})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        resp.read()
        readonly_cookie = resp.getheader('Set-Cookie', '').split(';')[0]
        conn.close()

        status, body, _ = http_post('/api/v1/payments', {
            'bill_id': str(bill_id),
            'amount': '10.00',
            'method': 'cash',
        }, readonly_cookie, TEST_PORT)

        self.assertEqual(status, 403)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'forbidden')
        self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)

    def test_api_v1_payment_routes_reject_frontdesk_user(self):
        import server.db as db_module
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('API-PAY-FRONTDESK', 90.0)
        frontdesk_cookie = self._create_user_and_login(
            'frontdesk_api_pay', 'frontdesk123', 'frontdesk', '客服API测试'
        )

        for path in ('/api/v1/payments/preview', '/api/v1/payments'):
            status, body, _ = http_post(path, {
                'bill_id': str(bill_id),
                'amount': '10.00',
                'method': 'cash',
            }, frontdesk_cookie, TEST_PORT)

            self.assertEqual(status, 403, path)
            payload = json.loads(body)
            self.assertFalse(payload['ok'])
            self.assertEqual(payload['error']['code'], 'forbidden')

        db = db_module.get_db()
        payment_count = db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (bill_id,)).fetchone()[0]
        db.close()
        self.assertEqual(payment_count, 0)
        self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)


    def test_api_v1_payment_create_writes_payment_backup_and_audit(self):
        import server.db as db_module
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('API-PAY-CREATE', 90.0)
        before_backups = set(os.listdir(db_module.BACKUP_DIR)) if os.path.exists(db_module.BACKUP_DIR) else set()

        status, body, _ = http_post('/api/v1/payments', {
            'bill_id': str(bill_id),
            'amount': '90.00',
            'method': 'cash',
            'idempotency_key': 'future-key-1',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['amount'], '90.00')
        self.assertEqual(payload['data']['bill_status'], 'paid')
        self.assertEqual(payload['data']['idempotency_key'], 'future-key-1')
        self.assertTrue(payload['data']['backup_name'].startswith('auto_before_api_payment_'))

        db = db_module.get_db()
        bill = db.execute('SELECT status FROM bills WHERE id=?', (bill_id,)).fetchone()
        payment = db.execute('SELECT id, amount_paid FROM payments WHERE bill_id=?', (bill_id,)).fetchone()
        audit = db.execute(
            "SELECT action FROM audit_logs WHERE action='api_payment_create' AND entity_type='payment' AND entity_id=?",
            (payment['id'],),
        ).fetchone()
        db.close()
        after_backups = set(os.listdir(db_module.BACKUP_DIR))

        self.assertEqual(bill['status'], 'paid')
        self.assertAlmostEqual(payment['amount_paid'], 90.0)
        self.assertIsNotNone(audit)
        self.assertTrue(any(name.startswith('auto_before_api_payment_') for name in after_backups - before_backups))
        self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)


    def test_api_v1_payment_create_rejects_overpay_without_writing(self):
        import server.db as db_module
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('API-PAY-OVERPAY', 30.0)

        status, body, _ = http_post('/api/v1/payments', {
            'bill_id': str(bill_id),
            'amount': '31.00',
            'method': 'cash',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'validation_error')
        db = db_module.get_db()
        count = db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (bill_id,)).fetchone()[0]
        db.close()
        self.assertEqual(count, 0)
        self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)


    def test_import_preview_mapping_uses_contract_start_and_end_not_contract_date(self):
        boundary = '----PropertyImportContractDatesBoundary'
        csv_data = (
            '类别,房号,业主姓名,面积㎡,合同开始日期,合同到期日期\n'
            '商户,B座950,独立日期业主,60,2026-01-15,2026-12-31\n'
        )
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="contract-dates.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        preview_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('数据核对与修正', preview_html)
        self.assertIn('name="col_contract_start"', preview_html)
        self.assertIn('name="col_contract_end"', preview_html)
        self.assertNotIn('name="col_contract_period"', preview_html)
        self.assertNotIn('>合同日期</label>', preview_html)


    def test_billing_calc_redirected_range_period_is_visible_in_bill_list(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('区间账期业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('RANGEBILL', 'A座', '1808', 18, '居民', 10, owner_id)
        ).lastrowid
        db.commit(); db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2032-01-01',
            'period_end': '2032-03-01',
            'fee_types': '1',
            'custom_amount_1': '88.00',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills?period=2032-01~2032-03', urllib.parse.unquote(loc))

        status, list_html = http_get('/bills?period=2032-01~2032-03&keyword=1808', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('RANGEBILL-A座-1808', list_html)
        self.assertIn('2032-01~2032-03', list_html)
        self.assertNotIn('暂无账单', list_html)


    def test_invoice_requests_backend_page_updates_status(self):
        import server.db as db_module
        from server.invoice_requests import InvoiceRequestService
        db = db_module.get_db()
        owner_id = create_owner(db, '后台票据业主', '13800139002')
        room_id = create_room(db, building='INVADMIN', room_number='3902', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, owner_id=owner_id, amount=99.0, status='paid', period='2030-01')
        db.close()
        request = InvoiceRequestService().create_request({'bill_id': bill_id, 'buyer_name': '后台票据抬头'})
        try:
            status, page = http_get('/invoice_requests', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn('电子票据请求', page)
            self.assertIn(request['request_no'], page)

            status, _, loc = http_post(f'/invoice_requests/{request["request_no"]}/status', {
                'status': 'issued',
                'external_invoice_id': 'EINV-001',
            }, self.cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('/invoice_requests', loc)

            db = db_module.get_db()
            row = db.execute('SELECT status, external_invoice_id FROM invoice_requests WHERE request_no=?', (request['request_no'],)).fetchone()
            db.close()
            self.assertEqual(row['status'], 'issued')
            self.assertEqual(row['external_invoice_id'], 'EINV-001')
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM invoice_requests WHERE bill_id=?', (bill_id,))
            db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()

