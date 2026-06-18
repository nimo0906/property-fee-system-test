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
        self.service.approve_bill(self.finance, self.project, bill['id'])
        payment = self.service.record_payment(self.finance, bill['id'], 100, 'cash', 'FIN-PAY-1')
        self.assertEqual(payment['amount_paid'], 100.0)

    def test_cashier_can_collect_payment_but_cannot_configure_fee_or_generate_bill(self):
        target = self.service.create_charge_target(self.finance, self.project, '1栋', '1单元', '101', '居民', 80)
        fee = self.service.create_fee_type(self.finance, self.project, '物业费', 2.5)
        bill = self.service.generate_bill(self.finance, self.project, target, fee, '2026-06', '2026-06-01', '2026-06-30')
        self.service.approve_bill(self.finance, self.project, bill['id'])

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

    def test_admin_can_list_and_disable_users_inside_same_tenant(self):
        new_user = self.service.create_staff_user(self.admin, self.project, 'new_cashier', 'cashier')
        users = self.service.list_staff_users(self.admin, self.project)
        self.assertEqual({u['username'] for u in users}, {'admin', 'finance', 'cashier', 'executive', 'new_cashier'})
        disabled = self.service.set_user_active(self.admin, self.project, new_user['id'], False)
        self.assertEqual(disabled['is_active'], 0)
        logs = self.service.list_audit_logs(self.admin, self.project)
        disable_log = next(row for row in logs if row['action'] == 'user.disable')
        self.assertEqual(disable_log['detail']['target_username'], 'new_cashier')
        self.assertEqual(disable_log['detail']['new_is_active'], False)
        with self.assertRaises(PermissionDenied):
            self.service.set_user_active(self.finance, self.project, new_user['id'], True)

    def test_platform_admin_can_manage_users_across_tenants_with_scoped_audit(self):
        other_tenant = self.service.create_tenant('其他物业')
        other_project = self.service.create_project(other_tenant, '其他项目')
        tenant_admin = self.service.create_user(other_tenant, 'other_admin', 'system_admin')
        other_user = self.service.create_staff_user(tenant_admin, other_project, 'other_cashier', 'cashier')
        platform_admin = self.service.create_user(self.tenant, 'platform_admin', 'platform_admin')

        users = self.service.list_staff_users(platform_admin, self.project)
        self.assertIn('other_cashier', {row['username'] for row in users})
        reset = self.service.reset_user_password(platform_admin, other_user['id'], 'platform-temp-pass')
        self.assertEqual(reset['user_id'], other_user['id'])
        logs = self.service.list_audit_logs(tenant_admin, other_project)
        reset_log = next(row for row in logs if row['action'] == 'user.password_reset')
        self.assertEqual(reset_log['detail']['scope'], 'platform')
        self.assertEqual(reset_log['detail']['actor_username'], 'platform_admin')
        self.assertNotIn('platform-temp-pass', str(reset_log))
        disabled = self.service.set_user_active(platform_admin, self.project, other_user['id'], False)
        self.assertEqual(disabled['is_active'], 0)
        logs = self.service.list_audit_logs(tenant_admin, other_project)
        disable_log = next(row for row in logs if row['action'] == 'user.disable')
        self.assertEqual(disable_log['detail']['scope'], 'platform')
        self.assertEqual(disable_log['detail']['actor_username'], 'platform_admin')

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
        users = admin.get('/api/users')
        self.assertEqual(users.status_code, 200)
        self.assertIn('cashier_1', [item['username'] for item in users.json()['items']])
        reset = admin.post(f'/api/users/{user_id}/reset-password', json={'new_password': 'safe-temp-password'})
        self.assertEqual(reset.status_code, 200)
        disabled = admin.post(f'/api/users/{user_id}/active', json={'is_active': False})
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.json()['item']['is_active'], 0)


if __name__ == '__main__':
    unittest.main()
