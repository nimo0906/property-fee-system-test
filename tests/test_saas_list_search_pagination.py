import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository
from server.saas_service import SaasBackofficeService


class TestSaasListSearchPagination(unittest.TestCase):
    def setUp(self):
        self.service = SaasBackofficeService.in_memory()
        self.tenant = self.service.create_tenant('搜索物业')
        self.project = self.service.create_project(self.tenant, '搜索项目')
        self.finance = self.service.create_user(self.tenant, 'finance', 'finance')
        self.fee = self.service.create_fee_type(self.finance, self.project, '物业费', 2)
        self.bills = []
        for room in ['101', '102', '商铺A']:
            target = self.service.create_charge_target(self.finance, self.project, '1栋', '1单元', room, '居民', 50)
            bill = self.service.generate_bill(self.finance, self.project, target, self.fee, '2026-06', '2026-06-01', '2026-06-30')
            self.service.approve_bill(self.finance, self.project, bill['id'])
            self.bills.append(bill)
        self.payment = self.service.record_payment(self.finance, self.bills[0]['id'], 20, 'cash', 'SEARCH-PAY-1')

    def test_bill_search_by_room_number_and_pagination(self):
        result = self.service.search_bills(self.finance, self.project, keyword='商铺', page=1, page_size=10)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['room_number'], '商铺A')
        paged = self.service.search_bills(self.finance, self.project, period='2026-06', page=2, page_size=2)
        self.assertEqual(paged['total'], 3)
        self.assertEqual(paged['page'], 2)
        self.assertEqual(len(paged['items']), 1)

    def test_payment_search_by_receipt_number_and_pagination(self):
        result = self.service.search_payments(self.finance, self.project, keyword=self.payment['receipt_number'], page=1, page_size=10)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['receipt_number'], self.payment['receipt_number'])
        self.assertEqual(result['items'][0]['bill_number'], self.bills[0]['bill_number'])

    def test_search_is_tenant_isolated(self):
        other_tenant = self.service.create_tenant('其他物业')
        other_project = self.service.create_project(other_tenant, '其他项目')
        other_user = self.service.create_user(other_tenant, 'finance_b', 'finance')
        self.assertEqual(self.service.search_bills(other_user, other_project, keyword='101')['items'], [])
        self.assertEqual(self.service.search_payments(other_user, other_project, keyword=self.payment['receipt_number'])['items'], [])


class TestSaasFastApiListSearchPagination(unittest.TestCase):
    def test_api_bills_and_payments_search_pagination(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': 'API搜索物业', 'project_name': 'API搜索项目', 'username': 'finance', 'role_code': 'finance'
        })
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
        bills = []
        for room in ['101', '102', '商铺A']:
            target = client.post('/api/charge-targets', json={
                'building': '1栋', 'unit': '1单元', 'room_number': room, 'category': '居民', 'area': 50
            }).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-06',
                'service_start': '2026-06-01', 'service_end': '2026-06-30'
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            bills.append(bill)
        payment = client.post('/api/payments', json={'bill_id': bills[0]['id'], 'amount': 20, 'method': 'cash', 'idempotency_key': 'API-SEARCH-PAY'}).json()['item']
        bill_search = client.get('/api/bills/search?keyword=商铺&page=1&page_size=10')
        payment_search = client.get(f"/api/payments?keyword={payment['receipt_number']}&page=1&page_size=10")
        self.assertEqual(bill_search.status_code, 200)
        self.assertEqual(bill_search.json()['total'], 1)
        self.assertEqual(bill_search.json()['items'][0]['room_number'], '商铺A')
        self.assertEqual(payment_search.status_code, 200)
        self.assertEqual(payment_search.json()['items'][0]['receipt_number'], payment['receipt_number'])


class TestSaasRepositoryListSearchPagination(unittest.TestCase):
    def test_repository_bill_and_payment_search(self):
        with tempfile.TemporaryDirectory() as td:
            repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            tenant = repo.create_tenant('持久搜索物业')
            project = repo.create_project(tenant['id'], '持久搜索项目')
            fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2)
            target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '商铺A', '商户', 50)
            bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2026-06', '2026-06-01', '2026-06-30', 100)
            repo.approve_bill(tenant['id'], project['id'], bill['id'])
            payment = repo.create_payment(tenant['id'], project['id'], bill['id'], 20, 'cash', 'REPO-SEARCH-PAY')
            bills = repo.search_bills(tenant['id'], project['id'], keyword='商铺', page=1, page_size=10)
            payments = repo.search_payments(tenant['id'], project['id'], keyword=payment['receipt_number'], page=1, page_size=10)
            self.assertEqual(bills['total'], 1)
            self.assertEqual(bills['items'][0]['room_number'], '商铺A')
            self.assertEqual(payments['items'][0]['receipt_number'], payment['receipt_number'])
            repo.close()


if __name__ == '__main__':
    unittest.main()
