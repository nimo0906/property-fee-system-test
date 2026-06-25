#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 25."""

from tests.integration_base import *


class TestIntegration25(IntegrationTestBase):
    def test_bill_batch_edit_without_selection_preserves_current_bill_filters(self):
        http_post('/rooms/create', {
            'building': 'BATCHBACK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-07', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BATCHBACK',
        }, self.cookie, TEST_PORT)

        status, _, loc = http_post('/bills/batch_edit', {
            'back': '/bills?period=2029-07&building=BATCHBACK',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills?period=2029-07&building=BATCHBACK', loc)
        self.assertIn('flash=', loc)


    def test_bill_list_can_select_owner_and_room_bill_groups(self):
        http_post('/rooms/create', {
            'building': 'SELECTGROUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-08', 'fee_type_ids': '1,3',
            'due_day': '28', 'building': 'SELECTGROUP',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills?period=2029-08&building=SELECTGROUP', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('class="owner-group-chk"', html)
        self.assertIn('class="room-group-chk"', html)
        self.assertIn('data-owner-group="o1"', html)
        self.assertIn('data-room-group="o1r', html)
        self.assertIn('toggleBillGroup', html)
        self.assertIn(".bill-chk[data-owner-group=", html)
        self.assertIn(".bill-chk[data-room-group=", html)
        self.assertIn('function appendCsrfToken', html)
        self.assertIn('meta[name="csrf-token"]', html)
        self.assertIn("input.name = '_csrf_token'", html)


    def test_bill_list_room_summary_rows_expand_their_bill_details(self):
        http_post('/rooms/create', {
            'building': 'ROOMFOLD', 'unit': 'B座', 'room_number': '1401',
            'floor': '14', 'category': '商户', 'area': '10', 'tenant_name': '房间折叠租户',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-11', 'fee_type_ids': '1,3',
            'due_day': '28', 'building': 'ROOMFOLD',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills?period=2029-11&building=ROOMFOLD', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn("onclick=\"toggleBillRoom('o1r1')\"", html)
        self.assertIn('id="icon_o1r1"', html)
        self.assertIn('class="bill-detail-o1r1"', html)
        self.assertIn('function toggleBillRoom(roomGroup)', html)
        self.assertIn('room-detail-o1 bill-room-row', html)


    def test_bill_list_groups_by_tenant_name_before_owner_name(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '账单分组业主', '13900008801')
        room_a = create_room(db, building='TENANTBILL', unit='B座', room_number='1401', category='商户', owner_id=owner_id)
        room_b = create_room(db, building='TENANTBILL', unit='B座', room_number='1402', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name=? WHERE id=?", ('租户甲', room_a))
        db.execute("UPDATE rooms SET tenant_name=? WHERE id=?", ('租户乙', room_b))
        create_bill(db, room_id=room_a, owner_id=owner_id, fee_type_id=1, period='2037-01', amount=100, status='unpaid')
        create_bill(db, room_id=room_b, owner_id=owner_id, fee_type_id=1, period='2037-01', amount=200, status='unpaid')
        db.close()

        status, html = http_get('/bills?period=2037-01&building=TENANTBILL', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<strong>租户甲</strong>', html)
        self.assertIn('<strong>租户乙</strong>', html)
        self.assertNotIn('<strong>账单分组业主</strong>', html)


    def test_bill_list_delete_buttons_are_not_nested_in_batch_form(self):
        http_post('/rooms/create', {
            'building': 'DELETEONE', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-10', 'fee_type_ids': '1,3',
            'due_day': '28', 'building': 'DELETEONE',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills?period=2029-10&building=DELETEONE&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<form method=POST id="billActionForm">', html)
        self.assertIn('name="_csrf_token"', html)
        self.assertIn('name="back" value="/bills?period=2029-10&amp;building=DELETEONE&amp;status=unpaid"', html)
        self.assertIn('class=bill-chk form="billActionForm"', html)
        self.assertIn('form="billActionForm" formaction=', html)
        self.assertIn('/delete" style=display:inline', html)
        self.assertIn('name="back" value="/bills?period=2029-10&amp;building=DELETEONE&amp;status=unpaid"', html)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute(
            "SELECT id FROM bills WHERE billing_period='2029-10' AND room_id=(SELECT id FROM rooms WHERE building='DELETEONE' LIMIT 1) ORDER BY id"
        ).fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        status, body, loc = http_post(f'/bills/{ids[0]}/delete', {
            'back': '/bills?period=2029-10&building=DELETEONE&status=unpaid'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('period=2029-10', loc)
        self.assertIn('building=DELETEONE', loc)

        db = db_module.get_db()
        remaining = [str(r['id']) for r in db.execute(
            "SELECT id FROM bills WHERE billing_period='2029-10' AND room_id=(SELECT id FROM rooms WHERE building='DELETEONE' LIMIT 1) ORDER BY id"
        ).fetchall()]
        db.close()
        self.assertEqual(remaining, [ids[1]])


    def test_print_selected_bills_combines_multiple_items_on_one_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '合并打印业主', '13911112222')
        room_id = create_room(db, building='PRINTMERGE', unit='商场', room_number='1F-201', category='商户', area=50, owner_id=owner_id)
        bill_a = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2031-01', amount=100, status='unpaid')
        bill_b = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=2, period='2031-01', amount=200, status='unpaid')
        db.close()

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode([
            ('bill_ids', str(bill_a)),
            ('bill_ids', str(bill_b)),
            ('back', '/bills?period=2031-01&building=PRINTMERGE'),
        ])
        conn.request('POST', '/bills/print_selected', params, {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': self.cookie,
            'X-CSRF-Token': csrf_header_for_cookie(self.cookie),
        })
        resp = conn.getresponse()
        print_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('账单打印', print_html)
        self.assertIn('打印类型：账单打印', print_html)
        self.assertIn('缴费合计', print_html)
        self.assertIn('300.0', print_html)
        self.assertIn('物业费(居民)', print_html)
        self.assertIn('物业费(商户)', print_html)
        self.assertEqual(print_html.count('陕西金莎国际物业管理有限公司'), 1)
        self.assertNotIn('<div class="page-break"', print_html)



    def test_print_selected_uses_new_template_but_distinguishes_bill_print(self):
        http_post('/rooms/create', {
            'building': 'PRINTNEWTPL', 'unit': 'B座', 'room_number': '1501',
            'floor': '15', 'category': '居民', 'area': '59.42',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2030-01', 'fee_type_ids': '1',
            'due_day': '31', 'building': 'PRINTNEWTPL',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2030-01' AND bill_number LIKE 'PRINTNEWTPL%' ORDER BY id DESC LIMIT 1").fetchone()['id'])
        db.close()

        status, print_html, _ = http_post('/bills/print_selected', {
            'bill_ids': bid,
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('账单打印', print_html)
        self.assertIn('打印类型：账单打印', print_html)
        self.assertIn('套户编号：', print_html)
        self.assertIn('PRINTNEWTPL\\B座\\1501', print_html)
        self.assertIn('<th style="width:18%">收费项目</th>', print_html)
        self.assertNotIn('<th>房间</th>', print_html)
        self.assertIn('费用区间', print_html)
        self.assertIn('使用量', print_html)
        self.assertIn('优惠', print_html)
        self.assertIn('减免', print_html)
        self.assertIn('缴费', print_html)
        self.assertIn('欠费', print_html)
        self.assertNotIn('收据信息确认', print_html)

    def test_print_selected_and_single_bill_show_exact_service_dates(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '打印日期区间业主', '13911113333')
        room_id = create_room(db, building='PRINTDATE', unit='B座', room_number='1001', category='商户', area=50, owner_id=owner_id)
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        bill_id = db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (room_id, owner_id, fee_id, '2026-07~2026-09', 825, '2026-09-30', 'unpaid', 'PRINT-DATE-001', '2026-07-01', '2026-09-30')
        ).lastrowid
        db.commit(); db.close()

        status, print_html, _ = http_post('/bills/print_selected', {
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-07-01 至 2026-09-30', print_html)
        self.assertNotIn('2026-07~2026-09</td>', print_html)

        status, single_html = http_get(f'/bills/{bill_id}/print', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-07-01 至 2026-09-30', single_html)
        self.assertNotIn('2026-07~2026-09</td>', single_html)


    def test_bill_list_print_and_receipt_preserve_current_back_url(self):
        http_post('/rooms/create', {
            'building': 'PRINTBACK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-11', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PRINTBACK',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute(
            "SELECT id FROM bills WHERE billing_period='2029-11' AND room_id=(SELECT id FROM rooms WHERE building='PRINTBACK' LIMIT 1)"
        ).fetchone()['id'])
        db.close()

        status, list_html = http_get('/bills?period=2029-11&building=PRINTBACK&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="back" value="/bills?period=2029-11&amp;building=PRINTBACK&amp;status=unpaid"', list_html)
        self.assertIn("submitBillAction('/bills/print_selected','_blank')", list_html)
        self.assertIn("submitBillAction('/bills/receipt_by_ids','_blank')", list_html)
        self.assertIn('function submitBillAction(action, target)', list_html)
        self.assertIn("alert('请先勾选账单')", list_html)
        self.assertNotIn("this.form.action='/bills/receipt_by_ids'", list_html)

        status, print_html, loc = http_post('/bills/print_selected', {
            'bill_ids': bid,
            'back': '/bills?period=2029-11&building=PRINTBACK&status=unpaid',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('href="/bills?period=2029-11&amp;building=PRINTBACK&amp;status=unpaid"', print_html)
        self.assertNotIn('href="/"', print_html)

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': bid,
            'back': '/bills?period=2029-11&building=PRINTBACK&status=unpaid',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('href="/bills?period=2029-11&amp;building=PRINTBACK&amp;status=unpaid"', receipt_html)
        self.assertIn('name="back" value="/bills?period=2029-11&amp;building=PRINTBACK&amp;status=unpaid"', receipt_html)


    def test_bill_detail_with_formula(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('账单详情业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('DETAILFORMULA', 'A座', '801', 8, '居民', 100, owner_id)
        ).lastrowid
        db.commit(); db.close()
        try:
            http_post('/bills/generate', {
                'period': '2026-06', 'fee_type_ids': '1', 'due_day': '28',
                'building': 'DETAILFORMULA',
            }, self.cookie, TEST_PORT)
            db = db_module.get_db()
            bill_id = db.execute("SELECT id FROM bills WHERE room_id=? AND billing_period='2026-06' ORDER BY id DESC LIMIT 1", (room_id,)).fetchone()['id']
            db.close()
            status, body = http_get(f'/bills/{bill_id}', self.cookie, TEST_PORT)
            self.assertEqual(status, 200, msg='Bill detail page not found')
            self.assertIn('账单信息', body)
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM payments WHERE bill_id IN (SELECT id FROM bills WHERE room_id=?)', (room_id,))
            db.execute('DELETE FROM bills WHERE room_id=?', (room_id,))
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()


    def test_batch_pay_preview_shows_selected_total_without_writing(self):
        for room_no in ('901', '902'):
            http_post('/rooms/create', {
                'building': 'PAYBATCH', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-01', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYBATCH',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-01' ORDER BY id").fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        status, html, loc = http_post('/bills/batch_pay', {
            'bill_ids': ','.join(ids),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量收费确认', html)
        self.assertIn('确认收款', html)
        self.assertIn('38.0', html)

        db = db_module.get_db()
        payment_count = db.execute("SELECT COUNT(*) FROM payments WHERE bill_id IN (?, ?)", ids).fetchone()[0]
        db.close()
        self.assertEqual(payment_count, 0)
