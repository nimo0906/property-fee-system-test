import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasReportPageEnhancements(unittest.TestCase):
    def _client(self, database_url, tenant_name='增强报表物业', project_name='增强报表项目', role_code='finance'):
        client = TestClient(create_app(database_url=database_url))
        response = client.post('/api/auth/login', json={
            'tenant_name': tenant_name,
            'project_name': project_name,
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_bill_with_payment(self, client, period, room, due_amount, payment_amount):
        target = client.post('/api/charge-targets', json={
            'building': '5栋', 'unit': '5单元', 'room_number': room, 'category': '居民', 'area': due_amount,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': f'物业费{room}', 'unit_price': 1}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': period,
            'service_start': f'{period}-01', 'service_end': f'{period}-28',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve", json={})
        if payment_amount:
            payment = client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': payment_amount, 'method': 'cash',
                'idempotency_key': f'REPORT-ENH-{period}-{room}',
            })
            self.assertEqual(payment.status_code, 200)
        return bill

    def test_report_page_has_commercial_summary_rates_and_period_exports(self):
        with tempfile.TemporaryDirectory() as td:
            client = self._client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
            self._seed_bill_with_payment(client, '2026-10', '501', 100, 100)
            self._seed_bill_with_payment(client, '2026-10', '502', 300, 50)
            self._seed_bill_with_payment(client, '2026-11', '503', 900, 900)

            page = client.get('/backoffice/reports?period=2026-10')

            self.assertEqual(page.status_code, 200)
            for text in ['对账报表', '高级筛选', '经营摘要', '收缴率', '欠费率', '导出账单', '导出收款流水', '欠费提醒']:
                self.assertIn(text, page.text)
            self.assertIn('37.50%', page.text)
            self.assertIn('62.50%', page.text)
            self.assertIn('/api/exports/bills?period=2026-10', page.text)
            self.assertIn('/api/exports/payments?period=2026-10', page.text)
            self.assertIn('400.0', page.text)
            self.assertIn('150.0', page.text)
            self.assertIn('250.0', page.text)
            self.assertNotIn('900.0</div>', page.text)

    def test_empty_report_page_shows_zero_rates_without_cross_tenant_data_or_internal_fields(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client_a = self._client(db_url, tenant_name='A增强报表物业', project_name='A增强报表项目')
            self._seed_bill_with_payment(client_a, '2026-10', '601', 500, 500)

            client_b = self._client(db_url, tenant_name='B增强报表物业', project_name='B增强报表项目')
            page = client_b.get('/backoffice/reports?period=2026-10')

            self.assertEqual(page.status_code, 200)
            self.assertIn('0.00%', page.text)
            self.assertIn('暂无欠费', page.text)
            self.assertNotIn('500.0</div>', page.text)
            for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'password']:
                self.assertNotIn(hidden, page.text)

    def test_report_breakdown_groups_due_paid_unpaid_by_building_and_fee_type(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url)
            property_fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
            parking_fee = client.post('/api/fee-types', json={'name': '车位费', 'unit_price': 80, 'billing_mode': 'fixed'}).json()['item']

            def seed(building, unit, room, area, fee, paid):
                target = client.post('/api/charge-targets', json={
                    'building': building, 'unit': unit, 'room_number': room, 'category': '商户', 'area': area,
                }).json()['item']
                bill = client.post('/api/bills/generate', json={
                    'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-12',
                    'service_start': '2026-12-01', 'service_end': '2026-12-31',
                }).json()['item']
                client.post(f"/api/bills/{bill['id']}/approve", json={})
                if paid:
                    response = client.post('/api/payments', json={
                        'bill_id': bill['id'], 'amount': paid, 'method': 'cash',
                        'idempotency_key': f"REPORT-BREAKDOWN-{building}-{unit}-{room}-{fee['id']}",
                    })
                    self.assertEqual(response.status_code, 200)

            seed('A座', '一层', 'A101', 100, property_fee, 50)
            seed('B座', '二层', 'B201', 300, property_fee, 600)
            seed('B座', '二层', 'B202', 1, parking_fee, 0)

            api = client.get('/api/reports/breakdown?period=2026-12')
            self.assertEqual(api.status_code, 200)
            data = api.json()
            self.assertEqual(data['by_building'], [
                {'name': 'A座', 'bill_count': 1, 'bill_amount_total': 200.0, 'payment_amount_total': 50.0, 'unpaid_amount_total': 150.0},
                {'name': 'B座', 'bill_count': 2, 'bill_amount_total': 680.0, 'payment_amount_total': 600.0, 'unpaid_amount_total': 80.0},
            ])
            self.assertEqual(data['by_fee_type'], [
                {'name': '物业费', 'bill_count': 2, 'bill_amount_total': 800.0, 'payment_amount_total': 650.0, 'unpaid_amount_total': 150.0},
                {'name': '车位费', 'bill_count': 1, 'bill_amount_total': 80.0, 'payment_amount_total': 0.0, 'unpaid_amount_total': 80.0},
            ])
            self.assertEqual(data['by_category'], [
                {'name': '商户', 'bill_count': 3, 'bill_amount_total': 880.0, 'payment_amount_total': 650.0, 'unpaid_amount_total': 230.0},
            ])
            self.assertEqual(data['by_unit'], [
                {'name': '一层', 'bill_count': 1, 'bill_amount_total': 200.0, 'payment_amount_total': 50.0, 'unpaid_amount_total': 150.0},
                {'name': '二层', 'bill_count': 2, 'bill_amount_total': 680.0, 'payment_amount_total': 600.0, 'unpaid_amount_total': 80.0},
            ])

            page = client.get('/backoffice/reports?period=2026-12')
            self.assertEqual(page.status_code, 200)
            for text in ['按楼栋 / 区域汇总', '按单元 / 分区汇总', '按收费项目汇总', '按收费对象分类汇总', 'A座', 'B座', '一层', '二层', '物业费', '车位费', '商户', '680.0', '650.0']:
                self.assertIn(text, page.text)

    def test_report_breakdown_can_export_grouped_summary_csv(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, tenant_name='A汇总导出物业', project_name='A汇总导出项目')
            fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
            target = client.post('/api/charge-targets', json={
                'building': 'A座', 'unit': '一层', 'room_number': 'A101', 'category': '商户', 'area': 100,
            }).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-01',
                'service_start': '2027-01-01', 'service_end': '2027-01-31',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 80, 'method': 'cash', 'idempotency_key': 'REPORT-BREAKDOWN-EXPORT-A',
            })

            page = client.get('/backoffice/reports?period=2027-01')
            self.assertEqual(page.status_code, 200)
            self.assertIn('/api/exports/reports/breakdown.csv?period=2027-01', page.text)

            exported = client.get('/api/exports/reports/breakdown.csv?period=2027-01')
            self.assertEqual(exported.status_code, 200)
            data = exported.json()
            self.assertEqual(data['filename'], 'report-breakdown-2027-01.csv')
            content = data['content']
            self.assertIn('group_type,name,bill_count,bill_amount_total,payment_amount_total,unpaid_amount_total', content)
            for text in ['building,A座,1,200.0,80.0,120.0', 'unit,一层,1,200.0,80.0,120.0', 'fee_type,物业费,1,200.0,80.0,120.0', 'category,商户,1,200.0,80.0,120.0']:
                self.assertIn(text, content)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
                self.assertNotIn(hidden, content)

            client_b = self._client(db_url, tenant_name='B汇总导出物业', project_name='B汇总导出项目')
            other = client_b.get('/api/exports/reports/breakdown.csv?period=2027-01')
            self.assertEqual(other.status_code, 200)
            self.assertNotIn('A座', other.json()['content'])


if __name__ == '__main__':
    unittest.main()
