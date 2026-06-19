import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasIsolationSelfCheckPages(unittest.TestCase):
    def _client(self, role_code='finance'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '自检展示物业',
            'project_name': '自检展示项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_boundary_page_posts_to_html_self_check_result(self):
        client = self._client('finance')
        page = client.get('/backoffice/data-boundaries')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/data-boundaries/self-check', page.text)
        self.assertIn('查看页面化结果', page.text)

    def test_html_self_check_result_shows_pass_fail_items_time_and_security_notice(self):
        client = self._client('finance')
        page = client.post('/backoffice/data-boundaries/self-check')
        self.assertEqual(page.status_code, 200)
        html = page.text
        for text in [
            '租户隔离自检结果',
            '检查时间',
            '总体结果',
            'PASS',
            '收费对象',
            '账单',
            '收款',
            '导入文件',
            '审计日志',
            '当前租户项目范围',
            '不展示客户业务明细',
            '不展示真实路径',
            '不展示数据库密码或应用密钥',
            '/backoffice/data-boundaries',
        ]:
            self.assertIn(text, html)
        self.assertNotIn('POSTGRES_PASSWORD=', html)
        self.assertNotIn('APP_SECRET_KEY=', html)
        self.assertNotIn('金丝雀楼', html)
        self.assertNotIn('canary.xlsx', html)

    def test_html_self_check_requires_login(self):
        client = TestClient(create_app())
        page = client.post('/backoffice/data-boundaries/self-check')
        self.assertEqual(page.status_code, 401)


if __name__ == '__main__':
    unittest.main()
