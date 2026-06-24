#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 08."""

from tests.integration_base import *


class TestIntegration08(IntegrationTestBase):
    def test_auto_billing_batch_detail_lists_generated_bills(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动详情业主', '13955556666')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTODETAIL', 'B座', '2603', 26, '居民', 100, owner_id, '自动详情租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = get_db()
        batch_no = db.execute("SELECT auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()['auto_batch_no']
        db.close()

        status, detail = http_get(f'/auto_billing/runs/{batch_no}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动出账批次详情', detail)
        self.assertIn(batch_no, detail)
        self.assertIn('自动详情租户', detail)
        self.assertIn('AUTODETAIL-B座-2603', detail)
        self.assertIn('物业费(居民)', detail)
        self.assertIn('2026-06-27 至 2026-09-26', detail)
        self.assertIn('2026-06-26', detail)
        self.assertIn('570.0', detail)
        self.assertIn('批次汇总', detail)
        self.assertIn('应收合计', detail)
        self.assertIn('已收合计', detail)
        self.assertIn('未收合计', detail)
        self.assertIn('¥570.0', detail)
        self.assertIn('可撤回', detail)
        self.assertIn('按租户/房间分组', detail)
        self.assertIn('自动详情租户 / AUTODETAIL-B座-2603', detail)
        self.assertIn('1 笔', detail)
        self.assertIn(f'/bills?auto_batch_no={batch_no}', detail)

        status, bills_page = http_get(f'/bills?auto_batch_no={batch_no}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前正在查看自动出账批次', bills_page)
        self.assertIn(batch_no, bills_page)
        self.assertIn(f'/auto_billing/runs/{batch_no}', bills_page)
        self.assertIn('返回批次详情', bills_page)
        self.assertIn('/bills', bills_page)
        self.assertIn('清除批次筛选', bills_page)
        self.assertIn('自动详情租户', bills_page)
        self.assertIn('AUTODETAIL-B座-2603', bills_page)
        self.assertIn('自动出账服务期 2026-06-27 至 2026-09-26', bills_page)


    def test_reminders_filters_by_natural_date_range(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '催缴自然日期业主', '13900001234')
        room_id = create_room(db, building='REMNAT', unit='商场', room_number='R-101', category='商户', owner_id=owner_id)
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)' LIMIT 1").fetchone()[0]
        db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,service_start,service_end)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, fee_id, '2039-05~2039-07', 300, '2026-05-20', 'overdue', 'REM-NAT-IN', 'auto_contract', '2039-05-15', '2039-07-14'))
        db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,service_start,service_end)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, fee_id, '2039-08', 100, '2026-08-20', 'overdue', 'REM-NAT-OUT', 'auto_contract', '2039-08-01', '2039-08-31'))
        db.commit(); db.close()

        status, body = http_get('/reminders?period_start=2039-06-01&period_end=2039-06-30&keyword=R-101&status=overdue', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('起始日期', body)
        self.assertIn('截止日期', body)
        self.assertIn('2039-05~2039-07', body)
        self.assertIn('催缴自然日期业主', body)
        self.assertNotIn('2039-08', body)


    def test_reminders_default_to_all_periods_and_support_keyword_unit_filters(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '催缴筛选业主', '13900000016')
        room_june = create_room(db, building='REMALL', unit='A座', room_number='601', category='居民', owner_id=owner_id)
        room_nov = create_room(db, building='REMALL', unit='商场', room_number='1101', category='商户', owner_id=owner_id)
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)' LIMIT 1").fetchone()[0]
        db.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)", (room_june, owner_id, fee_id, '2026-06', 66, '2026-06-28', 'unpaid', 'REM-JUN-001'))
        db.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,service_start,service_end) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (room_nov, owner_id, fee_id, '2026-07', 111, '2026-07-03', 'unpaid', 'REM-JUL-001', 'auto_contract', '2026-07-01', '2026-07-31'))
        db.commit(); db.close()

        status, body = http_get('/reminders', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="" onchange="this.form.submit()"', body)
        self.assertIn('REMALL-A座-601', body)
        self.assertIn('REMALL-商场-1101', body)

        status, november = http_get('/reminders?period=2026-07-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="2026-07-01" onchange="this.form.submit()"', november)
        self.assertIn('REMALL-商场-1101', november)
        self.assertNotIn('REMALL-A座-601', november)

        status, filtered = http_get('/reminders?keyword=1101&unit=%E5%95%86%E5%9C%BA', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="1101"', filtered)
        self.assertIn('REMALL-商场-1101', filtered)
        self.assertNotIn('REMALL-A座-601', filtered)


    def test_auto_billing_bill_shows_service_period_in_approaching_reminders(self):
        from server.db import get_db
        db = get_db()
        owner_id = db.execute(
            "INSERT INTO owners(name, phone) VALUES(?, ?)",
            ('自动催缴业主', '13922223333')
        ).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
            ('AUTOREM', 'B座', '2601', 26, '居民', 100, owner_id, '自动催缴租户')
        ).lastrowid
        db.execute(
            """INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,
            bill_number,source,service_start,service_end) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (room_id, owner_id, 1, '2026-06~2026-09', 570, '2026-06-26', 'unpaid',
             'AUTO-REMINDER-001', 'auto_contract', '2026-06-27', '2026-09-26')
        )
        db.commit(); db.close()

        status, body = http_get('/reminders?period=2026-06-01&status=approaching', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动催缴业主', body)
        self.assertIn('自动出账', body)
        self.assertIn('服务期 2026-06-27 至 2026-09-26', body)
        self.assertIn('截止 2026-06-26', body)


    def test_auto_billing_outputs_show_service_period(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动输出业主', '13966667777')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOOUTPUT', 'B座', '2801', 28, '居民', 100, owner_id, '自动输出租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        bill_id = db.execute("""
            INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,
            bill_number,source,service_start,service_end,auto_batch_no)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            room_id, owner_id, fee_id, '2026-06~2026-09', 570, '2026-06-26', 'unpaid',
            'AUTO-OUTPUT-001', 'auto_contract', '2026-06-27', '2026-09-26', 'AUTO-OUTPUT-BATCH'
        )).lastrowid
        db.commit(); db.close()

        status, print_html, loc = http_post('/bills/print_selected', {
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-06-27 至 2026-09-26', print_html)

        status, confirm_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收据信息确认', confirm_html)
        self.assertIn('2026-06-27 至 2026-09-26', confirm_html)

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'confirm_receipt': '1',
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-06-27 至 2026-09-26', receipt_html)

        status, csv_body, loc = http_post('/bills/export_selected', {
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('服务开始日', csv_body)
        self.assertIn('服务结束日', csv_body)
        self.assertIn('2026-06-27', csv_body)
        self.assertIn('2026-09-26', csv_body)


    def test_auto_billing_paid_bill_flows_to_reports_invoice_and_blocks_rollback(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动链路业主', '13977778888')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOFLOW', 'B座', '2901', 29, '居民', 100, owner_id, '自动链路租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing/runs/', loc)

        db = get_db()
        bill = db.execute("SELECT id,auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        bill_id = bill['id']
        batch_no = bill['auto_batch_no']
        db.execute("INSERT INTO payments(bill_id,amount_paid,payment_method,operator) VALUES(?,?,?,?)", (bill_id, 570, 'cash', '自动链路收费员'))
        db.execute("UPDATE bills SET status='paid' WHERE id=?", (bill_id,))
        db.commit(); db.close()

        status, report_html = http_get('/reports?period=2026-07&building=AUTOFLOW&status=paid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('AUTOFLOW', report_html)
        self.assertIn('570.0', report_html)
        self.assertIn('已收合计', report_html)
        self.assertIn('自动链路收费员', report_html)

        status, report_csv = http_get('/reports/reconciliation.csv?period=2026-07&building=AUTOFLOW&status=paid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('AUTOFLOW', report_csv)
        self.assertIn('自动链路业主', report_csv)
        self.assertIn('570.0', report_csv)

        status, invoice_html = http_get('/invoices?period=2026-07-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'value="{bill_id}"', invoice_html)
        self.assertIn('AUTOFLOW-2901', invoice_html)
        self.assertIn('自动链路业主', invoice_html)

        status, body, loc = http_post(f'/auto_billing/runs/{batch_no}/rollback', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('保留1笔不可撤回账单', urllib.parse.unquote(loc))
        db = get_db()
        self.assertIsNotNone(db.execute("SELECT id FROM bills WHERE id=?", (bill_id,)).fetchone())
        run = db.execute("SELECT status,rollback_count FROM auto_billing_runs WHERE batch_no=?", (batch_no,)).fetchone()
        db.close()
        self.assertEqual(run['status'], 'blocked')
        self.assertEqual(run['rollback_count'], 0)


