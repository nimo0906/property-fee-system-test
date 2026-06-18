#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 17."""

from tests.integration_base import *


class TestIntegration17(IntegrationTestBase):
    def test_core_charge_workflow_health_check(self):
        """体检第一阶段核心收费链路：收费项目→生成预览→确认→核对→收费→收据→报表→结账锁定。"""
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute(
            "INSERT INTO owners(name, phone) VALUES(?, ?)",
            ('主流程业主', '13812345678')
        ).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id) VALUES(?,?,?,?,?,?,?)",
            ('HEALTH', 'A座', '1201', 12, '商户', 50, owner_id)
        ).lastrowid
        fee_type_id = db.execute("""
            INSERT INTO fee_types(name, calc_method, unit_price, unit, sort_order, notes)
            VALUES(?, ?, ?, ?, ?, ?)
        """, ('体检自定义服务费', 'area', 0, '元/㎡', 20, '第一阶段收费体检')).lastrowid
        db.execute(
            "INSERT INTO fee_type_tiers(fee_type_id, category, rate, is_default) VALUES(?,?,?,?)",
            (fee_type_id, '商户', 2.5, 1)
        )
        db.commit(); db.close()

        status, preview_html, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period': '2032-01',
            'fee_type_ids': str(fee_type_id),
            'due_day': '28',
            'building': 'HEALTH',
            'category': '商户',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('生成账单预览', preview_html)
        self.assertIn('体检自定义服务费', preview_html)
        self.assertIn('50.0×2.5', preview_html)
        self.assertIn('125.00', preview_html)

        db = db_module.get_db()
        preview_count = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2032-01' AND room_id=?", (room_id,)).fetchone()[0]
        db.close()
        self.assertEqual(preview_count, 0)

        status, result_html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2032-01',
            'fee_type_ids': str(fee_type_id),
            'due_day': '28',
            'building': 'HEALTH',
            'category': '商户',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', result_html)
        self.assertIn('本次生成账单', result_html)
        self.assertIn('125.00', result_html)
        self.assertIn('异常核对清单', result_html)

        db = db_module.get_db()
        bill = db.execute("""
            SELECT id, amount, due_date, status FROM bills
            WHERE billing_period='2032-01' AND room_id=? AND fee_type_id=?
        """, (room_id, fee_type_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['amount'], 125)
        self.assertEqual(bill['due_date'], '2032-01-28')
        self.assertEqual(bill['status'], 'unpaid')

        status, list_html = http_get('/bills?period=2032-01&building=HEALTH', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('主流程业主', list_html)
        self.assertIn('体检自定义服务费', list_html)
        self.assertIn('125.00', list_html)

        status, review_html = http_get('/bills/review?period=2032-01&building=HEALTH&scope=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单核对工作台', review_html)
        self.assertIn('HEALTH-A座-1201', review_html)
        self.assertIn('125.00', review_html)

        status, pay_html = http_get(f'/bills/{bill["id"]}/pay', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('录入缴费', pay_html)
        self.assertIn('125.00', pay_html)

        status, body, loc = http_post(f'/bills/{bill["id"]}/pay', {
            'amount_paid': '125.00',
            'payment_method': 'wechat',
            'operator': '体检收费员',
            'notes': '核心收费体检',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款成功', body)
        self.assertIn('打印收据', body)

        db = db_module.get_db()
        paid = db.execute("SELECT status FROM bills WHERE id=?", (bill['id'],)).fetchone()['status']
        payment = db.execute("SELECT amount_paid, payment_method, operator FROM payments WHERE bill_id=?", (bill['id'],)).fetchone()
        db.close()
        self.assertEqual(paid, 'paid')
        self.assertEqual(payment['amount_paid'], 125)
        self.assertEqual(payment['payment_method'], 'wechat')
        self.assertEqual(payment['operator'], '体检收费员')

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': str(bill['id']),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('主流程业主', receipt_html)
        self.assertIn('体检收费员', receipt_html)
        self.assertIn('125.00', receipt_html)

        status, report_html = http_get('/reports?period=2032-01&building=HEALTH&status=paid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账期对账', report_html)
        self.assertIn('125.00', report_html)
        self.assertIn('100.0%', report_html)

        status, precheck_html, loc = http_post('/closing/close', {
            'period': '2032-01',
            'notes': '体检结账',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('结账前检查', precheck_html)
        self.assertIn('125.00', precheck_html)

        status, body, loc = http_post('/closing/close', {
            'period': '2032-01',
            'notes': '体检结账',
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        status, body, loc = http_post(f'/bills/{bill["id"]}/pay', {
            'amount_paid': '1.00',
            'payment_method': 'cash',
            'operator': '结账后误操作',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('已结账', urllib.parse.unquote(loc))


    def test_stable_closeout_amount_scope_and_wording_regressions(self):
        from server.db import get_db
        db = get_db()
        owner_b = create_owner(db, '金额专项B座业主', '13900003301')
        b_room = create_room(db, building='金莎国际', unit='B座', room_number='QA-B-01', category='商户', area=50, owner_id=owner_b)
        owner_mall = create_owner(db, '金额专项商场商户', '13900003302')
        mall_room = create_room(db, building='金莎国际', unit='商场', room_number='QA-M-01', category='商户', area=30, owner_id=owner_mall)
        db.execute("UPDATE rooms SET tenant_name='金额专项B座租户', custom_rate=4, payment_cycle='quarterly', contract_start='2039-01-01', contract_end='2039-12-31' WHERE id=?", (b_room,))
        db.execute("UPDATE rooms SET tenant_name='金额专项商场商户', shop_name='金额专项商铺', custom_rate=6, payment_cycle='quarterly', contract_start='2039-01-01', contract_end='2039-12-31' WHERE id=?", (mall_room,))
        prop_fee = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        water_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()['id']
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,previous_reading,current_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (b_room, water_fee, '203901', 0, 12, 12, 'confirmed'))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,previous_reading,current_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (mall_room, water_fee, '203901', 0, 20, 20, 'confirmed'))
        db.commit(); db.close()

        status, _, loc = http_post('/billing/calc', {
            'room_id': str(b_room),
            'period_start': '2039-01-01',
            'period_end': '2039-03-31',
            'fee_types': [str(prop_fee), str(water_fee)],
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        status, _, loc2 = http_post('/billing/calc', {
            'room_id': str(mall_room),
            'period_start': '2039-01-01',
            'period_end': '2039-03-31',
            'fee_types': [str(prop_fee), str(water_fee)],
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = get_db()
        b_amounts = {r['fee_type_id']: float(r['amount']) for r in db.execute("SELECT fee_type_id,amount FROM bills WHERE room_id=?", (b_room,)).fetchall()}
        mall_amounts = {r['fee_type_id']: float(r['amount']) for r in db.execute("SELECT fee_type_id,amount FROM bills WHERE room_id=?", (mall_room,)).fetchall()}
        water_rate = float(db.execute("SELECT unit_price FROM fee_types WHERE id=?", (water_fee,)).fetchone()['unit_price'])
        db.close()
        self.assertAlmostEqual(b_amounts[prop_fee], 600.0)
        self.assertAlmostEqual(b_amounts[water_fee], 12 * water_rate)
        self.assertAlmostEqual(mall_amounts[prop_fee], 540.0)
        self.assertAlmostEqual(mall_amounts[water_fee], 20 * water_rate)

        status, reports = http_get('/reports?period_start=2039-01-01&period_end=2039-03-31', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for text in ['商业物业费收入', '商业水电收入']:
            self.assertIn(text, reports)
        self.assertIn('¥600.00', reports)
        self.assertIn('¥540.00', reports)

        status, auto_page = http_get('/auto_billing?advance_days=365&period_cycle=tenant&target_scope=all', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('合同档案项目', auto_page)
        for text in ['合同租金', '合同物业费', '合同押金']:
            self.assertNotIn(text, auto_page)

        status, delivery = http_get('/delivery_center', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商业收费', delivery)
        self.assertIn('空间合同档案', delivery)
        self.assertNotIn('商户合同闭环', delivery)
        self.assertNotIn('合同出账预览', delivery)


    def test_billing_engine_matches_single_and_batch_amounts(self):
        import server.db as db_module
        db = db_module.get_db()
        try:
            owner_id = db.execute("INSERT INTO owners(name) VALUES('统一计算业主')").lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
                ('ENGINE', 'A座', '901', 9, '居民', 10, owner_id)
            ).lastrowid
            ft = db.execute("SELECT * FROM fee_types WHERE id=1").fetchone()
            room = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
            from server.billing_engine import calculate_bill_amount
            monthly = calculate_bill_amount(db, room, ft, '2026-12')
            multi = calculate_bill_amount(db, room, ft, '2026-12', months=3)
            self.assertEqual(monthly['amount'], 19)
            self.assertEqual(monthly['formula'], '10.0×1.9')
            self.assertEqual(multi['amount'], 57)
            self.assertEqual(multi['monthly_amount'], 19)
        finally:
            db.close()


    def test_billing_fee_checkbox_changes_recalculate_total(self):
        status, html = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('class="fee-check"', html)
        self.assertIn('id="checkAll"', html)
        self.assertNotIn('id="checkAll" onchange=', html)

        with open(os.path.join(PROJECT_ROOT, 'static', 'billing.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn('window.isFeeRowSelected', js)
        self.assertIn('if(!window.isFeeRowSelected(row)) return;', js)
        self.assertIn('e.target.id === "checkAll"', js)
        self.assertIn('if(e.target.classList.contains("fee-check")) calcFees();', js)
        self.assertIn('inp.disabled = !selected;', js)
        self.assertIn('row.querySelectorAll(".fee-check")', js)

