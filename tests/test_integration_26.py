#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 26."""

from tests.integration_base import *
import sqlite3
from html.parser import HTMLParser


class _BillRowParser(HTMLParser):
    def __init__(self, marker):
        super().__init__()
        self.marker = marker
        self.rows = []
        self._in_tr = False
        self._in_td = False
        self._cells = []

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self._in_tr = True
            self._cells = []
        elif self._in_tr and tag == 'td':
            self._in_td = True
            self._cells.append('')

    def handle_endtag(self, tag):
        if tag == 'td':
            self._in_td = False
        elif tag == 'tr' and self._in_tr:
            row = [' '.join(cell.split()) for cell in self._cells]
            if any(self.marker in cell for cell in row):
                self.rows.append(row)
            self._in_tr = False
            self._cells = []

    def handle_data(self, data):
        if self._in_td and self._cells:
            self._cells[-1] += data


def _bill_row_cells(html, marker):
    parser = _BillRowParser(marker)
    parser.feed(html)
    return parser.rows[0] if parser.rows else []


class TestIntegration26(IntegrationTestBase):

    def test_payment_forms_default_operator_to_current_user_display_name(self):
        operator_cookie = self._create_user_and_login('receipt_operator_default', 'pass123', 'operator', display_name='当前收费员')
        http_post('/rooms/create', {
            'building': 'PAYDEFAULTOP', 'unit': 'A座', 'room_number': '921',
            'floor': '9', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-12', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYDEFAULTOP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-12' AND bill_number LIKE 'PAYDEFAULTOP%' ORDER BY id DESC LIMIT 1").fetchone()['id'])
        db.close()

        status, pay_page = http_get(f'/bills/{bid}/pay', operator_cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="operator" class="form-control" value="当前收费员"', pay_page)

        status, confirm_html, _ = http_post('/bills/batch_pay', {
            'bill_ids': bid,
            'payment_method': 'wechat',
        }, operator_cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="当前收费员"', confirm_html)
        self.assertNotIn('value="批量缴费"', confirm_html)

    def test_batch_pay_confirm_creates_auto_backup_before_writing(self):
        for room_no in ('909', '910'):
            http_post('/rooms/create', {
                'building': 'PAYBACKUP', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-06', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-06' ORDER BY id").fetchall()]
        db.close()
        before = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_batch_payment_')] if os.path.exists(db_module.BACKUP_DIR) else []

        status, html, loc = http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动备份', html)
        after = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_batch_payment_')]
        self.assertGreater(len(after), len(before))


    def test_batch_pay_confirm_records_payments_and_result_details(self):
        for room_no in ('903', '904'):
            http_post('/rooms/create', {
                'building': 'PAYCONFIRM', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-02', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYCONFIRM',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-02' ORDER BY id").fetchall()]
        db.close()

        status, html, loc = http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '批量收费测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量收费结果', html)
        self.assertIn('成功收费', html)
        self.assertIn('38.0', html)
        self.assertIn('/bills/receipt_by_ids', html)

        db = db_module.get_db()
        statuses = [r['status'] for r in db.execute("SELECT status FROM bills WHERE id IN (?, ?) ORDER BY id", ids).fetchall()]
        operators = [r['operator'] for r in db.execute("SELECT operator FROM payments WHERE bill_id IN (?, ?) ORDER BY bill_id", ids).fetchall()]
        db.close()
        self.assertEqual(statuses, ['paid', 'paid'])
        self.assertEqual(operators, ['批量收费测试员', '批量收费测试员'])


    def test_receipt_by_ids_accepts_comma_separated_bill_ids(self):
        for room_no in ('905', '906'):
            http_post('/rooms/create', {
                'building': 'PAYRECEIPT', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-03', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYRECEIPT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-03' ORDER BY id").fetchall()]
        db.close()

        http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '收据测试员',
        }, self.cookie, TEST_PORT)
        status, confirm_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': ','.join(ids),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收据信息确认', confirm_html)
        self.assertIn('PAYRECEIPT', confirm_html)
        self.assertIn('38.0', confirm_html)

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'confirm_receipt': '1',
            'bill_ids': ','.join(ids),
            'operator': '收据测试员',
            'payment_method': 'wechat',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('PAYRECEIPT', receipt_html)
        self.assertIn('38.0', receipt_html)



    def test_receipt_confirmation_precedes_new_receipt_template_and_keeps_temp_fields(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '新版收据业主', '13900002601')
        room_id = create_room(db, building='NEWRECEIPT', unit='B座', room_number='1422', floor=14, category='居民', area=59.42, owner_id=owner_id)
        property_fee = db.execute("""
            INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active)
            VALUES('新版物业费','area',2.4,'元/m²·月','monthly',31,1)
        """).lastrowid
        energy_fee = db.execute("""
            INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active)
            VALUES('新版公摊能耗费','household',10,'元/户·月','monthly',32,1)
        """).lastrowid
        property_bill = db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, property_fee, '2026-07~2026-09', 427.82, '2026-09-30', 'partial', 'NEW-RC-PROP', '2026-07-01', '2026-09-30')).lastrowid
        energy_bill = db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, energy_fee, '2026-07~2026-09', 30, '2026-09-30', 'unpaid', 'NEW-RC-ENERGY', '2026-07-01', '2026-09-30')).lastrowid
        db.execute("INSERT INTO payments(bill_id,amount_paid,payment_method,operator,receipt_number) VALUES(?,?,?,?,?)", (property_bill, 100, 'wechat', '新版收费员', 'JS20260624170448'))
        db.execute("INSERT INTO bill_adjustments(bill_id,old_amount,new_amount,reason,approved_by) VALUES(?,?,?,?,?)", (property_bill, 500, 427.82, '优惠减免测试', '主管'))
        db.commit(); db.close()

        status, confirm_html, _ = http_post('/bills/receipt_by_ids', {
            'bill_ids': f'{property_bill},{energy_bill}',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收据信息确认', confirm_html)
        self.assertIn('name="summary"', confirm_html)
        self.assertIn('name="voucher_no"', confirm_html)
        self.assertIn('NEWRECEIPT\\B座\\1422', confirm_html)
        self.assertNotIn('<th style="width:16%">房间</th>', confirm_html)

        status, receipt_html, _ = http_post('/bills/receipt_by_ids', {
            'confirm_receipt': '1',
            'bill_ids': f'{property_bill},{energy_bill}',
            'summary': '临时摘要',
            'notes': '临时备注',
            'voucher_no': 'PZ-001',
            'payer_signature': '郝立科',
            'payment_method': '二维码',
            'operator': '周丹',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('套户编号：', receipt_html)
        self.assertIn('NEWRECEIPT\\B座\\1422', receipt_html)
        self.assertIn('客户名称：', receipt_html)
        self.assertIn('建筑面积：', receipt_html)
        self.assertIn('59.42m2', receipt_html)
        self.assertIn('流水号：', receipt_html)
        self.assertIn('JS20260624170448', receipt_html)
        self.assertIn('凭证号：', receipt_html)
        self.assertIn('PZ-001', receipt_html)
        self.assertIn('缴费时间：', receipt_html)
        self.assertIn('<th style="width:18%">收费项目</th>', receipt_html)
        self.assertNotIn('<th style="width:16%">房间</th>', receipt_html)
        self.assertIn('优惠', receipt_html)
        self.assertIn('减免', receipt_html)
        self.assertIn('59.42×3', receipt_html)
        self.assertIn('1×3', receipt_html)
        self.assertIn('72.2', receipt_html)
        self.assertIn('临时摘要', receipt_html)
        self.assertIn('临时备注', receipt_html)
        self.assertIn('收费员：', receipt_html)
        self.assertIn('周丹', receipt_html)
        self.assertIn('支付方式：', receipt_html)
        self.assertIn('二维码', receipt_html)
        self.assertIn('交款人签字：', receipt_html)
        self.assertIn('郝立科', receipt_html)
        self.assertIn('打印日期：', receipt_html)

    def test_single_payment_creates_auto_backup_before_writing(self):
        http_post('/rooms/create', {
            'building': 'PAYSINGLEBACKUP', 'unit': 'A座', 'room_number': '901',
            'floor': '9', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-07', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYSINGLEBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-07' LIMIT 1").fetchone()['id'])
        db.close()
        before = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_payment_')] if os.path.exists(db_module.BACKUP_DIR) else []

        status, body, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': '19.0',
            'payment_method': 'cash',
            'operator': '单笔备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款成功', body)
        after = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_payment_')]
        self.assertGreater(len(after), len(before))


    def test_bill_payment_page_opens_from_bill_detail(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('支付页业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('PAYPAGE', 'A座', '901', 9, '居民', 10, owner_id),
        ).lastrowid
        bid = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 1, '2028-08', 19, '2028-08-28', 'unpaid', 'PAYPAGE-001'),
        ).lastrowid
        db.commit()
        db.close()

        status, detail = http_get(f'/bills/{bid}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'/bills/{bid}/pay', detail)

        status, pay_page = http_get(f'/bills/{bid}/pay', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('录入缴费', pay_page)
        self.assertIn(f'action="/bills/{bid}/pay"', pay_page)
        self.assertIn('确认缴费', pay_page)


    def test_generated_bill_does_not_inherit_stale_payment_from_reused_id(self):
        import server.db as db_module

        db = db_module.get_db()
        try:
            owner_id = db.execute("INSERT INTO owners(name) VALUES('复用账单业主')").lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
                ('PAYREUSE', 'A座', '901', 9, '居民', 10, owner_id),
            ).lastrowid
            reused_bid = 900002
            db.execute("DELETE FROM payments")
            db.execute("DELETE FROM bills")
            db.execute("DELETE FROM sqlite_sequence WHERE name='bills'")
            db.execute("INSERT INTO sqlite_sequence(name, seq) VALUES('bills', ?)", (reused_bid - 1,))
            db.commit()
        finally:
            db.close()

        raw = sqlite3.connect(db_module.DB_PATH)
        try:
            raw.execute("PRAGMA foreign_keys=OFF")
            raw.execute(
                "INSERT INTO payments(bill_id,amount_paid,payment_date,payment_method,operator,created_at) VALUES(?,?,?,?,?,?)",
                (reused_bid, 19, '2027-01-02', 'cash', '旧收款', '2027-01-02 00:00:00'),
            )
            raw.commit()
        finally:
            raw.close()

        http_post('/bills/generate', {
            'mode': 'confirm', 'period_start': '2028-09-01', 'period_end': '2028-09-30',
            'fee_type_ids': '1', 'building': 'PAYREUSE',
        }, self.cookie, TEST_PORT)

        db = db_module.get_db()
        bill = db.execute("SELECT id,status FROM bills WHERE billing_period='2028-09' AND room_id=?", (room_id,)).fetchone()
        paid = db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=?", (bill['id'],)).fetchone()[0]
        db.close()

        self.assertEqual(bill['id'], reused_bid)
        self.assertEqual(float(paid or 0), 0)
        self.assertEqual(bill['status'], 'unpaid')
        status, detail = http_get(f'/bills/{bill["id"]}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('已缴</small><h5 class="money money-paid">¥0.0</h5>', detail)
        self.assertIn('欠费</small><h5 class="money money-due">¥19.0</h5>', detail)
        self.assertIn(f'/bills/{bill["id"]}/pay', detail)

        status, bill_list = http_get('/bills?building=PAYREUSE&keyword=901', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('未缴', bill_list)
        cells = _bill_row_cells(bill_list, 'PAYREUSE-901')
        self.assertGreaterEqual(len(cells), 10)
        self.assertIn('物业公司收费', cells[2])
        self.assertIn('PAYREUSE', cells[3])
        self.assertIn('901', cells[3])
        self.assertIn('2028-09', cells[5])
        self.assertEqual(cells[6], '¥19.0')
        self.assertEqual(cells[7], '¥0.0')
        self.assertEqual(cells[8], '¥19.0')
        self.assertIn('未缴', cells[9])
        db = db_module.get_db()
        payment_count = db.execute("SELECT COUNT(*) FROM payments WHERE bill_id=?", (bill['id'],)).fetchone()[0]
        db.close()
        self.assertEqual(payment_count, 0)


    def test_single_payment_rejects_amount_greater_than_remaining(self):
        http_post('/rooms/create', {
            'building': 'PAYLIMIT', 'unit': 'A座', 'room_number': '901',
            'floor': '9', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-04', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYLIMIT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-04' LIMIT 1").fetchone()['id'])
        db.close()

        status, body, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': '20.0',
            'payment_method': 'cash',
            'operator': '超额测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('不能超过待缴金额', urllib.parse.unquote(loc))

        db = db_module.get_db()
        payment_count = db.execute("SELECT COUNT(*) FROM payments WHERE bill_id=?", (bid,)).fetchone()[0]
        status_value = db.execute("SELECT status FROM bills WHERE id=?", (bid,)).fetchone()['status']
        db.close()
        self.assertEqual(payment_count, 0)
        self.assertEqual(status_value, 'unpaid')


    def test_single_payment_result_page_blocks_repeat_payment_and_links_receipt(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('单笔结果业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('PAYDONE', 'A座', '902', 9, '居民', 10, owner_id),
        ).lastrowid
        bid = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 1, '2028-10', 19, '2028-10-28', 'unpaid', 'PAYDONE-902-01'),
        ).lastrowid
        db.commit()
        db.close()

        status, html, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': '19.0',
            'payment_method': 'cash',
            'operator': '单笔结果测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款成功', html)
        self.assertIn('本次收款', html)
        self.assertIn('历史已收', html)
        self.assertIn('当前欠费', html)
        self.assertIn('/bills/receipt_by_ids', html)

        status, paid_page = http_get(f'/bills/{bid}/pay', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('该账单已结清', paid_page)
        self.assertNotIn('确认缴费', paid_page)

        status, html, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': '1.0',
            'payment_method': 'cash',
            'operator': '重复测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('账单已结清，不能重复收费', urllib.parse.unquote(loc))


    def test_bills_list_shows_group_reconciliation_hints(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('核对提示业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('PAYHINT', 'A座', '903', 9, '居民', 10, owner_id),
        ).lastrowid
        db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 1, '2028-11', 19, '2028-11-28', 'unpaid', 'PAYHINT-903-01'),
        )
        partial_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 2, '2028-11', 30, '2028-11-28', 'partial', 'PAYHINT-903-02'),
        ).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 10, 'cash', '核对提示测试员')", (partial_id,))
        db.commit()
        db.close()

        status, html = http_get('/bills?building=PAYHINT&period=2028-11', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('核对：2项', html)
        self.assertIn('未缴1', html)
        self.assertIn('部分1', html)
        self.assertIn('欠费¥39.0', html)


    def test_receipt_by_ids_shows_each_room_and_payment_operator(self):
        for room_no in ('907', '908'):
            http_post('/rooms/create', {
                'building': 'PAYRECEIPTROOM', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-05', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYRECEIPTROOM',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-05' ORDER BY id").fetchall()]
        db.close()

        http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '收据核对员',
        }, self.cookie, TEST_PORT)
        status, confirm_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': ','.join(ids),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收据信息确认', confirm_html)
        self.assertIn('收据核对员', confirm_html)
        self.assertIn('wechat', confirm_html)
        self.assertIn('PAYRECEIPTROOM\\A座\\907', confirm_html)
        self.assertIn('PAYRECEIPTROOM\\A座\\908', confirm_html)

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'confirm_receipt': '1',
            'bill_ids': ','.join(ids),
            'operator': '收据核对员',
            'payment_method': 'wechat',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收费员', receipt_html)
        self.assertIn('收据核对员', receipt_html)
        self.assertIn('支付方式', receipt_html)
        self.assertIn('wechat', receipt_html)
        self.assertIn('PAYRECEIPTROOM\\A座\\907', receipt_html)
        self.assertIn('PAYRECEIPTROOM\\A座\\908', receipt_html)


    def test_bill_payment_workflow(self):
        """Pay a bill, verify status changes to paid."""
        self._ensure_room_for_billing()
        http_post('/bills/generate', {
            'period': '2026-06', 'fee_type_ids': '1', 'due_day': '28',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bill = db.execute("SELECT id,amount FROM bills WHERE billing_period='2026-06' ORDER BY id DESC LIMIT 1").fetchone()
        bid = bill['id']
        amount = bill['amount']
        db.close()

        # Get bill amount
        _, detail = http_get(f'/bills/{bid}', self.cookie, TEST_PORT)
        self.assertIn('账单信息', detail)

        # Pay the bill
        status, body, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': str(amount), 'payment_method': 'wechat', 'operator': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款成功', body)

        # Verify status
        _, detail2 = http_get(f'/bills/{bid}', self.cookie, TEST_PORT)
        self.assertIn('已缴', detail2)


    def test_api_stats(self):
        status, body = http_get('/api/stats', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn('total_rooms', data)


    def test_api_owner_info(self):
        http_post('/owners/create', {'name': '李四', 'phone': '13900002222'},
                  self.cookie, TEST_PORT)
        import server.db as db_module
        db = db_module.get_db()
        owner = db.execute("SELECT id FROM owners WHERE phone=? ORDER BY id DESC LIMIT 1", ('13900002222',)).fetchone()
        db.close()
        status, body = http_get(f'/api/owners/{owner["id"]}/info', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data.get('name'), '李四')

    def test_payment_service_rechecks_unpaid_amount_inside_write_transaction(self):
        import server.db as db_module
        from server.services import Actor, PaymentService, ServiceError

        db = db_module.get_db()
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('PAYSTALE001', 100.0)
        db.close()
        try:
            db = db_module.get_db()
            db.execute(
                "INSERT INTO payments (bill_id, amount_paid, payment_date, payment_method, operator) "
                "VALUES (?, ?, datetime('now','localtime'), ?, ?)",
                (bill_id, 80.0, 'cash', '先收款'),
            )
            db.commit()
            db.close()

            service = PaymentService()
            service.preview_payment = lambda request: {
                'bill_id': bill_id,
                'amount': '30.0',
                'unpaid_before': '100.0',
                'unpaid_after': '70.0',
                'will_mark_paid': False,
            }

            with self.assertRaises(ServiceError) as ctx:
                service.create_payment(
                    {'bill_id': bill_id, 'amount': '30.0', 'method': 'cash'},
                    Actor(username='并发测试员', role='cashier'),
                )
            self.assertIn('收款金额不能超过欠费金额', str(ctx.exception))

            db = db_module.get_db()
            total_paid = db.execute(
                'SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=?',
                (bill_id,),
            ).fetchone()[0]
            db.close()
            self.assertEqual(total_paid, 80.0)
        finally:
            self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)
