import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasBackofficePages(unittest.TestCase):
    def _client(self, role_code='system_admin', database_url=None, tenant_name='首页物业', project_name='首页项目', username=None):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': username or role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_is_business_workbench_for_finance(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('物业收费工作台', page.text)
        self.assertIn('首页物业', page.text)
        self.assertIn('首页项目', page.text)
        self.assertIn('当前账号：', page.text)
        self.assertIn('财务', page.text)
        for text in ['收费对象', '收费项目', '批量出账', '账单审核', '收款登记', '欠费查询', '收据打印', '报表导出', '数据导入']:
            self.assertIn(text, page.text)
        for text in ['收费对象数', '收费项目数', '账单数', '应收', '实收', '欠费']:
            self.assertIn(text, page.text)
        self.assertNotIn('SaaS 员工后台', page.text)
        self.assertNotIn('首次使用向导', page.text)
        self.assertNotIn('生产交付总览', page.text)
        self.assertNotIn('客户开通', page.text)
        self.assertNotIn('授权运维', page.text)

    def test_backoffice_home_keeps_admin_system_entries_for_admin(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('物业收费工作台', page.text)
        for text in ['系统管理', '账号管理', '权限矩阵', '审计日志', '备份恢复', '业务配置']:
            self.assertIn(text, page.text)
        self.assertIn('/backoffice/users', page.text)
        self.assertIn('/backoffice/production-delivery', page.text)
        self.assertIn('生产交付总览', page.text)
        self.assertNotIn('客户开通', page.text)
        self.assertNotIn('授权运维', page.text)

    def test_backoffice_home_summary_is_current_tenant_project_only(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client('finance', db_url, tenant_name='A工作台物业', project_name='A项目', username='finance_a')
            target = client_a.post('/api/charge-targets', json={
                'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 100,
            }).json()['item']
            fee = client_a.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
            bill = client_a.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-08',
                'service_start': '2028-08-01', 'service_end': '2028-08-31',
            }).json()['item']
            client_a.post(f"/api/bills/{bill['id']}/approve", json={})
            client_a.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'WORKBENCH-A-1',
            })

            client_b = self._client('finance', db_url, tenant_name='B工作台物业', project_name='B项目', username='finance_b')
            other_target = client_b.post('/api/charge-targets', json={
                'building': '9栋', 'unit': '9单元', 'room_number': '901', 'category': '居民', 'area': 999,
            }).json()['item']
            other_fee = client_b.post('/api/fee-types', json={'name': '其他物业费', 'unit_price': 1, 'billing_mode': 'area'}).json()['item']
            other_bill = client_b.post('/api/bills/generate', json={
                'target_id': other_target['id'], 'fee_type_id': other_fee['id'], 'billing_period': '2028-08',
                'service_start': '2028-08-01', 'service_end': '2028-08-31',
            }).json()['item']
            client_b.post(f"/api/bills/{other_bill['id']}/approve", json={})

            page = client_a.get('/backoffice?period=2028-08')

            self.assertEqual(page.status_code, 200)
            for text in ['收费对象数</div><strong>1</strong>', '收费项目数</div><strong>1</strong>', '账单数</div><strong>1</strong>', '应收</div><strong>200.0</strong>', '实收</div><strong>50.0</strong>', '欠费</div><strong>150.0</strong>']:
                self.assertIn(text, page.text)
            for hidden in ['B工作台物业', 'B项目', '999.0', 'tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
                self.assertNotIn(hidden, page.text)

    def test_backoffice_home_requires_login(self):
        client = TestClient(create_app())
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 401)


if __name__ == '__main__':
    unittest.main()
