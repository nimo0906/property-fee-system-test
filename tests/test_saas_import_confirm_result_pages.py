import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasImportConfirmResultPages(unittest.TestCase):
    def _client(self, role_code='finance'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '导入结果物业',
            'project_name': '导入结果项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _preview(self, client):
        csv_text = 'building,unit,room_number,category,area\n1栋,1单元,101,居民,80\n2栋,1单元,,居民,70\n'
        page = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
        self.assertEqual(page.status_code, 200)
        marker = 'name="import_id" value="'
        start = page.text.index(marker) + len(marker)
        end = page.text.index('"', start)
        return int(page.text[start:end])

    def test_confirm_import_returns_batch_summary_page(self):
        client = self._client('finance')
        import_id = self._preview(client)
        page = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})
        self.assertEqual(page.status_code, 200)
        html = page.text
        for text in [
            '导入结果',
            '导入批次摘要',
            f'批次 ID：{import_id}',
            '成功导入：1',
            '跳过错误：1',
            '只写入有效行',
            '错误行未污染正式数据',
            '/backoffice/charge-targets',
            '查看收费对象',
            '/backoffice/imports',
            '继续导入',
        ]:
            self.assertIn(text, html)
        self.assertNotIn('tenant_id', html)
        self.assertNotIn('project_id', html)
        self.assertNotIn('POSTGRES_PASSWORD=', html)


    def test_confirm_import_shows_auto_created_owner_count(self):
        client = self._client('finance')
        csv_text = 'owner_name,owner_phone,building,unit,room_number,category,area\n张业主,13800000000,1栋,1单元,101,居民,80\n李业主,13900000000,商场,一层,A-01,商户,45\n'
        preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
        self.assertEqual(preview.status_code, 200)
        marker = 'name="import_id" value="'
        start = preview.text.index(marker) + len(marker)
        import_id = int(preview.text[start:preview.text.index('"', start)])

        page = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})

        self.assertEqual(page.status_code, 200)
        self.assertIn('成功导入：2', page.text)
        self.assertIn('自动创建业主：2', page.text)
        self.assertNotIn('tenant_id', page.text)
        self.assertNotIn('project_id', page.text)


    def test_persistent_confirm_import_shows_auto_created_owner_count(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = TestClient(create_app(database_url=db_url))
            response = client.post('/api/auth/login', json={
                'tenant_name': '持久导入结果物业',
                'project_name': '持久导入结果项目',
                'username': 'finance',
                'role_code': 'finance',
            })
            self.assertEqual(response.status_code, 200)
            csv_text = 'owner_name,owner_phone,building,unit,room_number,category,area\n王业主,13700000000,1栋,1单元,101,居民,80\n赵业主,13600000000,商场,二层,B-01,商户,55\n'
            preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
            self.assertEqual(preview.status_code, 200)
            marker = 'name="import_id" value="'
            start = preview.text.index(marker) + len(marker)
            import_id = int(preview.text[start:preview.text.index('"', start)])

            page = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})

            self.assertEqual(page.status_code, 200)
            self.assertIn('成功导入：2', page.text)
            self.assertIn('自动创建业主：2', page.text)

    def test_reconfirm_import_shows_zero_created_and_same_skipped(self):
        client = self._client('finance')
        import_id = self._preview(client)
        first = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})
        self.assertEqual(first.status_code, 200)
        second = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})
        self.assertEqual(second.status_code, 200)
        self.assertIn('成功导入：0', second.text)
        self.assertIn('跳过错误：1', second.text)
        self.assertIn('该批次已确认过', second.text)


if __name__ == '__main__':
    unittest.main()
