import tempfile
import unittest
from pathlib import Path

from server.saas_repository import create_saas_repository


class TestSaasRepositoryOpsAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = create_saas_repository(f"sqlite:///{Path(self.tmp.name) / 'saas.sqlite3'}")
        self.tenant = self.repo.create_tenant('持久化运维物业')
        self.project = self.repo.create_project(self.tenant['id'], '持久化运维项目')
        self.admin = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'admin', 'system_admin')

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_backup_record_and_restore_drill_are_persistent_and_audited(self):
        backup = self.repo.create_backup_record(self.tenant['id'], self.project['id'], self.admin['id'])
        records = self.repo.list_backup_records(self.tenant['id'], self.project['id'])
        self.assertEqual(records[0]['backup_id'], backup['backup_id'])
        drill = self.repo.create_restore_drill(self.tenant['id'], self.project['id'], self.admin['id'], backup['backup_id'], 'database')
        self.assertEqual(drill['scope'], 'database')
        logs = self.repo.list_audit_logs(self.tenant['id'], self.project['id'])
        actions = [row['action'] for row in logs]
        self.assertIn('backup.create', actions)
        self.assertIn('restore.drill', actions)

    def test_password_reset_is_audited_without_secret(self):
        cashier = self.repo.create_staff_user(self.tenant['id'], self.project['id'], 'cashier', 'cashier')
        self.repo.reset_user_password(self.tenant['id'], cashier['id'], 'secret-password', actor_user_id=self.admin['id'], project_id=self.project['id'])
        logs = self.repo.list_audit_logs(self.tenant['id'], self.project['id'])
        reset = next(row for row in logs if row['action'] == 'user.password_reset')
        self.assertEqual(reset['detail']['target_user_id'], cashier['id'])
        self.assertNotIn('secret-password', str(reset))
        self.assertEqual(reset['detail']['target_username'], 'cashier')
        self.assertEqual(reset['detail']['target_role_code'], 'cashier')
        self.assertEqual(reset['detail']['password_changed'], True)


if __name__ == '__main__':
    unittest.main()

class TestSaasFastApiPersistentOpsAudit(unittest.TestCase):
    def test_ops_records_are_persisted_in_repository_mode(self):
        from fastapi.testclient import TestClient
        from server.saas_app import create_app

        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            client.post('/api/auth/login', json={
                'tenant_name': '持久API物业', 'project_name': '持久API项目', 'username': 'admin', 'role_code': 'system_admin'
            })
            backup = client.post('/api/backups/create', json={})
            self.assertEqual(backup.status_code, 200)
            drill = client.post('/api/restore-drills', json={'backup_id': backup.json()['item']['backup_id'], 'scope': 'database'})
            self.assertEqual(drill.status_code, 200)

            reopened = create_saas_repository(db_url)
            tenants = reopened.list_tenants()
            projects = reopened.list_projects()
            records = reopened.list_backup_records(tenants[0]['id'], projects[0]['id'])
            logs = reopened.list_audit_logs(tenants[0]['id'], projects[0]['id'])
            self.assertEqual(records[0]['backup_id'], backup.json()['item']['backup_id'])
            self.assertIn('restore.drill', [row['action'] for row in logs])
            reopened.close()

    def test_persistent_api_business_and_import_actions_are_persisted_to_audit_log(self):
        from fastapi.testclient import TestClient
        from server.saas_app import create_app

        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            self.assertEqual(client.post('/api/auth/login', json={
                'tenant_name': '持久审计物业', 'project_name': '持久审计项目',
                'username': 'finance', 'role_code': 'finance',
            }).status_code, 200)
            client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2})
            preview = client.post('/api/imports/charge-targets/preview', json={'rows': [{
                'building': '1栋', 'unit': '1单元', 'room_number': '101',
                'category': '居民', 'area': '80',
            }]})
            self.assertEqual(preview.status_code, 200)
            confirmed = client.post('/api/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']})
            self.assertEqual(confirmed.status_code, 200)

            reopened = create_saas_repository(db_url)
            tenant = reopened.list_tenants()[0]
            project = reopened.list_projects()[0]
            actions = [row['action'] for row in reopened.list_audit_logs(tenant['id'], project['id'])]
            self.assertIn('fee_type.create', actions)
            self.assertIn('import.preview', actions)
            self.assertIn('import.confirm', actions)
            reopened.close()

class TestSaasOpsAuditSchema(unittest.TestCase):
    def test_schema_defines_backup_records_and_restore_drills_with_tenant_scope(self):
        from server.saas_schema import build_saas_postgres_schema

        schema = build_saas_postgres_schema()
        for table in ['backup_records', 'restore_drills']:
            self.assertIn(f'CREATE TABLE IF NOT EXISTS {table}', schema)
            block = schema.split(f'CREATE TABLE IF NOT EXISTS {table}', 1)[1].split(');', 1)[0]
            self.assertIn('tenant_id BIGINT NOT NULL REFERENCES tenants(id)', block)
            self.assertIn('project_id BIGINT NOT NULL REFERENCES projects(id)', block)
            self.assertIn('FOREIGN KEY(project_id, tenant_id) REFERENCES projects(id, tenant_id)', block)
