import tempfile
from urllib.parse import quote
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


class TestSaasBillSearchBatchPages(unittest.TestCase):
    def _client(self, database_url=None):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': '账单筛选物业',
            'project_name': '账单筛选项目',
            'username': 'finance',
            'role_code': 'finance',
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_bill(self, client, room, area, period='2026-06'):
        target = client.post('/api/charge-targets', json={
            'building': '账单楼', 'unit': '1单元', 'room_number': room, 'category': '居民', 'area': area,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': f'物业费{room}', 'unit_price': 2}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'],
            'fee_type_id': fee['id'],
            'billing_period': period,
            'service_start': f'{period}-01',
            'service_end': f'{period}-28',
        }).json()['item']
        return bill

    def test_bill_page_has_advanced_filters_pagination_and_batch_approve_entry(self):
        client = self._client()
        page = client.get('/backoffice/bills')
        self.assertEqual(page.status_code, 200)
        for text in [
            '高级筛选',
            'name="room_number"',
            'name="amount_min"',
            'name="amount_max"',
            'name="page_size"',
            '批量审核',
            '批量审核选中账单',
            '上一页',
            '下一页',
        ]:
            self.assertIn(text, page.text)

    def test_bill_page_filters_by_period_status_room_and_amount_range(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            self._seed_bill(client, '101', 50, '2026-06')
            self._seed_bill(client, '商铺A', 120, '2026-06')
            other = self._seed_bill(client, '201', 80, '2026-07')
            client.post(f"/api/bills/{other['id']}/approve", json={})

            page = client.get('/backoffice/bills?period=2026-06&status=pending_review&room_number=商铺&amount_min=200&amount_max=300&page_size=10')
            self.assertEqual(page.status_code, 200)
            html = page.text
            self.assertIn('商铺A', html)
            self.assertIn('240.0', html)
            self.assertIn('共 1 张账单', html)
            self.assertNotIn('<td>账单楼 1单元 101</td>', html)
            self.assertNotIn('<td>账单楼 1单元 201</td>', html)
            self.assertIn('value="商铺"', html)
            self.assertIn('value="200"', html)
            self.assertIn('value="300"', html)


    def test_bill_page_export_preserves_and_applies_current_filters(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            self._seed_bill(client, '101', 50, '2026-06')
            self._seed_bill(client, '商铺A', 120, '2026-06')
            other = self._seed_bill(client, '201', 80, '2026-07')
            client.post(f"/api/bills/{other['id']}/approve", json={})

            href = f'/api/exports/bills?period=2026-06&status=pending_review&room_number={quote("商铺")}&amount_min=200&amount_max=300'
            page = client.get('/backoffice/bills?period=2026-06&status=pending_review&room_number=商铺&amount_min=200&amount_max=300&page_size=10')
            self.assertEqual(page.status_code, 200)
            self.assertIn(href.replace('&', '&amp;'), page.text)

            exported = client.get(href)
            self.assertEqual(exported.status_code, 200)
            content = exported.json()['content']
            self.assertIn('商铺A', content)
            self.assertIn('240.0', content)
            self.assertNotIn('101', content)
            self.assertNotIn('201', content)


    def test_merchant_bill_page_and_export_include_shop_and_tenant_names(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            target = client.post('/api/charge-targets', json={
                'building': '商场账单区', 'unit': '二层', 'room_number': 'M-201',
                'category': '商户', 'area': 100, 'shop_name': '账单咖啡店',
                'tenant_name': '账单承租人', 'tenant_phone': '13900000000',
            }).json()['item']
            fee = client.post('/api/fee-types', json={'name': '商户物业费', 'unit_price': 3}).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-02',
                'service_start': '2028-02-01', 'service_end': '2028-02-29',
            }).json()['item']

            page = client.get('/backoffice/bills?period=2028-02')
            self.assertEqual(page.status_code, 200)
            for text in ['M-201', '账单咖啡店', '账单承租人', bill['bill_number']]:
                self.assertIn(text, page.text)

            exported = client.get('/api/exports/bills?period=2028-02')
            self.assertEqual(exported.status_code, 200)
            content = exported.json()['content']
            for text in ['shop_name', 'tenant_name', '账单咖啡店', '账单承租人', bill['bill_number']]:
                self.assertIn(text, content)

    def test_bill_page_paginates_and_batch_approves_selected_pending_bills(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(database_url=db_url)
            bills = [self._seed_bill(client, str(100 + i), 50, '2026-06') for i in range(1, 5)]

            page = client.get('/backoffice/bills?period=2026-06&page=2&page_size=2')
            self.assertEqual(page.status_code, 200)
            self.assertIn('共 4 张账单 · 第 2 页', page.text)
            self.assertIn('103', page.text)
            self.assertIn('104', page.text)
            self.assertIn('page=1', page.text)

            response = client.post('/backoffice/bills/batch-approve', data={'bill_ids': [str(bills[0]['id']), str(bills[1]['id'])]}, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertIn('message=', response.headers['location'])

            repo = create_saas_repository(db_url)
            stored = repo.list_bills(repo.list_tenants()[0]['id'], repo.list_projects()[0]['id'])
            statuses = {item['id']: item['status'] for item in stored}
            self.assertEqual(statuses[bills[0]['id']], 'unpaid')
            self.assertEqual(statuses[bills[1]['id']], 'unpaid')
            self.assertEqual(statuses[bills[2]['id']], 'pending_review')
            repo.close()


if __name__ == '__main__':
    unittest.main()
