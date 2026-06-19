import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasImportErrorDownload(unittest.TestCase):
    def _client(self, role_code='finance'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '错误行物业',
            'project_name': '错误行项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _preview_with_errors(self, client):
        csv_text = 'building,unit,room_number,category,area\n1栋,1单元,101,居民,80\n,1单元,102,居民,90\n2栋,1单元,,居民,70\n3栋,1单元,301,居民,-1\n'
        page = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
        self.assertEqual(page.status_code, 200)
        marker = 'name="import_id" value="'
        start = page.text.index(marker) + len(marker)
        end = page.text.index('"', start)
        return int(page.text[start:end]), page.text

    def test_preview_page_links_error_csv_when_errors_exist(self):
        client = self._client('finance')
        import_id, html = self._preview_with_errors(client)
        self.assertIn('下载错误行 CSV', html)
        self.assertIn(f'/api/imports/{import_id}/errors.csv', html)
        self.assertIn('修正后可重新复制到导入预览', html)

    def test_error_csv_download_contains_row_error_and_original_fields(self):
        client = self._client('finance')
        import_id, _ = self._preview_with_errors(client)
        response = client.get(f'/api/imports/{import_id}/errors.csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.headers.get('content-type', ''))
        self.assertIn('attachment; filename="charge_targets_errors.csv"', response.headers.get('content-disposition', ''))
        lines = response.text.strip().splitlines()
        self.assertEqual(lines[0], 'row,error,building,unit,room_number,category,area')
        self.assertIn('楼栋/区域不能为空', response.text)
        self.assertIn('房号/铺位号不能为空', response.text)
        self.assertIn('面积必须是数字且大于0', response.text)
        self.assertNotIn('tenant_id', response.text)
        self.assertNotIn('project_id', response.text)
        self.assertNotIn('POSTGRES_PASSWORD=', response.text)

    def test_error_csv_is_tenant_scoped_and_requires_login(self):
        client_a = self._client('finance')
        import_id, _ = self._preview_with_errors(client_a)
        client_b = TestClient(create_app())
        self.assertEqual(client_b.get(f'/api/imports/{import_id}/errors.csv').status_code, 401)

        client_b = self._client('finance')
        forbidden = client_b.get(f'/api/imports/{import_id}/errors.csv')
        self.assertEqual(forbidden.status_code, 403)


if __name__ == '__main__':
    unittest.main()
