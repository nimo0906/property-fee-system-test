#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 27."""

from tests.integration_base import *


class TestIntegration27(IntegrationTestBase):
    def test_reports_reconciliation_sections_and_export_links(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('报表对账业主', '13200000000')").lastrowid
        room_a = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('REPORTA', 'A座', '1501', 15, '居民', 70, ?)
        """, (owner_id,)).lastrowid
        room_b = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('REPORTB', 'A座', '1502', 15, '居民', 80, ?)
        """, (owner_id,)).lastrowid
        paid_bill = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-11', 100, '2030-11-28', 'paid', 'RPT-PAID')
        """, (room_a, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 100, 'cash', '报表员')", (paid_bill,))
        partial_bill = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-11', 80, '2030-11-28', 'partial', 'RPT-PARTIAL')
        """, (room_a, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 30, 'cash', '报表员')", (partial_bill,))
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-11', 60, '2030-11-28', 'unpaid', 'RPT-UNPAID')
        """, (room_b, owner_id))
        db.commit()
        db.close()

        status, html = http_get('/reports?period=2030-11', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('账期对账', html)
        self.assertIn('楼栋对账统计', html)
        self.assertIn('欠费清单', html)
        self.assertIn('应收合计', html)
        self.assertIn('已收合计', html)
        self.assertIn('未收合计', html)
        self.assertIn('收缴率', html)
        self.assertIn('账单状态分布', html)
        self.assertIn('已缴账单', html)
        self.assertIn('部分缴费', html)
        self.assertIn('未缴账单', html)
        self.assertIn('本期回款缺口', html)
        self.assertIn('240.0', html)
        self.assertIn('130.0', html)
        self.assertIn('110.0', html)
        self.assertIn('REPORTA', html)
        self.assertIn('REPORTB', html)
        self.assertIn('RPT-PARTIAL', html)
        self.assertIn('RPT-UNPAID', html)
        self.assertIn('/reports/reconciliation.csv?period_start=2030-11-01&amp;period_end=2030-11-30', html)


    def test_reports_filter_by_finance_natural_date_range(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('报表自然日期业主', '13200001234')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('RPTDATE', '商场', '3F-601', 3, '商户', 66, ?)
        """, (owner_id,)).lastrowid
        inside_bill = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number, service_start, service_end)
            VALUES(?, ?, 1, '2031-11~2032-01', 360, '2032-01-14', 'paid', 'RPT-DATE-IN', '2031-11-15', '2032-01-14')
        """, (room_id, owner_id)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number, service_start, service_end)
            VALUES(?, ?, 1, '2032-02', 220, '2032-02-28', 'paid', 'RPT-DATE-OUT', '2032-02-01', '2032-02-28')
        """, (room_id, owner_id))
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 360, 'cash', '报表自然日期')", (inside_bill,))
        db.commit(); db.close()

        status, html = http_get('/reports?period_start=2031-12-01&period_end=2031-12-31&building=RPTDATE', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('name="period_start"', html)
        self.assertIn('name="period_end"', html)
        self.assertIn('value="2031-12-01"', html)
        self.assertIn('value="2031-12-31"', html)
        self.assertIn('账期对账 <small class="text-muted">(2031-12-01 至 2031-12-31)</small>', html)
        self.assertNotIn('RPT-DATE-OUT', html)
        self.assertIn('应收合计</div><strong class="money">¥360.0</strong>', html)
        self.assertIn('/reports/reconciliation.csv?period_start=2031-12-01&amp;period_end=2031-12-31&amp;building=RPTDATE', html)

        status, csv_body = http_get('/reports/reconciliation.csv?period_start=2031-12-01&period_end=2031-12-31&building=RPTDATE', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('RPT-DATE-IN', csv_body)
        self.assertNotIn('RPT-DATE-OUT', csv_body)


    def test_reports_tenant_summary_csv_export_and_link(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('租户报表业主', '12800000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id, tenant_name, tenant_phone, shop_name, business_type)
            VALUES('TENANTRPT', '商场', '1F-201', 1, '商户', 88, ?, '张租户', '13812345678', '测试奶茶店', '餐饮')
        """, (owner_id,)).lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2031-01', 300, '2031-01-28', 'partial', 'TENANT-RPT-1')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 120, 'wechat', '报表员')", (bill_id,))
        db.commit(); db.close()

        status, html = http_get('/reports?period=2031-01&building=TENANTRPT', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('导出租户CSV', html)
        self.assertIn('/reports/tenants.csv?period_start=2031-01-01&amp;period_end=2031-01-31&amp;building=TENANTRPT', html)

        status, csv_body = http_get('/reports/tenants.csv?period=2031-01&building=TENANTRPT', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('tenant,shop,building,room,business_type,bill_count,amount,paid,due,phone', csv_body)
        self.assertIn('张租户', csv_body)
        self.assertIn('测试奶茶店', csv_body)
        self.assertIn('餐饮', csv_body)
        self.assertIn('300.0', csv_body)
        self.assertIn('120.0', csv_body)
        self.assertIn('180.0', csv_body)


    def test_reports_export_actions_are_grouped_by_business_purpose(self):
        status, html = http_get('/reports?period=2031-01', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('class="report-export-panel"', html)
        self.assertIn('对账与打印', html)
        self.assertIn('客户维度', html)
        self.assertIn('欠费分析', html)
        self.assertIn('打印当前对账单', html)
        self.assertIn('导出对账CSV', html)
        self.assertIn('导出租户CSV', html)
        self.assertIn('租户欠费排行CSV', html)
        self.assertIn('费用欠费CSV', html)
        self.assertIn('欠费明细CSV', html)
        self.assertIn('收款流水CSV', html)
        self.assertIn('减免明细CSV', html)
        self.assertIn('客户汇总CSV', html)
        self.assertIn('data-export-group="reconciliation"', html)
        self.assertIn('data-export-group="tenant"', html)
        self.assertIn('data-export-group="arrears"', html)


    def test_reports_detail_exports_for_arrears_payments_waivers_and_customer_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('导出明细业主', '12700009999')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id, tenant_name, tenant_phone, shop_name)
            VALUES('RPTEXPORT', 'B座', '2101', 21, '商户', 90, ?, '导出租户', '13899998888', '导出商铺')
        """, (owner_id,)).lastrowid
        partial_bill = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2031-03', 300, '2031-03-28', 'partial', 'RPT-EXPORT-PART')
        """, (room_id, owner_id)).lastrowid
        unpaid_bill = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 2, '2031-03', 120, '2031-03-28', 'unpaid', 'RPT-EXPORT-DUE')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator, receipt_number) VALUES(?, 80, 'wechat', '流水测试员', 'RC-RPT-EXPORT')", (partial_bill,))
        db.execute("""
            INSERT INTO bill_adjustments(bill_id, old_amount, new_amount, reason, approved_by)
            VALUES(?, 300, 260, '报表导出减免', '财务主管')
        """, (partial_bill,))
        db.commit(); db.close()

        status, arrears_csv = http_get('/reports/arrears_detail.csv?period=2031-03&building=RPTEXPORT', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('bill_number,target,customer,phone,fee_type,period,amount,paid,due,status,due_date', arrears_csv)
        self.assertIn('RPT-EXPORT-PART', arrears_csv)
        self.assertIn('RPT-EXPORT-DUE', arrears_csv)
        self.assertIn('220.0', arrears_csv)
        self.assertIn('120.0', arrears_csv)

        status, payments_csv = http_get('/reports/payment_detail.csv?period=2031-03&building=RPTEXPORT', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('payment_date,receipt_number,bill_number,target,customer,fee_type,method,operator,amount', payments_csv)
        self.assertIn('RC-RPT-EXPORT', payments_csv)
        self.assertIn('流水测试员', payments_csv)
        self.assertIn('80.0', payments_csv)

        status, waivers_csv = http_get('/reports/waivers.csv?period=2031-03&building=RPTEXPORT', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('created_at,bill_number,target,customer,fee_type,old_amount,new_amount,waiver_amount,reason,approved_by', waivers_csv)
        self.assertIn('报表导出减免', waivers_csv)
        self.assertIn('40.0', waivers_csv)

        status, summary_csv = http_get('/reports/customer_summary.csv?period=2031-03&building=RPTEXPORT', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('customer,target,phone,bill_count,amount,paid,due,paid_count,partial_count,unpaid_count', summary_csv)
        self.assertIn('导出租户', summary_csv)
        self.assertIn('420.0', summary_csv)
        self.assertIn('80.0', summary_csv)
        self.assertIn('340.0', summary_csv)


    def test_reports_tenant_arrears_ranking_csv_export(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('租户欠费排行业主', '12700000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id, tenant_name, tenant_phone, shop_name, business_type)
            VALUES('TENANTDUE', '商场', '2F-501', 2, '商户', 66, ?, '欠费租户', '13712345678', '欠费咖啡店', '餐饮')
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2031-02', 500, '2031-02-28', 'unpaid', 'TENANT-DUE-1')
        """, (room_id, owner_id))
        db.commit(); db.close()

        status, html = http_get('/reports?period=2031-02&building=TENANTDUE', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('租户欠费排行CSV', html)
        self.assertIn('/reports/tenant_arrears.csv?period_start=2031-02-01&amp;period_end=2031-02-28&amp;building=TENANTDUE', html)

        status, csv_body = http_get('/reports/tenant_arrears.csv?period=2031-02&building=TENANTDUE', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('tenant,shop,building,room,business_type,bill_count,due,phone', csv_body)
        self.assertIn('欠费租户', csv_body)
        self.assertIn('欠费咖啡店', csv_body)
        self.assertIn('500.0', csv_body)


    def test_reports_fee_arrears_csv_export(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('费用欠费业主', '12700000001')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('FEEDUE', 'A座', '1901', 19, '居民', 80, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2031-04', 410, '2031-04-28', 'unpaid', 'FEE-DUE-1')
        """, (room_id, owner_id))
        db.commit(); db.close()

        status, html = http_get('/reports?period=2031-04&building=FEEDUE', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('费用欠费CSV', html)
        self.assertIn('/reports/fee_arrears.csv?period_start=2031-04-01&amp;period_end=2031-04-30&amp;building=FEEDUE', html)

        status, csv_body = http_get('/reports/fee_arrears.csv?period=2031-04&building=FEEDUE', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('fee_type,bill_count,due', csv_body)
        self.assertIn('物业费(居民)', csv_body)
        self.assertIn('410.0', csv_body)


    def test_reports_can_select_multi_month_billing_period(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('跨月报表业主', '13200001111')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('RANGE_REPORT', 'A座', '1601', 16, '商户', 90, ?)
        """, (owner_id,)).lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-07~2030-10', 400, '2030-10-28', 'partial', 'RANGE-RPT')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 150, 'cash', '报表员')", (bill_id,))
        db.commit()
        db.close()

        status, html = http_get('/reports?period=2030-07~2030-10', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('账期对账 <small class="text-muted">(2030-07-01 至 2030-10-31)</small>', html)
        self.assertIn('RANGE-RPT', html)
        self.assertIn('400.0', html)
        self.assertIn('150.0', html)
        self.assertIn('name="period_start"', html)
        self.assertIn('value="2030-07-01"', html)
        self.assertIn('value="2030-10-31"', html)
        self.assertIn('/reports/reconciliation.csv?period_start=2030-07-01&amp;period_end=2030-10-31', html)

        status, inner_html = http_get('/reports?period=2030-08', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('RANGE-RPT', inner_html)
        self.assertIn('RANGE_REPORT', inner_html)
        self.assertIn('应收总额</div><div class="metric-value money">¥400.0</div>', inner_html)
        self.assertIn('已收总额</div><div class="metric-value money money-paid">¥150.0</div>', inner_html)
        self.assertRegex(inner_html, r'(?s)楼栋缴费统计.*RANGE_REPORT.*¥400\.0.*¥150\.0')

