import unittest

from server.saas_http import create_saas_http_app
from server.passwords import verify_password
from server.saas_service import PermissionDenied, SaasBackofficeService


class TestSaasAuditAndAdmin(unittest.TestCase):
    def test_service_records_audit_logs_for_high_risk_money_and_import_actions(self):
        app = SaasBackofficeService.in_memory()
        tenant = app.create_tenant('审计物业')
        project = app.create_project(tenant, '审计项目')
        finance = app.create_user(tenant, 'finance', 'finance')
        target = app.create_charge_target(finance, project, '住宅楼', '1单元', '101', '居民', 80)
        fee = app.create_fee_type(finance, project, '物业费', 2)
        bill = app.generate_bill(finance, project, target, fee, '2026-06', '2026-06-01', '2026-06-30')
        app.approve_bill(finance, project, bill['id'])
        app.record_payment(finance, bill['id'], 50, 'cash', idempotency_key='AUDIT-PAY-1')
        preview = app.preview_charge_target_import(finance, project, [
            {'building': '住宅楼', 'unit': '1单元', 'room_number': '102', 'category': '居民', 'area': '60'}
        ])
        app.confirm_charge_target_import(finance, project, preview['import_id'])

        logs = app.list_audit_logs(finance, project)
        actions = [row['action'] for row in logs]
        for action in ['charge_target.create', 'fee_type.create', 'bill.generate', 'payment.record', 'import.preview', 'import.confirm']:
            self.assertIn(action, actions)
        payment_log = next(row for row in logs if row['action'] == 'payment.record')
        self.assertEqual(payment_log['detail']['amount_paid'], 50.0)
        self.assertEqual(payment_log['username'], 'finance')

    def test_audit_logs_are_tenant_isolated_and_readonly_visible(self):
        app = SaasBackofficeService.in_memory()
        tenant_a = app.create_tenant('A物业')
        tenant_b = app.create_tenant('B物业')
        project_a = app.create_project(tenant_a, 'A项目')
        project_b = app.create_project(tenant_b, 'B项目')
        finance_a = app.create_user(tenant_a, 'finance_a', 'finance')
        finance_b = app.create_user(tenant_b, 'finance_b', 'finance')
        reader_a = app.create_user(tenant_a, 'reader_a', 'executive')
        app.create_fee_type(finance_a, project_a, 'A费', 1)
        app.create_fee_type(finance_b, project_b, 'B费', 1)
        a_logs = app.list_audit_logs(reader_a, project_a)
        self.assertEqual(len(a_logs), 1)
        self.assertEqual(a_logs[0]['username'], 'finance_a')
        self.assertEqual(app.list_audit_logs(reader_a, project_b), [])

    def test_only_system_admin_can_run_backup_and_reset_password(self):
        app = SaasBackofficeService.in_memory()
        tenant = app.create_tenant('管理物业')
        project = app.create_project(tenant, '管理项目')
        admin = app.create_user(tenant, 'admin', 'system_admin')
        finance = app.create_user(tenant, 'finance', 'finance')
        cashier = app.create_user(tenant, 'cashier', 'cashier')
        with self.assertRaises(PermissionDenied):
            app.create_backup_marker(finance, project)
        with self.assertRaises(PermissionDenied):
            app.reset_user_password(finance, cashier['id'], 'new-pass')
        backup = app.create_backup_marker(admin, project)
        self.assertTrue(backup['backup_id'].startswith('backup-'))
        reset = app.reset_user_password(admin, cashier['id'], 'new-pass')
        self.assertEqual(reset['user_id'], cashier['id'])
        self.assertTrue(verify_password('new-pass', app.users[cashier['id']]['password_hash']))
        self.assertNotIn('new-pass', str(app.list_audit_logs(admin, project)))
        actions = [row['action'] for row in app.list_audit_logs(admin, project)]
        self.assertIn('backup.create', actions)
        self.assertIn('user.password_reset', actions)

    def test_http_audit_and_backup_endpoints_enforce_permissions(self):
        client = create_saas_http_app()
        client.post('/auth/login', json={
            'tenant_name': 'HTTP物业', 'project_name': 'HTTP项目', 'username': 'finance', 'role_code': 'finance'
        })
        client.post('/fee-types', json={'name': '物业费', 'unit_price': 2})
        self.assertEqual(client.get('/audit-logs').status_code, 200)
        self.assertEqual(len(client.get('/audit-logs').json()['items']), 1)
        self.assertEqual(client.post('/backups/create', json={}).status_code, 403)

        admin_client = create_saas_http_app()
        admin_client.post('/auth/login', json={
            'tenant_name': 'HTTP物业2', 'project_name': 'HTTP项目2', 'username': 'admin', 'role_code': 'system_admin'
        })
        backup = admin_client.post('/backups/create', json={})
        self.assertEqual(backup.status_code, 200)
        self.assertTrue(backup.json()['item']['backup_id'].startswith('backup-'))

    def test_http_admin_reset_password_is_audited_without_plaintext(self):
        client = create_saas_http_app()
        client.post('/auth/login', json={
            'tenant_name': 'HTTP重置物业', 'project_name': 'HTTP重置项目', 'username': 'admin', 'role_code': 'system_admin'
        })
        created = client.post('/users', json={'username': 'cashier_http', 'role_code': 'cashier'})
        self.assertEqual(created.status_code, 200)
        user_id = created.json()['item']['id']
        reset = client.post(f'/users/{user_id}/reset-password', json={'new_password': 'http-temp-password'})
        self.assertEqual(reset.status_code, 200)
        logs = client.get('/audit-logs').json()['items']
        reset_log = next(row for row in logs if row['action'] == 'user.password_reset')
        self.assertNotIn('http-temp-password', str(reset_log))
        self.assertEqual(reset_log['detail']['target_username'], 'cashier_http')
        disabled = client.post(f'/users/{user_id}/active', json={'is_active': False})
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.json()['item']['is_active'], 0)
        logs = client.get('/audit-logs').json()['items']
        self.assertIn('user.disable', [row['action'] for row in logs])


if __name__ == '__main__':
    unittest.main()
