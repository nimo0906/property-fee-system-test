import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasBillPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None, tenant_name='账单物业', project_name='账单项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_target_and_fee(self, client):
        target = client.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80,
        })
        self.assertEqual(target.status_code, 200)
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5})
        self.assertEqual(fee.status_code, 200)
        return target.json()['item'], fee.json()['item']

    def test_backoffice_home_links_bill_page(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('出账收款', page.text)
        self.assertIn('/backoffice/bills', page.text)

    def test_finance_can_generate_and_list_bill_persistently(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            target, fee = self._seed_target_and_fee(client)
            created = client.post('/backoffice/bills/generate', data={
                'target_id': str(target['id']),
                'fee_type_id': str(fee['id']),
                'billing_period': '2026-06',
                'service_start': '2026-06-01',
                'service_end': '2026-06-30',
            }, follow_redirects=False)
            self.assertEqual(created.status_code, 303)

            page = client.get('/backoffice/bills?period=2026-06')
            self.assertEqual(page.status_code, 200)
            self.assertIn('账单生成', page.text)
            self.assertIn('2026-06', page.text)
            self.assertIn('200.0', page.text)
            self.assertIn('pending_review', page.text)
            self.assertIn('1栋', page.text)
            self.assertIn('101', page.text)
            self.assertIn('物业费', page.text)

            repo = create_saas_repository(db_url)
            bills = repo.list_bills(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            self.assertEqual(len(bills), 1)
            self.assertEqual(bills[0]['amount'], 200.0)
            repo.close()

    def test_cashier_can_view_but_cannot_generate_bill(self):
        client = self._client('cashier')
        page = client.get('/backoffice/bills')
        self.assertEqual(page.status_code, 200)
        self.assertIn('当前角色只能查看账单', page.text)
        created = client.post('/backoffice/bills/generate', data={
            'target_id': '1',
            'fee_type_id': '1',
            'billing_period': '2026-06',
            'service_start': '2026-06-01',
            'service_end': '2026-06-30',
        })
        self.assertEqual(created.status_code, 403)

    def test_bill_page_is_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client('finance', database_url=db_url, tenant_name='A物业', project_name='A项目')
            target, fee = self._seed_target_and_fee(client_a)
            response = client_a.post('/backoffice/bills/generate', data={
                'target_id': str(target['id']),
                'fee_type_id': str(fee['id']),
                'billing_period': '2026-06',
                'service_start': '2026-06-01',
                'service_end': '2026-06-30',
            }, follow_redirects=False)
            self.assertEqual(response.status_code, 303)

            client_b = self._client('finance', database_url=db_url, tenant_name='B物业', project_name='B项目')
            page_b = client_b.get('/backoffice/bills')
            self.assertEqual(page_b.status_code, 200)
            self.assertNotIn('BILL-', page_b.text)
            self.assertNotIn('1栋', page_b.text)
            self.assertNotIn('101', page_b.text)


if __name__ == '__main__':
    unittest.main()
