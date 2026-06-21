import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasReportPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None, tenant_name='报表物业', project_name='报表项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_paid_bill(self, client, period='2026-09', payment_amount=50):
        target = client.post('/api/charge-targets', json={
            'building': '4栋', 'unit': '4单元', 'room_number': '401', 'category': '居民', 'area': 100,
        })
        self.assertEqual(target.status_code, 200)
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.0})
        self.assertEqual(fee.status_code, 200)
        bill = client.post('/api/bills/generate', json={
            'target_id': target.json()['item']['id'],
            'fee_type_id': fee.json()['item']['id'],
            'billing_period': period,
            'service_start': f'{period}-01',
            'service_end': f'{period}-30',
        })
        self.assertEqual(bill.status_code, 200)
        approved = client.post(f"/api/bills/{bill.json()['item']['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200)
        payment = client.post('/api/payments', json={
            'bill_id': bill.json()['item']['id'],
            'amount': payment_amount,
            'method': 'cash',
            'idempotency_key': f'REPORT-PAY-{period}',
        })
        self.assertEqual(payment.status_code, 200)
        return bill.json()['item']

    def test_backoffice_home_links_report_page(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/reports', page.text)

    def test_report_page_shows_due_paid_and_unpaid_by_period(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            self._seed_paid_bill(client)

            page = client.get('/backoffice/reports?period=2026-09')
            self.assertEqual(page.status_code, 200)
            self.assertIn('对账报表', page.text)
            self.assertIn('2026-09', page.text)
            self.assertIn('账单数量', page.text)
            self.assertIn('1', page.text)
            self.assertIn('应收金额', page.text)
            self.assertIn('200.0', page.text)
            self.assertIn('实收金额', page.text)
            self.assertIn('50.0', page.text)
            self.assertIn('欠费金额', page.text)
            self.assertIn('150.0', page.text)

    def test_report_page_looks_like_report_workbench(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            self._seed_paid_bill(client, period='2027-05', payment_amount=50)

            page = client.get('/backoffice/reports?period=2027-05')

            self.assertEqual(page.status_code, 200)
            for text in [
                '报表工作台',
                '应收',
                '实收',
                '欠费',
                '收缴率',
                '欠费率',
                '报表检查',
                '按项目汇总',
                '按楼栋 / 区域汇总',
                '按收费项目汇总',
                '欠费明细',
                '导出账单',
                '导出收款流水',
                '导出项目汇总',
                '导出分组汇总',
                '导出欠费明细',
                '2027-05',
                '200.0',
                '50.0',
                '150.0',
            ]:
                self.assertIn(text, page.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
                self.assertNotIn(hidden, page.text)


    def test_report_page_shows_arrears_tracking_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            self._seed_paid_bill(client, period='2027-06', payment_amount=80)

            page = client.get('/backoffice/reports?period=2027-06')

            self.assertEqual(page.status_code, 200)
            for text in [
                '欠费追踪流程',
                '查看欠费明细',
                '定位账单',
                '登记收款',
                '导出催缴清单',
                '复核收缴率',
                '/backoffice/bills?period=2027-06&status=unpaid',
                '/backoffice/payments?period=2027-06',
                '/api/exports/reports/arrears-bills.csv?period=2027-06',
                '欠费账单明细',
                '120.0',
            ]:
                self.assertIn(text, page.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
                self.assertNotIn(hidden, page.text)

    def test_executive_can_view_report_readonly(self):
        client = self._client('executive')
        page = client.get('/backoffice/reports?period=2026-09')
        self.assertEqual(page.status_code, 200)
        self.assertIn('对账报表', page.text)
        self.assertIn('只读', page.text)

    def test_report_page_is_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client('finance', database_url=db_url, tenant_name='A报表物业', project_name='A报表项目')
            self._seed_paid_bill(client_a, payment_amount=200)

            client_b = self._client('finance', database_url=db_url, tenant_name='B报表物业', project_name='B报表项目')
            page_b = client_b.get('/backoffice/reports?period=2026-09')
            self.assertEqual(page_b.status_code, 200)
            self.assertIn('对账报表', page_b.text)
            self.assertIn('0.0', page_b.text)
            self.assertNotIn('200.0</div>', page_b.text)


if __name__ == '__main__':
    unittest.main()
