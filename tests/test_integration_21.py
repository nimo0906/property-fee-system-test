#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 21."""

from tests.integration_base import *


class TestIntegration21(IntegrationTestBase):
    def test_closing_page_has_non_writing_preview_button(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '结账预览业主', '13900004444')
        room_id = create_room(db, building='CLOSEPRE', unit='A座', room_number='601', owner_id=owner_id)
        create_bill(db, room_id=room_id, fee_type_id=1, period='2034-05', amount=99, status='unpaid', owner_id=owner_id)
        db.close()

        status, page = http_get('/closing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('提前预览', page)
        self.assertIn('name="preview" value="1"', page)
        self.assertIn('name="period_start"', page)
        self.assertIn('name="period_end"', page)

        status, preview, loc = http_post('/closing/close', {'period': '2034-05', 'preview': '1'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('结账前预览', preview)
        self.assertIn('本次将结账的账单', preview)
        self.assertIn('CLOSEPRE-A座-601', preview)
        self.assertIn('99.0', preview)
        self.assertIn('未缴', preview)
        self.assertIn('确认结账', preview)
        db = db_module.get_db()
        closed = db.execute("SELECT COUNT(*) FROM closing_records WHERE period='2034-05'").fetchone()[0]
        db.close()
        self.assertEqual(closed, 0)


    def test_closing_uses_finance_natural_date_range_for_preview_and_confirm(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '结账自然日期业主', '13900004445')
        room_id = create_room(db, building='CLOSEDATERN', unit='商场', room_number='2F-601', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-11~2035-01', amount=399, status='paid', owner_id=owner_id)
        outside_bill = create_bill(db, room_id=room_id, fee_type_id=1, period='2035-02', amount=288, status='paid', owner_id=owner_id)
        db.execute("UPDATE bills SET service_start=?, service_end=? WHERE id=?", ('2034-11-15', '2035-01-14', bill_id))
        db.execute("UPDATE bills SET service_start=?, service_end=? WHERE id=?", ('2035-02-01', '2035-02-28', outside_bill))
        db.close()

        status, preview, loc = http_post('/closing/close', {
            'period_start': '2034-12-01',
            'period_end': '2034-12-31',
            'preview': '1',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('2034-12-01 至 2034-12-31', preview)
        self.assertIn('CLOSEDATERN-商场-2F-601', preview)
        self.assertIn('399.0', preview)
        self.assertNotIn('288.0', preview)
        self.assertIn('name="period_start" value="2034-12-01"', preview)
        self.assertIn('name="period_end" value="2034-12-31"', preview)

        status, body, loc = http_post('/closing/close', {
            'period_start': '2034-12-01',
            'period_end': '2034-12-31',
            'confirm': '1',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('2034-12', urllib.parse.unquote(loc))
        db = db_module.get_db()
        row = db.execute("SELECT status, paid_count, total_amount FROM closing_records WHERE period='2034-12'").fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['status'], 'closed')
        self.assertEqual(row['paid_count'], 1)
        self.assertEqual(row['total_amount'], 399)


    def test_owner_portal_routes_are_removed(self):
        for path in ['/owner-portal', '/owner-portal/login', '/owner-portal/bills', '/owner-portal/payment-orders']:
            status, body = http_get(path, '', TEST_PORT)
            self.assertEqual(status, 404, path)
            self.assertIn('页面未找到', body)
            self.assertNotIn('业主端已停用', body)

        for path in ['/api/v1/owner-portal/send-code', '/api/v1/owner-portal/login']:
            status, body, loc = http_post(path, {'phone': '13800138000', 'code': '123456'}, '', TEST_PORT)
            self.assertEqual(status, 404, path)
            payload = json.loads(body)
            self.assertFalse(payload['ok'])
            self.assertEqual(payload['error']['code'], 'not_found')


    def test_payment_orders_module_is_removed_from_backend(self):
        status, body = http_get('/payment_orders', self.cookie, TEST_PORT)
        self.assertEqual(status, 404)
        self.assertIn('页面未找到', body)

        status, body = http_get('/', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('href="/payment_orders"', body)
        self.assertNotIn('支付订单', body)


    def test_billing_period_filter_helper_uses_start_month_for_range_periods(self):
        from server.billing_periods import period_filter_clause
        clause, params = period_filter_clause('2026-06-01', 'b.billing_period')
        self.assertIn('substr', clause)
        self.assertEqual(params, ['2026-06', '2026-06', '2026-06'])


    def test_fee_scope_helper_centralizes_property_and_commercial_fee_groups(self):
        from server.billing_rules import fee_in_scope
        self.assertTrue(fee_in_scope({'name': '物业费(商户)', 'sort_order': 10}, 'property'))
        self.assertFalse(fee_in_scope({'name': '物业费(商户)', 'sort_order': 10}, 'commercial'))
        self.assertTrue(fee_in_scope({'name': '物业费(商业)', 'sort_order': 31}, 'commercial'))
        self.assertFalse(fee_in_scope({'name': '泄水费', 'sort_order': 17}, 'property'))
        self.assertTrue(fee_in_scope({'name': '泄水费', 'sort_order': 17}, 'commercial'))
        self.assertTrue(fee_in_scope({'name': '水费(非居民)', 'sort_order': 5}, 'commercial'))


    def test_commercial_billing_hides_property_company_merchant_fee(self):
        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('data-name="物业费(商户)"', body)
        self.assertIn('物业费(商业)', body)


    def test_billing_calc_get_redirects_back_to_billing_page(self):
        status, body = http_get('/billing/calc', self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        # Browser refresh/back after submit must not leave user on an invalid POST-only URL.
        import http.client
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/billing/calc', headers={'Cookie': self.cookie})
        resp = conn.getresponse()
        resp.read()
        loc = resp.getheader('Location', '')
        conn.close()
        self.assertTrue(loc.startswith('/billing?flash='), loc)


    def test_billing_calc_generates_only_selected_fee_types(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('选择收费业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('SELECTFEE', 'A座', '901', 9, '居民', 10, owner_id)
        ).lastrowid
        db.commit()
        db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2031-01-01',
            'period_end': '2031-02-01',
            'fee_types': '1',
            'custom_amount_1': '19.00',
            'custom_amount_3': '99.0',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = db_module.get_db()
        rows = db.execute(
            "SELECT fee_type_id,amount FROM bills WHERE room_id=? AND billing_period='2031-01~2031-02' ORDER BY fee_type_id",
            (room_id,)
        ).fetchall()
        db.close()
        self.assertEqual([r['fee_type_id'] for r in rows], [1])
        self.assertEqual(rows[0]['amount'], 19)


    def test_billing_calc_existing_bill_redirects_to_room_all_statuses(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('重复收费业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('EXISTBILL', 'A座', '1705', 17, '商户', 85.4, owner_id)
        ).lastrowid
        db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 2, '2031-11~2031-12', 854, '2031-12-01', 'paid', 'EXIST-1705-001')
        )
        db.commit()
        db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2031-11-01',
            'period_end': '2031-12-01',
            'fee_types': '2',
            'custom_amount_2': '854.00',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        decoded = urllib.parse.unquote(loc)
        self.assertIn('/bills?period=2031-11~2031-12', decoded)
        self.assertNotIn('keyword=', decoded)
        self.assertIn('已存在账单，未重复生成', decoded)


    def test_bill_generate_form_uses_natural_date_range_fields(self):
        status, body = http_get('/bills/generate', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="period_start"', body)
        self.assertIn('name="period_end"', body)
        self.assertIn('按财务自然日期范围生成账单', body)
        self.assertNotIn('账期 *', body)


    def test_bill_generate_natural_date_range_sets_service_dates(self):
        http_post('/rooms/create', {
            'building': 'RANGEGEN', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period_start': '2032-01-01',
            'period_end': '2032-03-31',
            'fee_type_ids': '1',
            'building': 'RANGEGEN',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('生成账单预览', html)
        self.assertIn('2032-01-01 至 2032-03-31', html)

        import server.db as db_module
        db = db_module.get_db()
        before = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2032-01~2032-03'").fetchone()[0]
        db.close()
        self.assertEqual(before, 0)

        status, body, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period_start': '2032-01-01',
            'period_end': '2032-03-31',
            'fee_type_ids': '1',
            'building': 'RANGEGEN',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)
        self.assertIn('/bills?period_start=2032-01-01&amp;period_end=2032-03-31', body)
        db = db_module.get_db()
        bill = db.execute("""SELECT billing_period,service_start,service_end,due_date,amount
            FROM bills b JOIN rooms r ON b.room_id=r.id
            WHERE r.building='RANGEGEN' AND b.fee_type_id=1""").fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2032-01~2032-03')
        self.assertEqual(bill['service_start'], '2032-01-01')
        self.assertEqual(bill['service_end'], '2032-03-31')
        self.assertEqual(bill['due_date'], '2032-03-31')
        self.assertGreater(bill['amount'], 0)
