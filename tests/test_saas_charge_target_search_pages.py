import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasChargeTargetSearchPages(unittest.TestCase):
    def _client(self, database_url=None, tenant_name='筛选物业', project_name='筛选项目'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': 'finance',
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _create(self, client, building, unit, room_number, category='居民', area='80'):
        response = client.post('/backoffice/charge-targets/create', data={
            'building': building,
            'unit': unit,
            'room_number': room_number,
            'category': category,
            'area': area,
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 303)

    def test_charge_target_page_has_search_filters_and_pagination_controls(self):
        client = self._client()
        page = client.get('/backoffice/charge-targets')
        self.assertEqual(page.status_code, 200)
        for text in [
            '筛选收费对象',
            'name="building"',
            'name="unit"',
            'name="room_number"',
            'name="category"',
            'name="page_size"',
            '上一页',
            '下一页',
        ]:
            self.assertIn(text, page.text)

    def test_charge_target_page_filters_by_building_unit_room_and_category(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            self._create(client, '住宅A', '1单元', '101', '居民')
            self._create(client, '住宅A', '2单元', '201', '居民')
            self._create(client, '商业街', '一层', 'A-001', '商户', '56.5')

            page = client.get('/backoffice/charge-targets?building=商业&unit=一层&room_number=A-&category=商户&page_size=10')
            self.assertEqual(page.status_code, 200)
            html = page.text
            self.assertIn('商业街', html)
            self.assertIn('A-001', html)
            self.assertIn('共 1 个收费对象', html)
            self.assertNotIn('住宅A', html)
            self.assertIn('value="商业"', html)
            self.assertIn('value="一层"', html)
            self.assertIn('value="A-"', html)

    def test_charge_target_page_paginates_results_and_keeps_filters(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            for i in range(1, 6):
                self._create(client, '批量楼', '1单元', f'{100 + i}', '居民')

            page = client.get('/backoffice/charge-targets?building=批量楼&page=2&page_size=2')
            self.assertEqual(page.status_code, 200)
            html = page.text
            self.assertIn('共 5 个收费对象 · 第 2 页', html)
            self.assertIn('103', html)
            self.assertIn('104', html)
            self.assertNotIn('<strong>101</strong>', html)
            self.assertIn('/backoffice/charge-targets?building=', html)
            self.assertIn('page=1', html)
            self.assertIn('page=3', html)


if __name__ == '__main__':
    unittest.main()
