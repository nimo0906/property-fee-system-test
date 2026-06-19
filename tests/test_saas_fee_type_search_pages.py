import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasFeeTypeSearchPages(unittest.TestCase):
    def _client(self, database_url=None):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '项目筛选物业',
            'project_name': '项目筛选项目',
            'username': 'finance',
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _create(self, client, name, price):
        response = client.post('/backoffice/fee-types/create', data={'name': name, 'unit_price': str(price)}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)

    def test_fee_type_page_has_filters_pagination_and_price_visual_labels(self):
        client = self._client()
        page = client.get('/backoffice/fee-types')
        self.assertEqual(page.status_code, 200)
        for text in [
            '筛选收费项目',
            'name="keyword"',
            'name="price_min"',
            'name="price_max"',
            'name="page_size"',
            '价格配置',
            '基础单价',
            '上一页',
            '下一页',
        ]:
            self.assertIn(text, page.text)

    def test_fee_type_page_filters_by_name_and_price_range(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            self._create(client, '物业费', 2.5)
            self._create(client, '商业物业费', 6.8)
            self._create(client, '停车费', 100)

            page = client.get('/backoffice/fee-types?keyword=物业&price_min=5&price_max=10&page_size=10')
            self.assertEqual(page.status_code, 200)
            html = page.text
            self.assertIn('商业物业费', html)
            self.assertIn('¥6.80', html)
            self.assertIn('共 1 个收费项目', html)
            self.assertNotIn('<strong>物业费</strong>', html)
            self.assertNotIn('<strong>停车费</strong>', html)
            self.assertIn('value="物业"', html)
            self.assertIn('value="5"', html)
            self.assertIn('value="10"', html)

    def test_fee_type_page_paginates_and_keeps_filters(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            for idx in range(1, 6):
                self._create(client, f'项目{idx}', idx)

            page = client.get('/backoffice/fee-types?keyword=项目&page=2&page_size=2')
            self.assertEqual(page.status_code, 200)
            html = page.text
            self.assertIn('共 5 个收费项目 · 第 2 页', html)
            self.assertIn('项目3', html)
            self.assertIn('项目4', html)
            self.assertNotIn('项目1', html)
            self.assertIn('page=1', html)
            self.assertIn('page=3', html)


if __name__ == '__main__':
    unittest.main()
