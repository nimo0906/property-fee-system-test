import unittest

from server.saas_service import PermissionDenied, SaasBackofficeService


class TestSaasCrossTenantIsolation(unittest.TestCase):
    def setUp(self):
        self.service = SaasBackofficeService.in_memory()
        self.tenant_a = self.service.create_tenant('A物业')
        self.project_a = self.service.create_project(self.tenant_a, 'A项目')
        self.user_a = self.service.create_user(self.tenant_a, 'finance_a', 'finance')

        self.tenant_b = self.service.create_tenant('B物业')
        self.project_b = self.service.create_project(self.tenant_b, 'B项目')
        self.user_b = self.service.create_user(self.tenant_b, 'finance_b', 'finance')

    def test_cannot_list_other_tenant_charge_targets(self):
        self.service.create_charge_target(self.user_a, self.project_a, '1栋', '1单元', '101', '居民', 80)
        self.assertEqual(self.service.list_charge_targets(self.user_b, self.project_a), [])

    def test_cannot_generate_bill_for_other_tenant_target(self):
        target = self.service.create_charge_target(self.user_a, self.project_a, '1栋', '1单元', '101', '居民', 80)
        fee = self.service.create_fee_type(self.user_b, self.project_b, '物业费', 2.5)
        with self.assertRaises(PermissionDenied):
            self.service.generate_bill(self.user_b, self.project_b, target, fee, '2026-06', '2026-06-01', '2026-06-30')

    def test_cannot_record_payment_for_other_tenant_bill(self):
        target = self.service.create_charge_target(self.user_a, self.project_a, '1栋', '1单元', '101', '居民', 80)
        fee = self.service.create_fee_type(self.user_a, self.project_a, '物业费', 2.5)
        bill = self.service.generate_bill(self.user_a, self.project_a, target, fee, '2026-06', '2026-06-01', '2026-06-30')
        with self.assertRaises(PermissionDenied):
            self.service.record_payment(self.user_b, bill['id'], 100, 'cash', 'KEY-B')

    def test_cannot_read_other_tenant_audit_logs(self):
        self.service._log(self.user_a, self.project_a, 'test.action')
        self.assertEqual(self.service.list_audit_logs(self.user_b, self.project_a), [])


if __name__ == '__main__':
    unittest.main()

class TestSaasFastApiCrossTenantIsolation(unittest.TestCase):
    def _login(self, client, tenant, project, username):
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant,
            'project_name': project,
            'username': username,
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)

    def test_api_rejects_cross_tenant_bill_generation(self):
        from fastapi.testclient import TestClient
        from server.saas_app import create_app

        app = create_app()
        client_a = TestClient(app)
        client_b = TestClient(app)
        self._login(client_a, 'A物业', 'A项目', 'finance_a')
        self._login(client_b, 'B物业', 'B项目', 'finance_b')
        target_a = client_a.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        }).json()['item']
        fee_b = client_b.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5}).json()['item']
        response = client_b.post('/api/bills/generate', json={
            'target_id': target_a['id'],
            'fee_type_id': fee_b['id'],
            'billing_period': '2026-06',
            'service_start': '2026-06-01',
            'service_end': '2026-06-30',
        })
        self.assertEqual(response.status_code, 403)

    def test_api_rejects_cross_tenant_payment(self):
        from fastapi.testclient import TestClient
        from server.saas_app import create_app

        app = create_app()
        client_a = TestClient(app)
        client_b = TestClient(app)
        self._login(client_a, 'A物业', 'A项目', 'finance_a')
        self._login(client_b, 'B物业', 'B项目', 'finance_b')
        target_a = client_a.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        }).json()['item']
        fee_a = client_a.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5}).json()['item']
        bill_a = client_a.post('/api/bills/generate', json={
            'target_id': target_a['id'],
            'fee_type_id': fee_a['id'],
            'billing_period': '2026-06',
            'service_start': '2026-06-01',
            'service_end': '2026-06-30',
        }).json()['item']
        response = client_b.post('/api/payments', json={
            'bill_id': bill_a['id'], 'amount': 100, 'method': 'cash', 'idempotency_key': 'B-PAY-1'
        })
        self.assertEqual(response.status_code, 403)
