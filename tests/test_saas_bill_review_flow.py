import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_service import PermissionDenied, SaasBackofficeService


class TestSaasBillReviewFlow(unittest.TestCase):
    def setUp(self):
        self.service = SaasBackofficeService.in_memory()
        self.tenant = self.service.create_tenant('账单物业')
        self.project = self.service.create_project(self.tenant, '账单项目')
        self.finance = self.service.create_user(self.tenant, 'finance', 'finance')
        self.cashier = self.service.create_user(self.tenant, 'cashier', 'cashier')
        self.executive = self.service.create_user(self.tenant, 'executive', 'executive')
        self.target = self.service.create_charge_target(self.finance, self.project, '1栋', '1单元', '101', '居民', 80)
        self.fee = self.service.create_fee_type(self.finance, self.project, '物业费', 2.5)

    def test_generated_bill_waits_review_before_payment(self):
        bill = self.service.generate_bill(self.finance, self.project, self.target, self.fee, '2026-06', '2026-06-01', '2026-06-30')
        self.assertEqual(bill['status'], 'pending_review')
        with self.assertRaises(PermissionDenied):
            self.service.record_payment(self.cashier, bill['id'], 50, 'cash', 'PAY-BEFORE-REVIEW')
        approved = self.service.approve_bill(self.finance, self.project, bill['id'])
        self.assertEqual(approved['status'], 'unpaid')
        payment = self.service.record_payment(self.cashier, bill['id'], 50, 'cash', 'PAY-AFTER-REVIEW')
        self.assertEqual(payment['amount_paid'], 50.0)

    def test_bill_list_filters_by_period_and_status_inside_project(self):
        june = self.service.generate_bill(self.finance, self.project, self.target, self.fee, '2026-06', '2026-06-01', '2026-06-30')
        july = self.service.generate_bill(self.finance, self.project, self.target, self.fee, '2026-07', '2026-07-01', '2026-07-31')
        self.service.approve_bill(self.finance, self.project, june['id'])
        pending = self.service.list_bills(self.finance, self.project, status='pending_review')
        approved_june = self.service.list_bills(self.executive, self.project, period='2026-06', status='unpaid')
        self.assertEqual([b['id'] for b in pending], [july['id']])
        self.assertEqual([b['id'] for b in approved_june], [june['id']])

    def test_other_tenant_cannot_approve_or_list_bill(self):
        bill = self.service.generate_bill(self.finance, self.project, self.target, self.fee, '2026-06', '2026-06-01', '2026-06-30')
        tenant_b = self.service.create_tenant('B物业')
        project_b = self.service.create_project(tenant_b, 'B项目')
        finance_b = self.service.create_user(tenant_b, 'finance_b', 'finance')
        self.assertEqual(self.service.list_bills(finance_b, project_b), [])
        with self.assertRaises(PermissionDenied):
            self.service.approve_bill(finance_b, project_b, bill['id'])


class TestSaasFastApiBillReviewFlow(unittest.TestCase):
    def test_api_bill_review_list_and_payment_flow(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': 'API账单物业', 'project_name': 'API账单项目', 'username': 'finance', 'role_code': 'finance'
        })
        target = client.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-06',
            'service_start': '2026-06-01', 'service_end': '2026-06-30'
        })
        self.assertEqual(bill.status_code, 200)
        self.assertEqual(bill.json()['item']['status'], 'pending_review')
        bills = client.get('/api/bills?period=2026-06&status=pending_review')
        self.assertEqual(bills.status_code, 200)
        self.assertEqual(len(bills.json()['items']), 1)
        blocked = client.post('/api/payments', json={'bill_id': bill.json()['item']['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'PAY-1'})
        self.assertEqual(blocked.status_code, 403)
        approved = client.post(f"/api/bills/{bill.json()['item']['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200)
        paid = client.post('/api/payments', json={'bill_id': bill.json()['item']['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'PAY-1'})
        self.assertEqual(paid.status_code, 200)


if __name__ == '__main__':
    unittest.main()
