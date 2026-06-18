import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasTenantProjectPages(unittest.TestCase):
    def _client(self, db_url, tenant='项目物业', project='默认项目', username='admin', role_code='system_admin'):
        client = TestClient(create_app(database_url=db_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant,
            'project_name': project,
            'username': username,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_tenant_project_management_for_admins(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin = self._client(db_url, role_code='system_admin')
            page = admin.get('/backoffice')
            self.assertEqual(page.status_code, 200)
            self.assertIn('租户项目', page.text)
            self.assertIn('/backoffice/tenant-projects', page.text)
            finance = self._client(db_url, username='finance', role_code='finance')
            finance_page = finance.get('/backoffice')
            self.assertNotIn('href="/backoffice/tenant-projects"', finance_page.text)

    def test_tenant_admin_lists_and_creates_only_own_projects(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin_a = self._client(db_url, tenant='A物业', project='A项目', username='admin_a')
            admin_b = self._client(db_url, tenant='B物业', project='B项目', username='admin_b')
            created = admin_a.post('/backoffice/tenant-projects/create', data={
                'name': 'A二期',
                'code': 'A-002',
            }, follow_redirects=False)
            self.assertEqual(created.status_code, 303)
            page_a = admin_a.get('/backoffice/tenant-projects')
            self.assertEqual(page_a.status_code, 200)
            self.assertIn('租户项目管理', page_a.text)
            self.assertIn('A项目', page_a.text)
            self.assertIn('A二期', page_a.text)
            self.assertNotIn('B项目', page_a.text)
            page_b = admin_b.get('/backoffice/tenant-projects')
            self.assertIn('B项目', page_b.text)
            self.assertNotIn('A二期', page_b.text)

            repo = create_saas_repository(db_url)
            tenant_a = next(row for row in repo.list_tenants() if row['name'] == 'A物业')
            projects_a = [row for row in repo.list_projects() if row['tenant_id'] == tenant_a['id']]
            self.assertIn('A二期', [row['name'] for row in projects_a])
            logs = repo.list_audit_logs(tenant_a['id'], projects_a[0]['id'])
            self.assertIn('project.create', [row['action'] for row in logs])
            repo.close()

    def test_platform_admin_sees_tenant_list_but_tenant_admin_does_not_see_other_tenants(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            self._client(db_url, tenant='A物业', project='A项目', username='admin_a')
            self._client(db_url, tenant='B物业', project='B项目', username='admin_b')
            platform = self._client(db_url, tenant='平台物业', project='平台项目', username='platform', role_code='platform_admin')
            page = platform.get('/backoffice/tenant-projects')
            self.assertEqual(page.status_code, 200)
            self.assertIn('平台租户视图', page.text)
            self.assertIn('A物业', page.text)
            self.assertIn('B物业', page.text)
            self.assertIn('平台物业', page.text)

            admin_a = self._client(db_url, tenant='A物业', project='A项目', username='admin_a')
            page_a = admin_a.get('/backoffice/tenant-projects')
            self.assertNotIn('B物业', page_a.text)
            self.assertNotIn('平台租户视图', page_a.text)

    def test_non_admin_cannot_open_or_create_tenant_projects(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            cashier = self._client(db_url, username='cashier', role_code='cashier')
            page = cashier.get('/backoffice/tenant-projects')
            self.assertEqual(page.status_code, 403)
            created = cashier.post('/backoffice/tenant-projects/create', data={'name': 'bad', 'code': ''})
            self.assertEqual(created.status_code, 403)


if __name__ == '__main__':
    unittest.main()
