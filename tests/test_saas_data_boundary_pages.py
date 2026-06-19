import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasDataBoundaryPages(unittest.TestCase):
    def _client(self, role_code='finance'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '边界物业',
            'project_name': '边界项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_data_boundary_check(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('数据边界', page.text)
        self.assertIn('/backoffice/data-boundaries', page.text)

    def test_data_boundary_page_documents_tenant_project_and_storage_isolation(self):
        client = self._client('finance')
        page = client.get('/backoffice/data-boundaries')
        self.assertEqual(page.status_code, 200)
        html = page.text
        for text in [
            '数据边界检查',
            '公司数据隔离',
            '客户上传数据隔离',
            '系统自身数据隔离',
            '平台租户不承载客户业务数据',
            '每张业务表必须带 tenant_id',
            '项目级业务数据必须带 project_id',
            '收费对象',
            '账单',
            '收款',
            '导入文件',
            '审计日志',
            'tenants/{tenant_id}/projects/{project_id}',
            'system/',
            '数据库备份',
            '恢复演练',
            'A 公司不能读取 B 公司数据',
            '客户上传文件不能写入系统目录',
            '系统配置不能写入客户上传目录',
        ]:
            self.assertIn(text, html)
        self.assertNotIn('POSTGRES_PASSWORD=', html)
        self.assertNotIn('APP_SECRET_KEY=', html)
        self.assertNotIn('/var/lib/property-saas/tenants/', html)

    def test_data_boundary_page_requires_login(self):
        client = TestClient(create_app())
        page = client.get('/backoffice/data-boundaries')
        self.assertEqual(page.status_code, 401)


if __name__ == '__main__':
    unittest.main()
