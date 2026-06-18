import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasTenantStatusPages(unittest.TestCase):
    def _client(self, db_url, tenant='平台物业', project='平台项目', username='platform', role_code='platform_admin', password=''):
        client = TestClient(create_app(database_url=db_url))
        payload = {
            'tenant_name': tenant,
            'project_name': project,
            'username': username,
            'role_code': role_code,
        }
        if password:
            payload['password'] = password
        response = client.post('/api/auth/login', json=payload)
        self.assertEqual(response.status_code, 200)
        return client

    def _onboard_customer(self, platform):
        response = platform.post('/backoffice/tenant-onboarding/create', data={
            'tenant_name': '停用客户物业',
            'project_name': '停用客户项目',
            'admin_username': 'tenant_admin_suspend',
            'admin_password': 'Init-pass-2026',
            'project_code': 'SUSP-001',
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 303)

    def test_platform_admin_can_suspend_and_reactivate_tenant_from_project_page(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            platform = self._client(db_url)
            self._onboard_customer(platform)
            repo = create_saas_repository(db_url)
            tenant = next(row for row in repo.list_tenants() if row['name'] == '停用客户物业')
            project = repo.list_projects(tenant['id'])[0]
            repo.close()

            page = platform.get('/backoffice/tenant-projects')
            self.assertEqual(page.status_code, 200)
            self.assertIn('停用租户', page.text)
            suspended = platform.post('/backoffice/tenant-projects/tenant-status', data={
                'tenant_id': str(tenant['id']),
                'status': 'suspended',
            }, follow_redirects=False)
            self.assertEqual(suspended.status_code, 303)

            blocked_login = TestClient(create_app(database_url=db_url)).post('/api/auth/login', json={
                'tenant_name': '停用客户物业',
                'project_name': '停用客户项目',
                'username': 'tenant_admin_suspend',
                'role_code': 'system_admin',
                'password': 'Init-pass-2026',
            })
            self.assertEqual(blocked_login.status_code, 403)

            repo = create_saas_repository(db_url)
            self.assertEqual(repo.get_tenant(tenant['id'])['status'], 'suspended')
            logs = repo.list_audit_logs(tenant['id'], project['id'])
            self.assertIn('tenant.suspend', [row['action'] for row in logs])
            repo.close()

            activated = platform.post('/backoffice/tenant-projects/tenant-status', data={
                'tenant_id': str(tenant['id']),
                'status': 'active',
            }, follow_redirects=False)
            self.assertEqual(activated.status_code, 303)
            active_login = TestClient(create_app(database_url=db_url)).post('/api/auth/login', json={
                'tenant_name': '停用客户物业',
                'project_name': '停用客户项目',
                'username': 'tenant_admin_suspend',
                'role_code': 'system_admin',
                'password': 'Init-pass-2026',
            })
            self.assertEqual(active_login.status_code, 200)
            self.assertTrue(active_login.json()['must_change_password'])
            repo = create_saas_repository(db_url)
            logs = repo.list_audit_logs(tenant['id'], project['id'])
            self.assertIn('tenant.activate', [row['action'] for row in logs])
            repo.close()


    def test_suspending_tenant_blocks_existing_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            platform = self._client(db_url)
            self._onboard_customer(platform)
            repo = create_saas_repository(db_url)
            tenant = next(row for row in repo.list_tenants() if row['name'] == '停用客户物业')
            repo.close()

            tenant_client = TestClient(create_app(database_url=db_url))
            login = tenant_client.post('/api/auth/login', json={
                'tenant_name': '停用客户物业',
                'project_name': '停用客户项目',
                'username': 'tenant_admin_suspend',
                'role_code': 'system_admin',
                'password': 'Init-pass-2026',
            })
            self.assertEqual(login.status_code, 200)
            changed = tenant_client.post('/api/auth/change-password', json={
                'old_password': 'Init-pass-2026',
                'new_password': 'Changed-pass-2026',
            })
            self.assertEqual(changed.status_code, 200)
            before_suspend = tenant_client.get('/api/charge-targets')
            self.assertEqual(before_suspend.status_code, 200)

            suspended = platform.post('/backoffice/tenant-projects/tenant-status', data={
                'tenant_id': str(tenant['id']),
                'status': 'suspended',
            }, follow_redirects=False)
            self.assertEqual(suspended.status_code, 303)

            blocked = tenant_client.get('/api/charge-targets')
            self.assertEqual(blocked.status_code, 403)
            self.assertIn('tenant inactive', blocked.text)


    def test_platform_admin_can_filter_tenants_by_keyword_and_status(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            platform = self._client(db_url)
            platform.post('/backoffice/tenant-onboarding/create', data={
                'tenant_name': '东区物业',
                'project_name': '东区一期',
                'admin_username': 'east_admin',
                'admin_password': 'Init-pass-2026',
            }, follow_redirects=False)
            platform.post('/backoffice/tenant-onboarding/create', data={
                'tenant_name': '西区物业',
                'project_name': '西区一期',
                'admin_username': 'west_admin',
                'admin_password': 'Init-pass-2026',
            }, follow_redirects=False)
            repo = create_saas_repository(db_url)
            west = next(row for row in repo.list_tenants() if row['name'] == '西区物业')
            repo.close()
            platform.post('/backoffice/tenant-projects/tenant-status', data={
                'tenant_id': str(west['id']),
                'status': 'suspended',
            }, follow_redirects=False)

            keyword = platform.get('/backoffice/tenant-projects?tenant_q=东区')
            self.assertEqual(keyword.status_code, 200)
            self.assertIn('东区物业', keyword.text)
            self.assertIn('东区一期', keyword.text)
            self.assertNotIn('西区物业', keyword.text)
            self.assertIn('tenant_q', keyword.text)

            suspended = platform.get('/backoffice/tenant-projects?tenant_status=suspended')
            self.assertEqual(suspended.status_code, 200)
            self.assertIn('西区物业', suspended.text)
            self.assertIn('西区一期', suspended.text)
            self.assertNotIn('东区物业', suspended.text)
            self.assertIn('tenant_status', suspended.text)

    def test_tenant_admin_cannot_change_tenant_status(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            tenant_admin = self._client(db_url, tenant='客户物业', project='客户项目', username='tenant_admin', role_code='system_admin')
            repo = create_saas_repository(db_url)
            tenant = next(row for row in repo.list_tenants() if row['name'] == '客户物业')
            repo.close()
            blocked = tenant_admin.post('/backoffice/tenant-projects/tenant-status', data={
                'tenant_id': str(tenant['id']),
                'status': 'suspended',
            })
            self.assertEqual(blocked.status_code, 403)


if __name__ == '__main__':
    unittest.main()
