import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_service import PermissionDenied, SaasBackofficeService


class TestSaasPermissionMatrix(unittest.TestCase):
    def setUp(self):
        self.service = SaasBackofficeService.in_memory()
        self.tenant = self.service.create_tenant('权限物业')
        self.project = self.service.create_project(self.tenant, '权限项目')
        self.admin = self.service.create_user(self.tenant, 'admin', 'system_admin')
        self.finance = self.service.create_user(self.tenant, 'finance', 'finance')
        self.cashier = self.service.create_user(self.tenant, 'cashier', 'cashier')
        self.executive = self.service.create_user(self.tenant, 'executive', 'executive')

    def test_finance_can_configure_fee_and_generate_bill_and_collect_payment(self):
        target = self.service.create_charge_target(self.finance, self.project, '1栋', '1单元', '101', '居民', 80)
        fee = self.service.create_fee_type(self.finance, self.project, '物业费', 2.5)
        bill = self.service.generate_bill(self.finance, self.project, target, fee, '2026-06', '2026-06-01', '2026-06-30')
        payment = self.service.record_payment(self.finance, bill['id'], 100, 'cash', 'FIN-PAY-1')
        self.assertEqual(payment['amount_paid'], 100.0)

    def test_cashier_can_collect_payment_but_cannot_configure_fee_or_generate_bill(self):
        target = self.service.create_charge_target(self.finance, self.project, '1栋', '1单元', '101', '居民', 80)
        fee = self.service.create_fee_type(self.finance, self.project, '物业费', 2.5)
        bill = self.service.generate_bill(self.finance, self.project, target, fee, '2026-06', '2026-06-01', '2026-06-30')

        payment = self.service.record_payment(self.cashier, bill['id'], 100, 'cash', 'CASH-PAY-1')
        self.assertEqual(payment['amount_paid'], 100.0)
        with self.assertRaises(PermissionDenied):
            self.service.create_fee_type(self.cashier, self.project, '停车费', 100)
        with self.assertRaises(PermissionDenied):
            self.service.generate_bill(self.cashier, self.project, target, fee, '2026-07', '2026-07-01', '2026-07-31')

    def test_executive_is_read_only(self):
        self.assertEqual(self.service.list_charge_targets(self.executive, self.project), [])
        self.service.report(self.executive, self.project, '2026-06')
        with self.assertRaises(PermissionDenied):
            self.service.create_charge_target(self.executive, self.project, '1栋', '1单元', '102', '居民', 80)
        with self.assertRaises(PermissionDenied):
            self.service.record_payment(self.executive, 1, 1, 'cash', 'EXEC-PAY-1')

    def test_only_admin_can_manage_users_inside_same_tenant(self):
        new_user = self.service.create_staff_user(self.admin, self.project, 'new_finance', 'finance')
        self.assertEqual(new_user['tenant_id'], self.tenant)
        self.assertEqual(new_user['project_id'], self.project)
        with self.assertRaises(PermissionDenied):
            self.service.create_staff_user(self.finance, self.project, 'bad_user', 'cashier')
        with self.assertRaises(PermissionDenied):
            self.service.reset_user_password(self.cashier, new_user['id'], 'new-password')

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_staff_user(self.admin, self.project, 'ghost', 'owner')


class TestSaasFastApiPermissionMatrix(unittest.TestCase):
    def _client(self, role_code):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': f'{role_code}物业',
            'project_name': f'{role_code}项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_api_cashier_cannot_create_fee_type(self):
        client = self._client('cashier')
        response = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5})
        self.assertEqual(response.status_code, 403)

    def test_api_executive_cannot_post_business_changes(self):
        client = self._client('executive')
        target = client.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        })
        payment = client.post('/api/payments', json={'bill_id': 1, 'amount': 1, 'method': 'cash'})
        self.assertEqual(target.status_code, 403)
        self.assertEqual(payment.status_code, 403)

    def test_api_only_admin_can_create_and_reset_staff_users(self):
        finance = self._client('finance')
        forbidden = finance.post('/api/users', json={'username': 'u1', 'role_code': 'cashier'})
        self.assertEqual(forbidden.status_code, 403)

        admin = self._client('system_admin')
        created = admin.post('/api/users', json={'username': 'cashier_1', 'role_code': 'cashier'})
        self.assertEqual(created.status_code, 200)
        user_id = created.json()['item']['id']
        reset = admin.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'safe-temp-password'})
        self.assertEqual(reset.status_code, 200)


if __name__ == '__main__':
    unittest.main()
