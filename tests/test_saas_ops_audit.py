import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_service import PermissionDenied, SaasBackofficeService


class TestSaasOpsAudit(unittest.TestCase):
    def setUp(self):
        self.service = SaasBackofficeService.in_memory()
        self.tenant = self.service.create_tenant('运维物业')
        self.project = self.service.create_project(self.tenant, '运维项目')
        self.admin = self.service.create_user(self.tenant, 'admin', 'system_admin')
        self.finance = self.service.create_user(self.tenant, 'finance', 'finance')

    def test_backup_record_is_created_and_queryable_without_cross_tenant_leak(self):
        backup = self.service.create_backup_marker(self.admin, self.project)
        records = self.service.list_backup_records(self.admin, self.project)
        self.assertEqual(records[0]['backup_id'], backup['backup_id'])
        self.assertEqual(records[0]['tenant_id'], self.tenant)
        self.assertEqual(records[0]['project_id'], self.project)
        self.assertEqual(records[0]['status'], 'created')
        self.assertIn('created_at', records[0])
        other_tenant = self.service.create_tenant('其他物业')
        other_project = self.service.create_project(other_tenant, '其他项目')
        other_admin = self.service.create_user(other_tenant, 'other_admin', 'system_admin')
        self.assertEqual(self.service.list_backup_records(other_admin, other_project), [])

    def test_restore_drill_requires_admin_and_is_audited(self):
        with self.assertRaises(PermissionDenied):
            self.service.record_restore_drill(self.finance, self.project, 'backup-000001', 'database')
        drill = self.service.record_restore_drill(self.admin, self.project, 'backup-000001', 'database')
        self.assertEqual(drill['scope'], 'database')
        logs = self.service.list_audit_logs(self.admin, self.project)
        restore_log = next(row for row in logs if row['action'] == 'restore.drill')
        self.assertEqual(restore_log['detail']['backup_id'], 'backup-000001')
        self.assertEqual(restore_log['detail']['scope'], 'database')

    def test_password_reset_audit_masks_secret(self):
        cashier = self.service.create_staff_user(self.admin, self.project, 'cashier', 'cashier')
        self.service.reset_user_password(self.admin, cashier['id'], 'super-secret-password')
        reset_log = next(row for row in self.service.list_audit_logs(self.admin, self.project) if row['action'] == 'user.password_reset')
        self.assertNotIn('super-secret-password', str(reset_log))
        self.assertEqual(reset_log['detail']['target_user_id'], cashier['id'])
        self.assertEqual(reset_log['detail']['target_username'], 'cashier')
        self.assertEqual(reset_log['detail']['target_role_code'], 'cashier')
        self.assertEqual(reset_log['detail']['password_changed'], True)


class TestSaasFastApiOpsAudit(unittest.TestCase):
    def test_admin_can_create_and_list_backup_records_and_restore_drills(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': 'API运维物业', 'project_name': 'API运维项目', 'username': 'admin', 'role_code': 'system_admin'
        })
        backup = client.post('/api/backups/create', json={})
        self.assertEqual(backup.status_code, 200)
        records = client.get('/api/backups')
        self.assertEqual(records.status_code, 200)
        self.assertEqual(records.json()['items'][0]['backup_id'], backup.json()['item']['backup_id'])
        drill = client.post('/api/restore-drills', json={
            'backup_id': backup.json()['item']['backup_id'],
            'scope': 'database',
        })
        self.assertEqual(drill.status_code, 200)
        audit = client.get('/api/audit-logs')
        actions = [row['action'] for row in audit.json()['items']]
        self.assertIn('backup.create', actions)
        self.assertIn('restore.drill', actions)

    def test_non_admin_cannot_access_ops_endpoints(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': 'API财务物业', 'project_name': 'API财务项目', 'username': 'finance', 'role_code': 'finance'
        })
        self.assertEqual(client.get('/api/backups').status_code, 403)
        self.assertEqual(client.post('/api/restore-drills', json={'backup_id': 'backup-1', 'scope': 'database'}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
