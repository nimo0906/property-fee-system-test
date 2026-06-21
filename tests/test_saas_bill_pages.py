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

    def test_bill_page_looks_like_billing_workbench(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            target, fee = self._seed_target_and_fee(client)
            created = client.post('/backoffice/bills/generate', data={
                'target_id': str(target['id']),
                'fee_type_id': str(fee['id']),
                'billing_period': '2026-08',
                'service_start': '2026-08-01',
                'service_end': '2026-08-31',
            }, follow_redirects=False)
            self.assertEqual(created.status_code, 303)

            page = client.get('/backoffice/bills?period=2026-08')

            self.assertEqual(page.status_code, 200)
            for text in [
                '出账工作台',
                '账单总数',
                '待审核',
                '应收',
                '实收',
                '欠费',
                '出账检查',
                '账期',
                '服务期起止',
                '金额核对',
                '重复出账自动跳过',
                '批量出账预览',
                '账单审核',
                '收款登记',
                '账单审核列表',
                '单户生成账单',
                '2026-08',
                '200.0',
                'pending_review',
            ]:
                self.assertIn(text, page.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
                self.assertNotIn(hidden, page.text)


    def test_bill_page_shows_bill_query_and_arrears_tracking_flow(self):
        client = self._client('finance')

        page = client.get('/backoffice/bills')

        self.assertEqual(page.status_code, 200)
        for text in [
            '账单查询流程',
            '生成/预览账单',
            '审核应收账单',
            '查询未收欠费',
            '进入收款登记',
            '核对欠费报表',
            '/backoffice/bills?status=pending_review',
            '/backoffice/bills?status=unpaid',
            '/backoffice/payments',
            '/backoffice/reports',
            '共 0 张账单',
        ]:
            self.assertIn(text, page.text)
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            self.assertNotIn(hidden, page.text)


    def test_bill_approval_page_shows_formal_review_board_and_payment_next_step(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            target, fee = self._seed_target_and_fee(client)
            created = client.post('/backoffice/bills/generate', data={
                'target_id': str(target['id']),
                'fee_type_id': str(fee['id']),
                'billing_period': '2026-09',
                'service_start': '2026-09-01',
                'service_end': '2026-09-30',
            }, follow_redirects=False)
            self.assertEqual(created.status_code, 303)

            page = client.get('/backoffice/bills?period=2026-09')

            self.assertEqual(page.status_code, 200)
            for text in [
                '出账审核看板',
                '待审核账单',
                '审核通过后进入收款登记',
                '服务期',
                '2026-09-01~2026-09-30',
                '待审核',
                '去收款登记',
                '/backoffice/payments',
            ]:
                self.assertIn(text, page.text)
            self.assertNotIn('<td>pending_review</td>', page.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
                self.assertNotIn(hidden, page.text)

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

class TestSaasBillApprovalPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None, tenant_name='账单审核物业', project_name='账单审核项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_bill(self, client):
        target = client.post('/api/charge-targets', json={
            'building': '2栋', 'unit': '2单元', 'room_number': '201', 'category': '居民', 'area': 90,
        })
        self.assertEqual(target.status_code, 200)
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 3.0})
        self.assertEqual(fee.status_code, 200)
        bill = client.post('/api/bills/generate', json={
            'target_id': target.json()['item']['id'],
            'fee_type_id': fee.json()['item']['id'],
            'billing_period': '2026-07',
            'service_start': '2026-07-01',
            'service_end': '2026-07-31',
        })
        self.assertEqual(bill.status_code, 200)
        return bill.json()['item']

    def test_bill_page_shows_approve_action_for_pending_review(self):
        client = self._client('finance')
        self._seed_bill(client)
        page = client.get('/backoffice/bills?status=pending_review')
        self.assertEqual(page.status_code, 200)
        self.assertIn('审核通过', page.text)
        self.assertIn('/backoffice/bills/', page.text)

    def test_finance_can_approve_bill_from_page_and_it_moves_to_unpaid(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            bill = self._seed_bill(client)

            approved = client.post(f"/backoffice/bills/{bill['id']}/approve", follow_redirects=False)
            self.assertEqual(approved.status_code, 303)

            page = client.get('/backoffice/bills?status=unpaid')
            self.assertEqual(page.status_code, 200)
            self.assertIn('unpaid', page.text)
            self.assertNotIn('<td>pending_review</td>', page.text)

            repo = create_saas_repository(db_url)
            stored = repo.list_bills(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'], status='unpaid')
            self.assertEqual([item['status'] for item in stored], ['unpaid'])
            repo.close()

    def test_cashier_cannot_approve_bill_from_page(self):
        client = self._client('finance')
        bill = self._seed_bill(client)
        cashier = self._client('cashier')
        page = cashier.get('/backoffice/bills')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('审核通过', page.text)
        blocked = cashier.post(f"/backoffice/bills/{bill['id']}/approve", follow_redirects=False)
        self.assertEqual(blocked.status_code, 403)

    def test_other_tenant_cannot_see_or_approve_bill(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client('finance', database_url=db_url, tenant_name='A审核物业', project_name='A审核项目')
            bill = self._seed_bill(client_a)

            client_b = self._client('finance', database_url=db_url, tenant_name='B审核物业', project_name='B审核项目')
            page_b = client_b.get('/backoffice/bills')
            self.assertEqual(page_b.status_code, 200)
            self.assertNotIn('2栋', page_b.text)
            self.assertNotIn('201', page_b.text)
            blocked = client_b.post(f"/backoffice/bills/{bill['id']}/approve", follow_redirects=False)
            self.assertEqual(blocked.status_code, 403)
