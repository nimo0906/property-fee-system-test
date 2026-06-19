import unittest

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
