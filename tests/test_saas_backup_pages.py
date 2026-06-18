import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasBackupPages(unittest.TestCase):
    def _client(self, role_code='system_admin', database_url=None, tenant_name='备份物业', project_name='备份项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_backup_page(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/backups', page.text)

    def test_admin_can_create_backup_and_restore_drill_from_page(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('system_admin', database_url=db_url)
            page = client.get('/backoffice/backups')
            self.assertEqual(page.status_code, 200)
            self.assertIn('备份记录', page.text)
            self.assertIn('恢复演练', page.text)
            self.assertIn('创建备份', page.text)

            backup = client.post('/backoffice/backups/create', follow_redirects=False)
            self.assertEqual(backup.status_code, 303)
            page = client.get('/backoffice/backups')
            self.assertIn('backup-', page.text)
            self.assertIn('restore', page.text)

            repo = create_saas_repository(db_url)
            records = repo.list_backup_records(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            self.assertEqual(len(records), 1)
            drill = client.post('/backoffice/backups/restore-drills', data={
                'backup_id': records[0]['backup_id'],
                'scope': 'database'
            }, follow_redirects=False)
            self.assertEqual(drill.status_code, 303)
            logs = repo.list_audit_logs(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            actions = [row['action'] for row in logs]
            self.assertIn('backup.create', actions)
            self.assertIn('restore.drill', actions)
            repo.close()

    def test_finance_can_view_but_cannot_create_backup_or_restore_drill(self):
        client = self._client('finance')
        page = client.get('/backoffice/backups')
        self.assertEqual(page.status_code, 200)
        self.assertIn('当前角色只能查看备份', page.text)
        self.assertNotIn('创建备份', page.text)
        self.assertNotIn('提交恢复演练', page.text)
        self.assertEqual(client.post('/backoffice/backups/create', follow_redirects=False).status_code, 403)
        self.assertEqual(client.post('/backoffice/backups/restore-drills', data={'backup_id': 'backup-1', 'scope': 'database'}, follow_redirects=False).status_code, 403)

    def test_backup_page_is_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            admin_a = self._client('system_admin', database_url=db_url, tenant_name='A备份物业', project_name='A备份项目')
            admin_a.post('/backoffice/backups/create')

            admin_b = self._client('system_admin', database_url=db_url, tenant_name='B备份物业', project_name='B备份项目')
            page_b = admin_b.get('/backoffice/backups')
            self.assertEqual(page_b.status_code, 200)
            self.assertNotIn('backup-', page_b.text)
            self.assertNotIn('restore-', page_b.text)
            self.assertEqual(admin_b.post('/backoffice/backups/restore-drills', data={'backup_id': 'backup-000001', 'scope': 'database'}, follow_redirects=False).status_code, 403)


if __name__ == '__main__':
    unittest.main()
