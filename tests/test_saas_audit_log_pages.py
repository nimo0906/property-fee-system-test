import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasAuditLogPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None, tenant_name='审计物业', project_name='审计项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_audit_log_page(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/audit-logs', page.text)

    def test_audit_log_page_lists_current_tenant_actions_without_password_plaintext(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = self._client('system_admin', database_url=db_url)
            created = admin.post('/api/users', json={'username': 'cashier_audit', 'role_code': 'cashier'})
            self.assertEqual(created.status_code, 200)
            reset = admin.post(f"/api/users/{created.json()['item']['id']}/reset-password", json={'new_password': 'secret-temp-password'})
            self.assertEqual(reset.status_code, 200)

            page = admin.get('/backoffice/audit-logs')
            self.assertEqual(page.status_code, 200)
            self.assertIn('审计日志', page.text)
            self.assertIn('user.password_reset', page.text)
            self.assertIn('cashier_audit', page.text)
            self.assertNotIn('secret-temp-password', page.text)

    def test_audit_log_page_groups_high_risk_actions_and_documents_security_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = self._client('system_admin', database_url=db_url)
            created = admin.post('/api/users', json={'username': 'audit_cashier', 'role_code': 'cashier'})
            admin.post(f"/api/users/{created.json()['item']['id']}/reset-password", json={'new_password': 'NoPlaintext-2026'})
            csv_text = 'building,unit,room_number,category,area\n1栋,1单元,101,居民,80'
            preview = admin.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
            import_id = preview.text.split('name="import_id" value="')[1].split('"')[0]
            admin.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id}, follow_redirects=False)
            fee = admin.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.0}).json()['item']
            target = admin.get('/api/charge-targets').json()['items'][0]
            bill = admin.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'],
                'billing_period': '2026-06', 'service_start': '2026-06-01', 'service_end': '2026-06-30',
            }).json()['item']
            admin.post(f"/api/bills/{bill['id']}/approve", json={})
            admin.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'AUDIT-PAY-1',
            })
            backup = admin.post('/api/backups/create', json={}).json()['item']
            admin.post('/api/restore-drills', json={'backup_id': backup['backup_id'], 'scope': 'database'})

            page = admin.get('/backoffice/audit-logs')
            self.assertEqual(page.status_code, 200)
            html = page.text
            for text in [
                '高风险操作分类',
                '账号操作',
                '密码操作',
                '导入操作',
                '出账操作',
                '收款操作',
                '备份操作',
                '恢复操作',
                '只显示当前租户和当前项目的审计日志',
                '密码不展示在页面、日志或审计明细',
                '审计日志只读展示，不提供页面删除',
            ]:
                self.assertIn(text, html)
            self.assertIn('user.password_reset', html)
            self.assertIn('import.confirm', html)
            self.assertIn('bill.generate', html)
            self.assertIn('payment.record', html)
            self.assertIn('backup.create', html)
            self.assertIn('restore.drill', html)
            self.assertNotIn('NoPlaintext-2026', html)
            self.assertNotIn('POSTGRES_PASSWORD=', html)
            self.assertNotIn('APP_SECRET_KEY=', html)

    def test_executive_can_view_audit_logs_readonly(self):
        client = self._client('executive')
        page = client.get('/backoffice/audit-logs')
        self.assertEqual(page.status_code, 200)
        self.assertIn('审计日志', page.text)
        self.assertIn('只读', page.text)

    def test_audit_log_page_is_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin_a = self._client('system_admin', database_url=db_url, tenant_name='A审计物业', project_name='A审计项目')
            created = admin_a.post('/api/users', json={'username': 'a_cashier', 'role_code': 'cashier'})
            self.assertEqual(created.status_code, 200)
            admin_a.post(f"/api/users/{created.json()['item']['id']}/active", json={'is_active': False})

            admin_b = self._client('system_admin', database_url=db_url, tenant_name='B审计物业', project_name='B审计项目')
            page_b = admin_b.get('/backoffice/audit-logs')
            self.assertEqual(page_b.status_code, 200)
            self.assertIn('审计日志', page_b.text)
            self.assertNotIn('a_cashier', page_b.text)
            self.assertNotIn('user.disable', page_b.text)


    def test_batch_billing_audit_page_shows_created_amount_total(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            client.post('/api/charge-targets', json={
                'building': '审计金额区', 'unit': '一层', 'room_number': 'A-101', 'category': '商户', 'area': 40,
            })
            client.post('/api/charge-targets', json={
                'building': '审计金额区', 'unit': '一层', 'room_number': 'A-102', 'category': '商户', 'area': 60,
            })
            fee = client.post('/api/fee-types', json={
                'name': '商户物业费', 'unit_price': 2, 'billing_mode': 'area',
            }).json()['item']

            response = client.post('/api/bills/batch-generate', json={
                'fee_type_id': fee['id'], 'billing_period': '2028-02',
                'service_start': '2028-02-01', 'service_end': '2028-02-29',
                'category': '商户', 'building': '审计金额区',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['amount_total'], 200.0)

            page = client.get('/backoffice/audit-logs?action=bill.batch_generate')
            self.assertEqual(page.status_code, 200)
            self.assertIn('bill.batch_generate', page.text)
            self.assertIn('出账操作</strong><div class="sub">1 条', page.text)
            self.assertIn('生成2张，跳过0张，金额合计200.0元', page.text)

            logs = client.get('/api/audit-logs').json()['items']
            batch_log = next(item for item in logs if item['action'] == 'bill.batch_generate')
            detail = client.get(f"/backoffice/audit-logs/{batch_log['id']}")
            self.assertEqual(detail.status_code, 200)
            self.assertIn('生成2张，跳过0张，金额合计200.0元', detail.text)


if __name__ == '__main__':
    unittest.main()
