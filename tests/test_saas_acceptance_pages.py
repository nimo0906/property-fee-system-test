import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasAcceptancePages(unittest.TestCase):
    def _client(self, role_code='system_admin'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '验收页面物业',
            'project_name': '验收页面项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_acceptance_page(self):
        client = self._client('system_admin')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('/backoffice/acceptance', page.text)

    def test_acceptance_page_documents_full_business_closure(self):
        client = self._client('system_admin')
        page = client.get('/backoffice/acceptance')
        self.assertEqual(page.status_code, 200)
        html = page.text
        self.assertIn('SaaS 商业后台验收', html)
        for text in [
            '创建项目', '导入/录入收费对象', '配置收费项目', '生成账单', '审核账单',
            '登记收款', '对账报表', '审计日志', '备份恢复', '租户隔离',
            'scripts/saas_acceptance_check.py',
        ]:
            self.assertIn(text, html)
        for href in [
            '/backoffice/charge-targets', '/backoffice/fee-types', '/backoffice/bills',
            '/backoffice/payments', '/backoffice/reports', '/backoffice/audit-logs',
            '/backoffice/backups', '/backoffice/imports',
        ]:
            self.assertIn(href, html)

    def test_finance_can_view_acceptance_page_readonly(self):
        client = self._client('finance')
        page = client.get('/backoffice/acceptance')
        self.assertEqual(page.status_code, 200)
        self.assertIn('只读验收清单', page.text)

    def test_acceptance_page_shows_password_policy(self):
        client = self._client('system_admin')
        page = client.get('/backoffice/acceptance')
        self.assertEqual(page.status_code, 200)
        for text in [
            '密码策略',
            '最少 8 位',
            '个人改密不能与原密码相同',
            '管理员重置临时密码不能与当前密码相同',
            '密码不展示在页面、日志或审计明细',
        ]:
            self.assertIn(text, page.text)


if __name__ == '__main__':
    unittest.main()
