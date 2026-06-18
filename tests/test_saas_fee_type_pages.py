import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasFeeTypePages(unittest.TestCase):
    def _client(self, role_code='finance', database_url=None):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '收费项目物业',
            'project_name': '收费项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_backoffice_home_links_fee_types(self):
        client = self._client('finance')
        page = client.get('/backoffice')
        self.assertEqual(page.status_code, 200)
        self.assertIn('收费项目', page.text)
        self.assertIn('/backoffice/fee-types', page.text)

    def test_fee_type_page_can_create_and_list_persistently(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client('finance', database_url=db_url)
            created = client.post('/backoffice/fee-types/create', data={
                'name': '物业费',
                'unit_price': '2.50',
            }, follow_redirects=False)
            self.assertEqual(created.status_code, 303)
            page = client.get('/backoffice/fee-types')
            self.assertEqual(page.status_code, 200)
            self.assertIn('收费项目管理', page.text)
            self.assertIn('物业费', page.text)
            self.assertIn('2.5', page.text)

            repo = create_saas_repository(db_url)
            items = repo.list_fee_types(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            self.assertEqual(items[0]['name'], '物业费')
            self.assertEqual(items[0]['unit_price'], 2.5)
            repo.close()

    def test_cashier_can_view_but_cannot_create_fee_type(self):
        client = self._client('cashier')
        page = client.get('/backoffice/fee-types')
        self.assertEqual(page.status_code, 200)
        created = client.post('/backoffice/fee-types/create', data={
            'name': '停车费',
            'unit_price': '100',
        })
        self.assertEqual(created.status_code, 403)


if __name__ == '__main__':
    unittest.main()
