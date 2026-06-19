import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasBackupSearchDetailPages(unittest.TestCase):
    def _client(self, database_url, tenant_name='备份增强物业', project_name='备份增强项目', role_code='system_admin'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _create_backup_and_drill(self, db_url, client, scope='database'):
        self.assertEqual(client.post('/backoffice/backups/create', follow_redirects=False).status_code, 303)
        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        record = repo.list_backup_records(tenant['id'], project['id'])[-1]
        repo.close()
        self.assertEqual(client.post('/backoffice/backups/restore-drills', data={'backup_id': record['backup_id'], 'scope': scope}, follow_redirects=False).status_code, 303)
        return record

    def test_backup_page_filters_records_and_exposes_detail_links(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url)
            first = self._create_backup_and_drill(db_url, client, 'database')
            second = self._create_backup_and_drill(db_url, client, 'tenant-files')

            page = client.get(f"/backoffice/backups?keyword={second['backup_id']}&status=created&scope=tenant-files&page=1&page_size=1")

            self.assertEqual(page.status_code, 200)
            for text in ['高级筛选', '备份详情', '恢复演练详情', '上一页', '下一页', 'tenant-files']:
                self.assertIn(text, page.text)
            for field in ['keyword', 'status', 'scope', 'page_size']:
                self.assertIn(f'name="{field}"', page.text)
            self.assertIn(second['backup_id'], page.text)
            self.assertNotIn(f'<td>{first["backup_id"]}</td>', page.text)
            self.assertIn(f'/backoffice/backups/{second["backup_id"]}', page.text)
            self.assertIn('/backoffice/backups/restore-drills/', page.text)

    def test_backup_and_restore_detail_pages_are_tenant_scoped_and_hide_paths_and_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A备份增强物业', project_name='A备份增强项目')
            record = self._create_backup_and_drill(db_url, client_a, 'system-files')
            repo = create_saas_repository(db_url)
            tenant = repo.list_tenants()[0]
            project = repo.list_projects(tenant['id'])[0]
            drill = repo.list_restore_drills(tenant['id'], project['id'])[0]
            repo.close()

            backup_detail = client_a.get(f"/backoffice/backups/{record['backup_id']}")
            self.assertEqual(backup_detail.status_code, 200)
            for text in ['备份详情', record['backup_id'], 'created', 'A备份增强物业', 'A备份增强项目', '恢复演练记录']:
                self.assertIn(text, backup_detail.text)
            drill_detail = client_a.get(f"/backoffice/backups/restore-drills/{drill['id']}")
            self.assertEqual(drill_detail.status_code, 200)
            for text in ['恢复演练详情', record['backup_id'], 'system-files', 'recorded', 'A备份增强物业', 'A备份增强项目']:
                self.assertIn(text, drill_detail.text)
            for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/var/lib/property-saas', 'tenant_id', 'project_id']:
                self.assertNotIn(hidden, backup_detail.text)
                self.assertNotIn(hidden, drill_detail.text)

            client_b = self._client(db_url, tenant_name='B备份增强物业', project_name='B备份增强项目')
            self.assertEqual(client_b.get(f"/backoffice/backups/{record['backup_id']}").status_code, 404)
            self.assertEqual(client_b.get(f"/backoffice/backups/restore-drills/{drill['id']}").status_code, 404)


if __name__ == '__main__':
    unittest.main()
