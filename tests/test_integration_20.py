#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 20."""

from tests.integration_base import *


class TestIntegration20(IntegrationTestBase):
    def test_range_paid_bills_are_available_for_invoice_by_inner_month(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '区间待开发票业主', '13900007777')
        room_id = create_room(db, building='INVRANGE', unit='B座', room_number='808', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-06~2034-09', amount=488, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=488, method='transfer', operator='开票员')
        db.close()

        status, body = http_get('/invoices?period=2034-07-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'value="{bill_id}"', body)
        self.assertIn('INVRANGE-808', body)
        self.assertIn('区间待开发票业主', body)


    def test_invoice_print_link_opens_in_current_window_and_has_content(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '发票打印业主', '13900005555')
        room_id = create_room(db, building='INVOICEPRINT', unit='A座', room_number='1701', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-06', amount=188, status='paid', owner_id=owner_id)
        db.execute("UPDATE bills SET service_start='2034-06-01', service_end='2034-06-30' WHERE id=?", (bill_id,))
        invoice_id = db.execute("""
            INSERT INTO invoices(bill_id, invoice_number, amount, issue_date, buyer_name, buyer_tax_id)
            VALUES(?, 'INV-PRINT-001', 188, '2034-06-02', '发票打印抬头', 'TAX001')
        """, (bill_id,)).lastrowid
        db.commit()
        db.close()

        status, page = http_get('/invoices?period=2034-06', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'href="/invoices/{invoice_id}/print"', page)
        self.assertNotIn(f'href="/invoices/{invoice_id}/print" class="btn btn-sm btn-outline-info" target="_blank"', page)

        status, print_page = http_get(f'/invoices/{invoice_id}/print', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('电子发票', print_page)
        self.assertIn('INV-PRINT-001', print_page)
        self.assertIn('发票打印抬头', print_page)
        self.assertIn('188.00', print_page)
        self.assertIn('电子发票（普通发票）', print_page)
        self.assertIn('购买方信息', print_page)
        self.assertIn('销售方信息', print_page)
        self.assertIn('价税合计（大写）', print_page)
        self.assertIn('价税合计（小写）', print_page)
        self.assertIn('壹佰捌拾捌元整', print_page)
        self.assertIn('本系统打印样式，仅用于内部留存', print_page)
        self.assertIn('保存为PDF', print_page)
        self.assertIn('打印对话框中选择“保存为 PDF”', print_page)
        self.assertIn('class="invoice-qr"', print_page)
        self.assertIn('class="invoice-copy-label"', print_page)
        self.assertIn('class="fiscal-mark"', print_page)
        self.assertIn('合计', print_page)
        self.assertIn('class="invoice-code-line"', print_page)
        self.assertIn('机器编号', print_page)
        self.assertIn('开票校验码', print_page)
        self.assertIn('class="invoice-password-zone"', print_page)
        self.assertIn('class="invoice-watermark"', print_page)
        self.assertIn('数电票据样式参考，仅用于内部留存', print_page)
        self.assertIn('内部凭证信息', print_page)
        self.assertIn('服务期', print_page)
        self.assertIn('缴费截止日', print_page)
        self.assertIn('2034-06-01 至 2034-06-30', print_page)


    def test_invoice_list_filters_by_keyword_and_buyer(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '发票筛选业主', '13900006666')
        room_id = create_room(db, building='INVFILTER', unit='商场', room_number='2F-301', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-08', amount=260, status='paid', owner_id=owner_id)
        db.execute("""
            INSERT INTO invoices(bill_id, invoice_number, amount, issue_date, buyer_name, buyer_tax_id)
            VALUES(?, 'INV-FILTER-001', 260, '2034-08-02', '筛选抬头公司', 'FILTER-TAX')
        """, (bill_id,))
        db.commit(); db.close()

        status, html = http_get('/invoices?period=2034-08&keyword=%E7%AD%9B%E9%80%89%E6%8A%AC%E5%A4%B4', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="keyword"', html)
        self.assertIn('筛选抬头公司', html)
        self.assertIn('INV-FILTER-001', html)
        self.assertIn('INVFILTER-商场-2F-301', html)
        self.assertIn('发票列表筛选', html)


    def test_invoice_page_groups_filter_issued_and_available_bills(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '发票分区业主', '13900007777')
        room_id = create_room(db, building='INVSECTIONS', unit='B座', room_number='1801', owner_id=owner_id)
        issued_bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-09', amount=180, status='paid', owner_id=owner_id)
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2034-09', 220, '2034-09-28', 'paid', 'INV-SECTION-AVAILABLE')
        """, (room_id, owner_id))
        db.execute("""
            INSERT INTO invoices(bill_id, invoice_number, amount, issue_date, buyer_name, buyer_tax_id)
            VALUES(?, 'INV-SECTION-001', 180, '2034-09-02', '分区抬头', 'SECTION-TAX')
        """, (issued_bill_id,))
        db.commit(); db.close()

        status, html = http_get('/invoices?period=2034-09', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('class="invoice-dashboard"', html)
        self.assertIn('data-invoice-section="filters"', html)
        self.assertIn('筛选发票', html)
        self.assertIn('data-invoice-section="issued"', html)
        self.assertIn('已开发票列表', html)
        self.assertIn('data-invoice-section="available"', html)
        self.assertIn('待开票账单', html)
        self.assertIn('INV-SECTION-001', html)
        self.assertIn('¥180.00', html)
        self.assertIn('¥220.00', html)
        self.assertIn('筛选范围已开票金额', html)


    def test_audit_logs_details_are_readable_and_admin_can_delete_selected(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,old_value,new_value,reason) VALUES(?,?,?,?,?,?,?,?,?)",
                   ('乱码测试', 'bill', 1, 'admin', 'admin', '127.0.0.1', '{"amount":100}', '{"amount":120}', '详情核对'))
        log_id = db.execute("SELECT MAX(id) FROM audit_logs WHERE action='乱码测试'").fetchone()[0]
        db.commit(); db.close()

        status, html = http_get('/audit_logs?keyword=%E4%B9%B1%E7%A0%81%E6%B5%8B%E8%AF%95', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('选择', html)
        self.assertIn('格式化详情', html)
        self.assertIn('action="/audit_logs/delete"', html)
        self.assertIn('amount', html)
        self.assertIn('审计摘要', html)
        self.assertIn('高风险操作', html)
        self.assertIn('name="username"', html)
        self.assertIn('name="date_from"', html)
        self.assertIn('/audit_logs/export.csv?', html)

        status, csv_body = http_get('/audit_logs/export.csv?keyword=%E4%B9%B1%E7%A0%81%E6%B5%8B%E8%AF%95', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('created_at,action,entity_type,entity_id,username,role,ip,reason,changed_fields,old_value,new_value', csv_body)
        self.assertIn('amount', csv_body)
        self.assertIn('乱码测试', csv_body)
        self.assertIn('详情核对', csv_body)

        status, body, loc = http_post('/audit_logs/delete', {'log_ids': str(log_id)}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        exists = db.execute('SELECT COUNT(*) FROM audit_logs WHERE id=?', (log_id,)).fetchone()[0]
        db.close()
        self.assertEqual(exists, 0)


    def test_audit_logs_page_groups_filter_risk_actions_and_details(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,old_value,new_value,reason) VALUES(?,?,?,?,?,?,?,?,?)",
                   ('bill_amount_update', 'bill', 101, 'admin', 'admin', '127.0.0.1', '{"amount":300}', '{"amount":330}', '页面分组'))
        db.commit(); db.close()

        status, html = http_get('/audit_logs?keyword=%E9%A1%B5%E9%9D%A2%E5%88%86%E7%BB%84', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('class="audit-control-panel"', html)
        self.assertIn('data-audit-section="filters"', html)
        self.assertIn('筛选日志', html)
        self.assertIn('data-audit-section="risk"', html)
        self.assertIn('高风险快捷筛选', html)
        self.assertIn('data-audit-section="actions"', html)
        self.assertIn('导出当前筛选CSV', html)
        self.assertIn('删除选中日志', html)
        self.assertIn('class="audit-log-table"', html)
        self.assertIn('查看变更详情', html)
        self.assertIn('字段差异', html)


    def test_audit_logs_high_risk_quick_filter(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,reason) VALUES(?,?,?,?,?,?,?)",
                   ('bill_delete', 'bill', 88, 'admin', 'admin', '127.0.0.1', '高风险删除'))
        db.execute("INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,reason) VALUES(?,?,?,?,?,?,?)",
                   ('login_success', 'user', 1, 'admin', 'admin', '127.0.0.1', '普通登录'))
        db.commit(); db.close()

        status, html = http_get('/audit_logs?risk=high', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('高风险快捷筛选', html)
        self.assertIn('name="risk" value="high"', html)
        self.assertIn('bill_delete', html)
        self.assertIn('高风险删除', html)
        self.assertNotIn('普通登录', html)


    def test_audit_logs_highlight_old_new_diff_fields(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,old_value,new_value,reason) VALUES(?,?,?,?,?,?,?,?,?)",
                   ('bill_amount_update', 'bill', 99, 'admin', 'admin', '127.0.0.1', '{"amount":100,"due_date":"2031-02-01"}', '{"amount":120,"due_date":"2031-02-15"}', '差异高亮'))
        db.commit(); db.close()

        status, html = http_get('/audit_logs?keyword=%E5%B7%AE%E5%BC%82%E9%AB%98%E4%BA%AE', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('字段差异', html)
        self.assertIn('audit-diff-table', html)
        self.assertIn('amount', html)
        self.assertIn('100', html)
        self.assertIn('120', html)
        self.assertIn('due_date', html)


    def test_audit_logs_csv_includes_changed_fields_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,old_value,new_value,reason) VALUES(?,?,?,?,?,?,?,?,?)",
                   ('bill_amount_update', 'bill', 100, 'admin', 'admin', '127.0.0.1', '{"amount":200,"due_date":"2031-03-01"}', '{"amount":260,"due_date":"2031-03-15"}', 'CSV字段摘要'))
        db.commit(); db.close()

        status, csv_body = http_get('/audit_logs/export.csv?keyword=CSV%E5%AD%97%E6%AE%B5%E6%91%98%E8%A6%81', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('created_at,action,entity_type,entity_id,username,role,ip,reason,changed_fields,old_value,new_value', csv_body)
        self.assertIn('amount;due_date', csv_body)


    def test_backup_page_has_direct_preview_action(self):
        import server.db as db_module
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, page = http_get('/backups', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'/backups/{name}/preview', page)

        status, preview = http_get(f'/backups/{name}/preview', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('备份预览', preview)
        self.assertIn('备份数据摘要', preview)
        self.assertNotIn('确认恢复', preview)

