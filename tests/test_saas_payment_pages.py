import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasPaymentPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None, tenant_name='收款物业', project_name='收款项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_unpaid_bill(self, client):
        target = client.post('/api/charge-targets', json={
            'building': '3栋', 'unit': '3单元', 'room_number': '301', 'category': '居民', 'area': 100,
        })
        self.assertEqual(target.status_code, 200)
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.0})
        self.assertEqual(fee.status_code, 200)
        bill = client.post('/api/bills/generate', json={
            'target_id': target.json()['item']['id'],
            'fee_type_id': fee.json()['item']['id'],
            'billing_period': '2026-08',
            'service_start': '2026-08-01',
            'service_end': '2026-08-31',
        })
        self.assertEqual(bill.status_code, 200)
        approved = client.post(f"/api/bills/{bill.json()['item']['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200)
        return approved.json()['item']

    def test_backoffice_home_links_payment_page(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/payments', page.text)

    def test_cashier_can_record_payment_from_page_and_list_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            finance = self._client('finance', database_url=db_url)
            bill = self._seed_unpaid_bill(finance)
            cashier = self._client('cashier', database_url=db_url, tenant_name='收款物业', project_name='收款项目')

            page = cashier.get('/backoffice/payments')
            self.assertEqual(page.status_code, 200)
            self.assertIn('收款登记', page.text)
            self.assertIn(bill['bill_number'], page.text)
            self.assertIn('登记收款', page.text)

            paid = cashier.post('/backoffice/payments/create', data={
                'bill_id': str(bill['id']),
                'amount': '50',
                'method': 'cash',
                'idempotency_key': 'PAGE-PAY-1',
            }, follow_redirects=False)
            self.assertEqual(paid.status_code, 303)

            page = cashier.get('/backoffice/payments')
            self.assertEqual(page.status_code, 200)
            self.assertIn('RCPT-', page.text)
            self.assertIn('50.0', page.text)
            self.assertIn('partial', page.text)

            repo = create_saas_repository(db_url)
            bills = repo.list_bills(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            self.assertEqual(bills[0]['status'], 'partial')
            payments = repo.search_payments(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            self.assertEqual(payments['total'], 1)
            repo.close()

    def test_payment_page_looks_like_payment_workbench(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            finance = self._client('finance', database_url=db_url)
            bill = self._seed_unpaid_bill(finance)
            paid = finance.post('/backoffice/payments/create', data={
                'bill_id': str(bill['id']),
                'amount': '50',
                'method': 'cash',
                'idempotency_key': 'WORKBENCH-PAY-1',
            }, follow_redirects=False)
            self.assertEqual(paid.status_code, 303)

            page = finance.get('/backoffice/payments')

            self.assertEqual(page.status_code, 200)
            for text in [
                '收款工作台',
                '收款笔数',
                '本页收款',
                '收后累计已收',
                '收后欠费',
                '部分收款',
                '欠费联动',
                '收据号',
                '收据打印',
                '导出收据',
                '幂等防重复',
                '收款流水',
                '登记收款',
                'RCPT-',
                '50.0',
                '150.0',
                'cash',
            ]:
                self.assertIn(text, page.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
                self.assertNotIn(hidden, page.text)


    def test_payment_page_shows_cashier_workflow_links(self):
        client = self._client('finance')

        page = client.get('/backoffice/payments')

        self.assertEqual(page.status_code, 200)
        for text in [
            '收款办理流程',
            '选择未收账单',
            '登记本次收款',
            '打印/导出收据',
            '核对欠费报表',
            '/backoffice/bills?status=unpaid',
            '/backoffice/reports',
            '/api/exports/payments',
            '共 0 条',
        ]:
            self.assertIn(text, page.text)
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            self.assertNotIn(hidden, page.text)

    def test_executive_can_view_but_cannot_record_payment(self):
        client = self._client('executive')
        page = client.get('/backoffice/payments')
        self.assertEqual(page.status_code, 200)
        self.assertIn('当前角色只能查看收款', page.text)
        blocked = client.post('/backoffice/payments/create', data={
            'bill_id': '1', 'amount': '1', 'method': 'cash', 'idempotency_key': 'EXEC-PAY'
        }, follow_redirects=False)
        self.assertEqual(blocked.status_code, 403)

    def test_payment_page_is_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client('finance', database_url=db_url, tenant_name='A收款物业', project_name='A收款项目')
            bill = self._seed_unpaid_bill(client_a)
            paid = client_a.post('/backoffice/payments/create', data={
                'bill_id': str(bill['id']), 'amount': '200', 'method': 'cash', 'idempotency_key': 'A-PAY-1'
            }, follow_redirects=False)
            self.assertEqual(paid.status_code, 303)

            client_b = self._client('finance', database_url=db_url, tenant_name='B收款物业', project_name='B收款项目')
            page_b = client_b.get('/backoffice/payments')
            self.assertEqual(page_b.status_code, 200)
            self.assertNotIn(bill['bill_number'], page_b.text)
            self.assertNotIn('A-PAY-1', page_b.text)
            blocked = client_b.post('/backoffice/payments/create', data={
                'bill_id': str(bill['id']), 'amount': '1', 'method': 'cash', 'idempotency_key': 'B-BAD-PAY'
            }, follow_redirects=False)
            self.assertEqual(blocked.status_code, 403)


if __name__ == '__main__':
    unittest.main()
