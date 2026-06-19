import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasAccountBoundaryPages(unittest.TestCase):
    def _login(self, db_url, role_code, tenant_name, project_name, username):
        client = TestClient(create_app(database_url=db_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': username,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_platform_user_page_documents_cross_tenant_account_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._login(db_url, 'platform_admin', '平台物业', '平台项目', 'platform_admin')

            page = client.get('/backoffice/users')
            self.assertEqual(page.status_code, 200)
            for text in [
                '平台账号不承载客户业务数据',
                '客户员工必须归属具体客户公司',
                '跨租户账号操作写入目标租户审计',
                '不能把客户上传数据放入平台租户',
            ]:
                self.assertIn(text, page.text)

    def test_tenant_admin_page_documents_tenant_only_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._login(db_url, 'system_admin', '客户物业', '客户项目', 'tenant_admin')

            page = client.get('/backoffice/tenant-admin')
            self.assertEqual(page.status_code, 200)
            for text in [
                '只能管理本公司员工账号',
                '不能查看或操作其他客户公司账号',
                '客户上传数据只进入本租户目录',
                '系统自身部署、备份和运行数据使用系统目录',
            ]:
                self.assertIn(text, page.text)

    def test_onboarding_page_documents_new_customer_isolation_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._login(db_url, 'platform_admin', '平台物业', '平台项目', 'platform_admin')

            page = client.get('/backoffice/tenant-onboarding')
            self.assertEqual(page.status_code, 200)
            for text in [
                '新客户必须创建独立 tenant_id',
                '默认项目使用独立 project_id',
                '客户上传文件进入租户目录',
                '平台系统配置、日志和备份进入系统目录',
                '首个账号只能是该客户的租户管理员',
            ]:
                self.assertIn(text, page.text)


if __name__ == '__main__':
    unittest.main()
