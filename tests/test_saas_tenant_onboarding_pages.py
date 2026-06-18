import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.passwords import verify_password
from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasTenantOnboardingPages(unittest.TestCase):
    def _client(self, db_url, role_code='platform_admin', tenant='平台物业', project='平台项目', username='platform'):
        client = TestClient(create_app(database_url=db_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant,
            'project_name': project,
            'username': username,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_tenant_onboarding_for_platform_admin(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url)
            page = client.get('/backoffice')
            self.assertEqual(page.status_code, 200)
            self.assertIn('客户开通', page.text)
            self.assertIn('/backoffice/tenant-onboarding', page.text)

    def test_tenant_onboarding_page_creates_tenant_project_and_admin_account(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url)
            page = client.get('/backoffice/tenant-onboarding')
            self.assertEqual(page.status_code, 200)
            self.assertIn('平台客户开通', page.text)
            self.assertIn('租户管理员账号', page.text)

            created = client.post('/backoffice/tenant-onboarding/create', data={
                'tenant_name': '金桥物业',
                'project_name': '金桥一期',
                'admin_username': 'tenant_admin_jq',
                'admin_password': 'Init-pass-2026',
                'project_code': 'JQ-001',
            }, follow_redirects=False)
            self.assertEqual(created.status_code, 303)

            repo = create_saas_repository(db_url)
            tenants = repo.list_tenants()
            self.assertIn('金桥物业', [row['name'] for row in tenants])
            tenant = next(row for row in tenants if row['name'] == '金桥物业')
            projects = [row for row in repo.list_projects(tenant['id'])]
            self.assertEqual([row['name'] for row in projects], ['金桥一期'])
            admin_row = next(row for row in repo.list_users(tenant['id']) if row['username'] == 'tenant_admin_jq')
            admin = repo.get_user(admin_row['id'])
            self.assertTrue(verify_password('Init-pass-2026', admin['password_hash']))
            logs = repo.list_audit_logs(tenant['id'], projects[0]['id'])
            self.assertIn('tenant.create', [row['action'] for row in logs])
            self.assertIn('project.create', [row['action'] for row in logs])
            self.assertIn('user.create', [row['action'] for row in logs])
            self.assertIn('user.password_reset', [row['action'] for row in logs])
            self.assertNotIn('Init-pass-2026', str(logs))
            repo.close()

            tenant_client = TestClient(create_app(database_url=db_url))
            login = tenant_client.post('/api/auth/login', json={
                'tenant_name': '金桥物业',
                'project_name': '金桥一期',
                'username': 'tenant_admin_jq',
                'role_code': 'system_admin',
                'password': 'Init-pass-2026',
            })
            self.assertEqual(login.status_code, 200)
            self.assertTrue(login.json()['must_change_password'])
            blocked = tenant_client.get('/api/charge-targets')
            self.assertEqual(blocked.status_code, 403)
            changed = tenant_client.post('/api/auth/change-password', json={
                'old_password': 'Init-pass-2026',
                'new_password': 'Changed-pass-2026',
            })
            self.assertEqual(changed.status_code, 200)
            allowed = tenant_client.get('/api/charge-targets')
            self.assertEqual(allowed.status_code, 200)
            repo = create_saas_repository(db_url)
            logs = repo.list_audit_logs(tenant['id'], projects[0]['id'])
            self.assertIn('user.password_change', [row['action'] for row in logs])
            self.assertNotIn('Changed-pass-2026', str(logs))
            repo.close()

    def test_non_platform_admin_cannot_open_tenant_onboarding_page(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, role_code='system_admin', tenant='客户物业', project='客户项目', username='tenant_admin')
            page = client.get('/backoffice/tenant-onboarding')
            self.assertEqual(page.status_code, 403)
            created = client.post('/backoffice/tenant-onboarding/create', data={
                'tenant_name': '坏客户',
                'project_name': '坏项目',
                'admin_username': 'bad_admin',
                'admin_password': 'Bad-pass-2026',
            })
            self.assertEqual(created.status_code, 403)


if __name__ == '__main__':
    unittest.main()
