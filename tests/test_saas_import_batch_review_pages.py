import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


CSV_ROWS = """building,unit,room_number,category,area
1栋,1单元,101,居民,80
1栋,1单元,,居民,60
"""


class TestSaasImportBatchReviewPages(unittest.TestCase):
    def _client(self, database_url, tenant_name='批次导入物业', project_name='批次导入项目', role_code='finance'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _preview(self, client):
        preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': CSV_ROWS})
        self.assertEqual(preview.status_code, 200)
        marker = 'name="import_id" value="'
        self.assertIn(marker, preview.text)
        return preview.text.split(marker)[1].split('"')[0]

    def test_import_home_lists_preview_batches_with_review_and_error_links(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            import_id = self._preview(client)

            page = client.get('/backoffice/imports')

            self.assertEqual(page.status_code, 200)
            for text in ['导入批次记录', f'批次 {import_id}', '待确认', '有效 1 行', '错误 1 行', '复核批次']:
                self.assertIn(text, page.text)
            self.assertIn(f'/backoffice/imports/{import_id}/review', page.text)
            self.assertIn(f'/api/imports/{import_id}/errors.csv', page.text)
            self.assertNotIn('tenant_id', page.text)
            self.assertNotIn('project_id', page.text)


    def test_import_home_batch_list_shows_auto_created_owner_count_after_confirm(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            csv_text = 'owner_name,owner_phone,building,unit,room_number,category,area\n张业主,13800000000,1栋,1单元,101,居民,80\n李业主,13900000000,商场,一层,A-01,商户,45\n'
            preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
            self.assertEqual(preview.status_code, 200)
            marker = 'name="import_id" value="'
            import_id = preview.text.split(marker)[1].split('"')[0]
            confirmed = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})
            self.assertEqual(confirmed.status_code, 200)

            page = client.get('/backoffice/imports')

            self.assertEqual(page.status_code, 200)
            self.assertIn('自动创建业主', page.text)
            self.assertIn('业主 2 个', page.text)
            self.assertIn(f'批次 {import_id}', page.text)
            self.assertNotIn('tenant_id', page.text)
            self.assertNotIn('project_id', page.text)

    def test_import_batch_review_page_is_tenant_scoped_and_updates_after_confirm(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A批次物业', project_name='A批次项目')
            import_id = self._preview(client_a)

            review = client_a.get(f'/backoffice/imports/{import_id}/review')
            self.assertEqual(review.status_code, 200)
            for text in ['导入批次复核', f'批次 {import_id}', '状态：待确认', '有效行', '错误行', '确认导入']:
                self.assertIn(text, review.text)
            self.assertIn('101', review.text)
            self.assertIn('房号/铺位号必填', review.text)
            self.assertIn(f'/api/imports/{import_id}/errors.csv', review.text)

            confirmed = client_a.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})
            self.assertEqual(confirmed.status_code, 200)
            review_after = client_a.get(f'/backoffice/imports/{import_id}/review')
            self.assertIn('状态：已确认', review_after.text)
            self.assertIn('该批次已确认过', review_after.text)

            client_b = self._client(db_url, tenant_name='B批次物业', project_name='B批次项目')
            blocked = client_b.get(f'/backoffice/imports/{import_id}/review')
            self.assertEqual(blocked.status_code, 403)


if __name__ == '__main__':
    unittest.main()
