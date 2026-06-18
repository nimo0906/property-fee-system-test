import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasChargeTargetPages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '对象物业',
            'project_name': '对象项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_charge_targets(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('收费对象', page.text)
        self.assertIn('/backoffice/charge-targets', page.text)

    def test_charge_target_page_uses_general_property_labels(self):
        client = self._client('finance')
        page = client.get('/backoffice/charge-targets')
        self.assertEqual(page.status_code, 200)
        self.assertIn('收费对象管理', page.text)
        self.assertIn('楼栋 / 区域', page.text)
        self.assertIn('单元 / 分区', page.text)
        self.assertIn('房号 / 铺位号', page.text)

    def test_charge_target_page_can_create_and_list_target_persistently(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            created = client.post('/backoffice/charge-targets/create', data={
                'building': '商业区A',
                'unit': '一层',
                'room_number': 'A-101',
                'category': '商户',
                'area': '88.5',
            }, follow_redirects=False)
            self.assertEqual(created.status_code, 303)
            page = client.get('/backoffice/charge-targets')
            self.assertIn('商业区A', page.text)
            self.assertIn('A-101', page.text)

            repo = create_saas_repository(db_url)
            target = repo.list_charge_targets(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])[0]
            self.assertEqual(target['building'], '商业区A')
            self.assertEqual(target['unit'], '一层')
            self.assertEqual(target['room_number'], 'A-101')
            self.assertEqual(target['category'], '商户')
            repo.close()

    def test_cashier_can_view_but_cannot_create_charge_target(self):
        client = self._client('cashier')
        page = client.get('/backoffice/charge-targets')
        self.assertEqual(page.status_code, 200)
        created = client.post('/backoffice/charge-targets/create', data={
            'building': '住宅楼',
            'unit': '1单元',
            'room_number': '101',
            'category': '居民',
            'area': '80',
        })
        self.assertEqual(created.status_code, 403)


if __name__ == '__main__':
    unittest.main()
