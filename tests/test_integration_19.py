#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 19."""

from tests.integration_base import *


class TestIntegration19(IntegrationTestBase):
    def test_payments_page_has_print_receipt_and_export_actions(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '缴费打印业主', '13900002222')
        room_id = create_room(db, building='PAYACT', unit='A座', room_number='501', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-03', amount=120, status='paid', owner_id=owner_id)
        db.execute("UPDATE bills SET service_start='2034-03-01', service_end='2034-03-31' WHERE id=?", (bill_id,))
        payment_id = create_payment(db, bill_id=bill_id, amount=120, method='cash', operator='打印员')
        db.commit()
        db.close()

        status, body = http_get('/payments?period=2034-03-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('/payments/print', body)
        self.assertIn('/payments/receipts', body)
        self.assertIn('id="paymentActionForm" method="POST" action="/payments/receipts" target="_blank"', body)
        self.assertIn("submitPaymentAction('/payments/print')", body)
        self.assertIn("submitPaymentAction('/payments/receipts')", body)
        self.assertNotIn("this.form.action='/payments/receipts'", body)
        self.assertIn('导出', body)
        self.assertIn('name="payment_ids"', body)
        self.assertIn('class="payment-group-chk"', body)
        self.assertIn('togglePaymentSelection', body)
        self.assertIn('payment_ui.js?v=20260625csrf', body)
        self.assertNotIn("togglePaymentGroup('('", body)
        self.assertNotIn("payment-detail-('", body)
        self.assertRegex(body, r"togglePaymentGroup\('p\d+_room_\d+'\)")
        self.assertIn('payment-detail-p', body)
        with open(os.path.join(PROJECT_ROOT, 'static', 'payment_ui.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn('window.togglePaymentGroup', js)
        self.assertIn('payment-detail-', js)
        self.assertIn('window.submitPaymentAction', js)
        self.assertIn("form.method = 'POST'", js)
        self.assertIn('function appendCsrfToken', js)
        self.assertIn('meta[name="csrf-token"]', js)
        self.assertIn("input.name = '_csrf_token'", js)

        status, print_html, _ = http_post('/payments/print', {'payment_ids': str(payment_id)}, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('缴费记录打印', print_html)
        self.assertIn('收款对象', print_html)
        self.assertIn('PAYACT\\A座\\501', print_html)
        self.assertIn('<th style="width:18%">收费项目</th>', print_html)
        self.assertNotIn('<th>对象</th>', print_html)
        self.assertIn('费用区间', print_html)
        self.assertIn('2034-03-01 至 2034-03-31', print_html)
        self.assertIn('优惠', print_html)
        self.assertIn('减免', print_html)
        self.assertIn('缴费', print_html)
        self.assertIn('欠费', print_html)
        self.assertIn('打印类型：缴费记录打印', print_html)
        self.assertIn('class="print-toolbar"', print_html)
        self.assertIn('保存为PDF', print_html)
        self.assertIn('href="/payments"', print_html)
        self.assertNotIn('href="/bills"', print_html)


    def test_payment_receipt_return_button_goes_back_to_payments_page(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '缴费收据返回业主', '13900002223')
        room_id = create_room(db, building='PAYBACK', unit='A座', room_number='502', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-03', amount=130, status='paid', owner_id=owner_id)
        payment_id = create_payment(db, bill_id=bill_id, amount=130, method='cash', operator='收据返回员')
        db.close()

        status, confirm_html, _ = http_post('/payments/receipts', {'payment_ids': str(payment_id)}, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('收据信息确认', confirm_html)
        self.assertIn('PAYBACK', confirm_html)
        self.assertIn('action="/bills/receipt_by_ids"', confirm_html)
        self.assertIn('name="back" value="/payments"', confirm_html)
        self.assertNotIn('缴费记录打印', confirm_html)

        status, receipt_html, _ = http_post('/bills/receipt_by_ids', {
            'confirm_receipt': '1',
            'bill_ids': str(bill_id),
            'back': '/payments',
            'summary': '缴费收据摘要',
            'operator': '收据返回员',
            'payment_method': 'cash',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('缴费收据摘要', receipt_html)
        self.assertIn('href="/payments"', receipt_html)
        self.assertNotIn('href="/bills"', receipt_html)




    def test_payments_print_stays_direct_print_without_receipt_confirmation(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '普通打印业主', '13900002224')
        room_id = create_room(db, building='PAYPRINTONLY', unit='A座', room_number='503', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-04', amount=88, status='paid', owner_id=owner_id)
        payment_id = create_payment(db, bill_id=bill_id, amount=88, method='transfer', operator='普通打印员')
        db.close()

        status, print_html, _ = http_post('/payments/print', {'payment_ids': str(payment_id)}, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('缴费记录打印', print_html)
        self.assertIn('receipt-new-detail', print_html)
        self.assertIn('打印类型：缴费记录打印', print_html)
        self.assertNotIn('收据信息确认', print_html)

    def test_invoices_default_page_shows_all_available_paid_bills(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '全部待开票业主', '13900008888')
        june_room = create_room(db, building='INVALLJUN', unit='A座', room_number='601', owner_id=owner_id)
        nov_room = create_room(db, building='INVALLNOV', unit='A座', room_number='1101', owner_id=owner_id)
        june_bill = create_bill(db, room_id=june_room, fee_type_id=1, period='2036-06', amount=66, status='paid', owner_id=owner_id)
        nov_bill = create_bill(db, room_id=nov_room, fee_type_id=1, period='2036-11', amount=111, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=june_bill, amount=66, method='cash', operator='发票全部')
        create_payment(db, bill_id=nov_bill, amount=111, method='cash', operator='发票全部')
        db.close()

        status, html = http_get('/invoices', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn(f'value="{june_bill}"', html)
        self.assertIn(f'value="{nov_bill}"', html)
        self.assertIn('INVALLJUN-601', html)
        self.assertIn('INVALLNOV-1101', html)
        self.assertIn('value="" onchange="this.form.submit()"', html)
        self.assertIn('已开发票列表 <small class="text-muted">(全部)</small>', html)


    def test_invoice_available_paid_bills_are_grouped_by_tenant(self):
        from server.db import get_db
        db = get_db()
        owner_a = create_owner(db, '开票分组业主甲', '13900008892')
        owner_b = create_owner(db, '开票分组业主乙', '13900008893')
        room_a = create_room(db, building='INVGROUP', unit='商场', room_number='1F-101', category='商户', owner_id=owner_a)
        room_b = create_room(db, building='INVGROUP', unit='商场', room_number='1F-102', category='商户', owner_id=owner_b)
        db.execute("UPDATE rooms SET tenant_name=?, shop_name=? WHERE id=?", ('开票商户甲', '甲店', room_a))
        db.execute("UPDATE rooms SET tenant_name=?, shop_name=? WHERE id=?", ('开票商户乙', '乙店', room_b))
        bill_a1 = create_bill(db, room_id=room_a, fee_type_id=1, period='2036-12', amount=310, status='paid', owner_id=owner_a)
        bill_a2 = create_bill(db, room_id=room_a, fee_type_id=1, period='2037-01', amount=320, status='paid', owner_id=owner_a)
        bill_b = create_bill(db, room_id=room_b, fee_type_id=1, period='2036-12', amount=410, status='paid', owner_id=owner_b)
        create_payment(db, bill_id=bill_a1, amount=310, method='cash', operator='发票分组')
        create_payment(db, bill_id=bill_a2, amount=320, method='cash', operator='发票分组')
        create_payment(db, bill_id=bill_b, amount=410, method='cash', operator='发票分组')
        db.close()

        status, html = http_get('/invoices', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('<optgroup label="开票商户甲 / INVGROUP-商场-1F-101">', html)
        self.assertIn('<optgroup label="开票商户乙 / INVGROUP-商场-1F-102">', html)
        group_a_start = html.index('label="开票商户甲 / INVGROUP-商场-1F-101"')
        group_a_end = html.index('</optgroup>', group_a_start)
        group_b_start = html.index('label="开票商户乙 / INVGROUP-商场-1F-102"')
        group_b_end = html.index('</optgroup>', group_b_start)
        self.assertIn(f'value="{bill_a1}"', html[group_a_start:group_a_end])
        self.assertIn(f'value="{bill_a2}"', html[group_a_start:group_a_end])
        self.assertNotIn(f'value="{bill_b}"', html[group_a_start:group_a_end])
        self.assertIn(f'value="{bill_b}"', html[group_b_start:group_b_end])


    def test_invoices_period_filter_keeps_selected_november_and_filters_available_bills(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '十一月待开票业主', '13900008889')
        june_room = create_room(db, building='INVNOVJUN', unit='A座', room_number='602', owner_id=owner_id)
        nov_room = create_room(db, building='INVNOVONLY', unit='A座', room_number='1102', owner_id=owner_id)
        june_bill = create_bill(db, room_id=june_room, fee_type_id=1, period='2036-06', amount=66, status='paid', owner_id=owner_id)
        nov_bill = create_bill(db, room_id=nov_room, fee_type_id=1, period='2036-11', amount=111, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=june_bill, amount=66, method='cash', operator='发票十一月')
        create_payment(db, bill_id=nov_bill, amount=111, method='cash', operator='发票十一月')
        db.close()

        status, html = http_get('/invoices?period=2036-11-01', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('value="2036-11-01" onchange="this.form.submit()"', html)
        self.assertIn(f'value="{nov_bill}"', html)
        self.assertIn('INVNOVONLY-1102', html)
        self.assertNotIn(f'value="{june_bill}"', html)
        self.assertNotIn('INVNOVJUN-602', html)
        self.assertIn('已开发票列表 <small class="text-muted">(2036-11-01 至 2036-11-30)</small>', html)


    def test_invoices_filter_by_finance_natural_date_range(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自然日期开票业主', '13900008894')
        room_id = create_room(db, building='INVDATE', unit='商场', room_number='3F-301', owner_id=owner_id)
        inside_bill = create_bill(db, room_id=room_id, fee_type_id=1, period='2036-11~2037-01', amount=311, status='paid', owner_id=owner_id)
        outside_bill = create_bill(db, room_id=room_id, fee_type_id=1, period='2037-02', amount=222, status='paid', owner_id=owner_id)
        db.execute("UPDATE bills SET service_start=?, service_end=? WHERE id=?", ('2036-11-15', '2037-01-14', inside_bill))
        db.execute("UPDATE bills SET service_start=?, service_end=? WHERE id=?", ('2037-02-01', '2037-02-28', outside_bill))
        create_payment(db, bill_id=inside_bill, amount=311, method='cash', operator='发票自然日期')
        create_payment(db, bill_id=outside_bill, amount=222, method='cash', operator='发票自然日期')
        db.close()

        status, html = http_get('/invoices?period_start=2036-12-01&period_end=2036-12-31', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('name="period_start"', html)
        self.assertIn('name="period_end"', html)
        self.assertIn('value="2036-12-01"', html)
        self.assertIn('value="2036-12-31"', html)
        self.assertIn(f'value="{inside_bill}"', html)
        self.assertIn('INVDATE-3F-301', html)
        self.assertNotIn(f'value="{outside_bill}"', html)
        self.assertIn('已开发票列表 <small class="text-muted">(2036-12-01 至 2036-12-31)</small>', html)


    def test_invoice_create_keeps_selected_period_after_success(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '十一月开票后返回业主', '13900008890')
        room_id = create_room(db, building='INVRETURNNOV', unit='A座', room_number='1103', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2036-11', amount=211, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=211, method='cash', operator='发票返回')
        db.close()

        status, body, location = http_post('/invoices/create', {
            'bill_id': str(bill_id),
            'issue_date': '2036-11-05',
            'buyer_name': '十一月开票抬头',
            'buyer_tax_id': 'NOVTAX001',
            'period': '2036-11-01',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        decoded_location = urllib.parse.unquote(location)
        self.assertIn('period=2036-11-01', decoded_location)
        self.assertIn('发票开具成功', decoded_location)


    def test_invoice_create_keeps_selected_date_range_after_success(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '日期范围开票后返回业主', '13900008895')
        room_id = create_room(db, building='INVRETURNDATE', unit='商场', room_number='3F-302', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2036-12', amount=312, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=312, method='cash', operator='发票日期返回')
        db.close()

        status, body, location = http_post('/invoices/create', {
            'bill_id': str(bill_id),
            'issue_date': '2036-12-05',
            'buyer_name': '日期范围开票抬头',
            'buyer_tax_id': 'DATERANGETAX001',
            'period_start': '2036-12-01',
            'period_end': '2036-12-31',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        decoded_location = urllib.parse.unquote(location)
        self.assertIn('period_start=2036-12-01', decoded_location)
        self.assertIn('period_end=2036-12-31', decoded_location)
        self.assertIn('发票开具成功', decoded_location)


    def test_invoice_create_defaults_back_to_all_available_bills_without_period(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '默认全部开票返回业主', '13900008891')
        room_id = create_room(db, building='INVRETURNALL', unit='A座', room_number='605', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2036-06', amount=122, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=122, method='cash', operator='发票返回')
        db.close()

        status, body, location = http_post('/invoices/create', {
            'bill_id': str(bill_id),
            'issue_date': '2036-06-05',
            'buyer_name': '默认全部开票抬头',
            'buyer_tax_id': 'ALLTAX001',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        decoded_location = urllib.parse.unquote(location)
        self.assertIn('/invoices?flash=', decoded_location)
        self.assertNotIn('period=', decoded_location)


    def test_paid_bills_available_for_invoice_even_without_existing_invoice(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '待开发票业主', '13900003333')
        room_id = create_room(db, building='INVAVAIL', unit='B座', room_number='701', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-04', amount=188, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=188, method='transfer', operator='开票员')
        db.close()

        status, body = http_get('/invoices?period=2034-04-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'value="{bill_id}"', body)
        self.assertIn('INVAVAIL-701', body)
        self.assertIn('待开发票业主', body)
