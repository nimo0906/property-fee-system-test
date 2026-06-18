import os
import tempfile
import unittest
from pathlib import Path

from server.saas_backoffice import build_saas_postgres_schema, validate_deployment_assets
from server.saas_repository import SaasRepository, create_saas_repository
from server.saas_app import create_app


class TestSaasMigrationAndFastAPI(unittest.TestCase):
    def test_repository_persists_core_tenant_project_and_rbac_data(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / 'saas.sqlite3'
            repo = create_saas_repository(f'sqlite:///{db_path}')
            tenant = repo.create_tenant('持久化物业')
            project = repo.create_project(tenant['id'], '持久化项目')
            role = repo.upsert_role('finance', '财务')
            perm = repo.upsert_permission('billing.generate', '出账')
            repo.grant_permission(role['code'], perm['code'])
            user = repo.create_user(tenant['id'], 'finance', role['code'])
            repo.close()

            reopened = create_saas_repository(f'sqlite:///{db_path}')
            self.assertEqual(reopened.get_tenant(tenant['id'])['name'], '持久化物业')
            self.assertEqual(reopened.get_project(project['id'])['name'], '持久化项目')
            self.assertEqual(reopened.get_user(user['id'])['username'], 'finance')
            self.assertIn('billing.generate', reopened.list_permissions_for_role('finance'))
            reopened.close()

    def test_alembic_baseline_files_and_schema_text_are_present(self):
        root = Path.cwd()
        self.assertTrue((root / 'alembic.ini').exists())
        self.assertTrue((root / 'alembic' / 'env.py').exists())
        self.assertTrue((root / 'alembic' / 'versions' / '0001_saas_baseline.py').exists())
        schema = build_saas_postgres_schema()
        self.assertIn('CREATE TABLE IF NOT EXISTS tenants', schema)
        self.assertIn('CREATE TABLE IF NOT EXISTS audit_logs', schema)
        self.assertTrue(validate_deployment_assets(root)['ok'])

    def test_fastapi_app_exposes_login_me_and_tenant_scoped_routes(self):
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        login = client.post('/api/auth/login', json={
            'tenant_name': '云端物业',
            'project_name': '云端项目',
            'username': 'admin',
            'role_code': 'system_admin',
        })
        self.assertEqual(login.status_code, 200)
        me = client.get('/api/auth/me')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['tenant_name'], '云端物业')
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5})
        self.assertEqual(fee.status_code, 200)
        target = client.post('/api/charge-targets', json={
            'building': '住宅楼', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80
        })
        self.assertEqual(target.status_code, 200)
        preview = client.post('/api/imports/charge-targets/preview', json={
            'rows': [{'building': '住宅楼', 'unit': '1单元', 'room_number': '102', 'category': '居民', 'area': '70'}]
        })
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['valid_count'], 1)


if __name__ == '__main__':
    unittest.main()
