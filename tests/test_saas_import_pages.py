import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


CSV_ROWS = """building,unit,room_number,category,area
1栋,1单元,101,居民,80
1栋,1单元,,居民,60
1栋,1单元,103,居民,bad
"""


class TestSaasImportPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None, tenant_name='导入页面物业', project_name='导入页面项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_import_page(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/imports', page.text)

    def test_preview_does_not_write_and_confirm_writes_only_valid_rows(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': CSV_ROWS}, follow_redirects=False)
            self.assertEqual(preview.status_code, 200)
            self.assertIn('导入预览', preview.text)
            self.assertIn('有效 1 行', preview.text)
            self.assertIn('错误 2 行', preview.text)
            self.assertIn('确认导入', preview.text)

            repo = create_saas_repository(db_url)
            self.assertEqual(repo.list_charge_targets(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id']), [])
            repo.close()

            import_id = preview.text.split('name="import_id" value="')[1].split('"')[0]
            confirmed = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id}, follow_redirects=False)
            self.assertEqual(confirmed.status_code, 303)

            repo = create_saas_repository(db_url)
            targets = repo.list_charge_targets(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0]['room_number'], '101')
            repo.close()

    def test_import_page_registers_upload_file_under_tenant_scope(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            page = client.get('/backoffice/imports')
            self.assertEqual(page.status_code, 200)
            self.assertIn('上传文件登记', page.text)
            self.assertIn('/backoffice/imports/files/register', page.text)
            self.assertIn('客户上传文件进入当前租户目录', page.text)
            self.assertIn('预览不会写库', page.text)

            registered = client.post('/backoffice/imports/files/register', data={
                'original_name': '../../业主房间.xlsx',
                'file_size': '2048',
                'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            }, follow_redirects=False)
            self.assertEqual(registered.status_code, 200)
            html = registered.text
            self.assertIn('文件已登记', html)
            self.assertIn('tenants/', html)
            self.assertIn('/imports/', html)
            self.assertNotIn('..', html)

            repo = create_saas_repository(db_url)
            tenant = repo.list_tenants()[0]
            project = repo.list_projects(tenant['id'])[0]
            files = repo.list_import_files(tenant['id'], project['id'])
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0]['storage_key'].startswith(f"tenants/{tenant['id']}/projects/{project['id']}/imports/"))
            self.assertNotIn('..', files[0]['storage_key'])
            repo.close()

    def test_import_page_shows_recent_uploads_and_import_audit(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            registered = client.post('/backoffice/imports/files/register', data={
                'original_name': '房间导入.xlsx',
                'file_size': '4096',
                'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            })
            self.assertEqual(registered.status_code, 200)
            preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': CSV_ROWS})
            import_id = preview.text.split('name="import_id" value="')[1].split('"')[0]
            confirmed = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id}, follow_redirects=False)
            self.assertEqual(confirmed.status_code, 303)

            page = client.get('/backoffice/imports')
            self.assertEqual(page.status_code, 200)
            html = page.text
            self.assertIn('最近上传文件', html)
            self.assertIn('房间导入.xlsx', html)
            self.assertIn('uploaded', html)
            self.assertIn('tenants/', html)
            self.assertIn('最近导入审计', html)
            self.assertIn('import.confirm', html)
            self.assertIn('写入 1 行', html)
            self.assertIn('跳过 2 行', html)
            self.assertIn('/backoffice/audit-logs', html)

    def test_executive_cannot_preview_import(self):
        client = self._client('executive')
        page = client.get('/backoffice/imports')
        self.assertEqual(page.status_code, 200)
        self.assertIn('当前角色不能导入', page.text)
        blocked = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': CSV_ROWS}, follow_redirects=False)
        self.assertEqual(blocked.status_code, 403)

    def test_other_tenant_cannot_confirm_import_id(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client('finance', database_url=db_url, tenant_name='A导入物业', project_name='A导入项目')
            preview = client_a.post('/backoffice/imports/charge-targets/preview', data={'csv_text': CSV_ROWS})
            self.assertEqual(preview.status_code, 200)
            import_id = preview.text.split('name="import_id" value="')[1].split('"')[0]

            client_b = self._client('finance', database_url=db_url, tenant_name='B导入物业', project_name='B导入项目')
            blocked = client_b.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id}, follow_redirects=False)
            self.assertEqual(blocked.status_code, 403)


if __name__ == '__main__':
    unittest.main()
