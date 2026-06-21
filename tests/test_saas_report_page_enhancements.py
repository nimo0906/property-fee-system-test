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
            self.assertIn('欠费最高区域', page.text)
            self.assertIn('5栋：欠费250.0，欠费率62.50%', page.text)
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
                {'name': 'A座', 'bill_count': 1, 'bill_amount_total': 200.0, 'payment_amount_total': 50.0, 'unpaid_amount_total': 150.0, 'collection_rate': '25.00%', 'arrears_rate': '75.00%'},
                {'name': 'B座', 'bill_count': 2, 'bill_amount_total': 680.0, 'payment_amount_total': 600.0, 'unpaid_amount_total': 80.0, 'collection_rate': '88.24%', 'arrears_rate': '11.76%'},
            ])
            self.assertEqual(data['by_fee_type'], [
                {'name': '物业费', 'bill_count': 2, 'bill_amount_total': 800.0, 'payment_amount_total': 650.0, 'unpaid_amount_total': 150.0, 'collection_rate': '81.25%', 'arrears_rate': '18.75%'},
                {'name': '车位费', 'bill_count': 1, 'bill_amount_total': 80.0, 'payment_amount_total': 0.0, 'unpaid_amount_total': 80.0, 'collection_rate': '0.00%', 'arrears_rate': '100.00%'},
            ])
            self.assertEqual(data['by_category'], [
                {'name': '商户', 'bill_count': 3, 'bill_amount_total': 880.0, 'payment_amount_total': 650.0, 'unpaid_amount_total': 230.0, 'collection_rate': '73.86%', 'arrears_rate': '26.14%'},
            ])
            self.assertEqual(data['by_unit'], [
                {'name': '一层', 'bill_count': 1, 'bill_amount_total': 200.0, 'payment_amount_total': 50.0, 'unpaid_amount_total': 150.0, 'collection_rate': '25.00%', 'arrears_rate': '75.00%'},
                {'name': '二层', 'bill_count': 2, 'bill_amount_total': 680.0, 'payment_amount_total': 600.0, 'unpaid_amount_total': 80.0, 'collection_rate': '88.24%', 'arrears_rate': '11.76%'},
            ])

            page = client.get('/backoffice/reports?period=2026-12')
            self.assertEqual(page.status_code, 200)
            for text in ['按楼栋 / 区域汇总', '按单元 / 分区汇总', '按收费项目汇总', '按收费对象分类汇总', 'A座', 'B座', '一层', '二层', '物业费', '车位费', '商户', '680.0', '650.0', '88.24%', '25.00%', '欠费率', '75.00%', '11.76%']:
                self.assertIn(text, page.text)
            self.assertIn('欠费最高单元/分区', page.text)
            self.assertIn('一层：欠费150.0，欠费率75.00%', page.text)
            self.assertIn('欠费最高收费项目', page.text)
            self.assertIn('物业费：欠费150.0，欠费率18.75%', page.text)
            self.assertIn('欠费最高对象分类', page.text)
            self.assertIn('商户：欠费230.0，欠费率26.14%', page.text)

    def test_report_breakdown_api_fallback_returns_real_group_totals(self):
        client = TestClient(create_app())
        client.post('/api/auth/login', json={
            'tenant_name': '内存报表物业', 'project_name': '内存报表项目', 'username': 'finance', 'role_code': 'finance'
        })
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
        target = client.post('/api/charge-targets', json={
            'building': 'A座', 'unit': '一层', 'room_number': 'A101', 'category': '商户', 'area': 100,
        }).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-08',
            'service_start': '2026-08-01', 'service_end': '2026-08-31',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve", json={})
        client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': 80, 'method': 'cash', 'idempotency_key': 'API-BREAKDOWN-1'
        })

        response = client.get('/api/reports/breakdown?period=2026-08')

        self.assertEqual(response.status_code, 200)
        expected = {'name': 'A座', 'bill_count': 1, 'bill_amount_total': 200.0, 'payment_amount_total': 80.0, 'unpaid_amount_total': 120.0, 'collection_rate': '40.00%', 'arrears_rate': '60.00%'}
        self.assertEqual(response.json()['by_building'], [expected])
        self.assertEqual(response.json()['by_unit'], [{**expected, 'name': '一层'}])
        self.assertEqual(response.json()['by_fee_type'], [{**expected, 'name': '物业费'}])
        self.assertEqual(response.json()['by_category'], [{**expected, 'name': '商户'}])

    def test_report_page_shows_top_arrears_bill_details_with_bill_filter_links(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, tenant_name='A欠费明细物业', project_name='A欠费明细项目')
            fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 1}).json()['item']

            def seed(room, due, paid):
                target = client.post('/api/charge-targets', json={
                    'building': '欠费区', 'unit': '一层', 'room_number': room, 'category': '商户', 'area': due,
                    'shop_name': f'{room}店', 'tenant_name': f'{room}承租人',
                }).json()['item']
                bill = client.post('/api/bills/generate', json={
                    'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-04',
                    'service_start': '2027-04-01', 'service_end': '2027-04-30',
                }).json()['item']
                client.post(f"/api/bills/{bill['id']}/approve", json={})
                if paid:
                    client.post('/api/payments', json={
                        'bill_id': bill['id'], 'amount': paid, 'method': 'cash',
                        'idempotency_key': f'REPORT-ARREARS-DETAIL-{room}',
                    })
                return bill

            seed('A101', 100, 0)
            seed('A102', 200, 50)
            seed('A103', 300, 300)

            client_b = self._client(db_url, tenant_name='B欠费明细物业', project_name='B欠费明细项目')
            other_fee = client_b.post('/api/fee-types', json={'name': '物业费', 'unit_price': 1}).json()['item']
            other_target = client_b.post('/api/charge-targets', json={
                'building': '其他区', 'unit': '二层', 'room_number': 'B201', 'category': '商户', 'area': 999,
            }).json()['item']
            other_bill = client_b.post('/api/bills/generate', json={
                'target_id': other_target['id'], 'fee_type_id': other_fee['id'], 'billing_period': '2027-04',
                'service_start': '2027-04-01', 'service_end': '2027-04-30',
            }).json()['item']
            client_b.post(f"/api/bills/{other_bill['id']}/approve", json={})

            page = client.get('/backoffice/reports?period=2027-04')

            self.assertEqual(page.status_code, 200)
            for text in ['欠费账单明细', 'A102店', 'A102承租人', 'A102', '150.0', 'A101店', 'A101承租人', '100.0']:
                self.assertIn(text, page.text)
            self.assertLess(page.text.index('A102店'), page.text.index('A101店'))
            self.assertIn('/backoffice/bills?period=2027-04', page.text)
            self.assertIn('查看账单', page.text)
            self.assertNotIn('B201', page.text)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
                self.assertNotIn(hidden, page.text)

    def test_report_arrears_bill_details_can_export_csv_with_tenant_scope(self):
        with tempfile.TemporaryDirectory() as td:
            db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
            client = self._client(db_url, tenant_name='A欠费导出物业', project_name='A欠费导出项目')
            fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 1}).json()['item']
            owner = client.post('/api/owners', json={'name': '赵催缴', 'phone': '13800138000', 'owner_type': '业主'}).json()['item']
            target = client.post('/api/charge-targets', json={
                'owner_id': owner['id'], 'building': '欠费区', 'unit': '一层', 'room_number': 'A201', 'category': '商户', 'area': 300,
                'shop_name': 'A201店', 'tenant_name': 'A201承租人',
            }).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-05',
                'service_start': '2027-05-01', 'service_end': '2027-05-31',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            client.post('/api/payments', json={
                'bill_id': bill['id'], 'amount': 80, 'method': 'cash', 'idempotency_key': 'REPORT-ARREARS-EXPORT-A',
            })

            page = client.get('/backoffice/reports?period=2027-05')
            self.assertEqual(page.status_code, 200)
            self.assertIn('/api/exports/reports/arrears-bills.csv?period=2027-05', page.text)
            self.assertIn('赵催缴 / 13800138000', page.text)

            exported = client.get('/api/exports/reports/arrears-bills.csv?period=2027-05')
            self.assertEqual(exported.status_code, 200)
            data = exported.json()
            self.assertEqual(data['filename'], 'report-arrears-bills-2027-05.csv')
            content = data['content']
            self.assertIn('bill_number,billing_period,building,unit,room_number,shop_name,tenant_name,owner_name,owner_phone,fee_name,amount,paid_amount,unpaid_amount,status', content)
            self.assertIn('owner_name,owner_phone', content)
            self.assertIn('A201店,A201承租人,赵催缴,13800138000,物业费,300.0,80.0,220.0,partial', content)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', 'idempotency_key']:
                self.assertNotIn(hidden, content)

            client_b = self._client(db_url, tenant_name='B欠费导出物业', project_name='B欠费导出项目')
            other = client_b.get('/api/exports/reports/arrears-bills.csv?period=2027-05')
            self.assertEqual(other.status_code, 200)
            self.assertNotIn('A201店', other.json()['content'])

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
            self.assertIn('group_type,name,bill_count,bill_amount_total,payment_amount_total,unpaid_amount_total,collection_rate,arrears_rate', content)
            for text in ['building,A座,1,200.0,80.0,120.0,40.00%,60.00%', 'unit,一层,1,200.0,80.0,120.0,40.00%,60.00%', 'fee_type,物业费,1,200.0,80.0,120.0,40.00%,60.00%', 'category,商户,1,200.0,80.0,120.0,40.00%,60.00%']:
                self.assertIn(text, content)
            self.assertIn('summary_building,A座,1,200.0,80.0,120.0,40.00%,60.00%', content)
            self.assertIn('summary_unit,一层,1,200.0,80.0,120.0,40.00%,60.00%', content)
            self.assertIn('summary_fee_type,物业费,1,200.0,80.0,120.0,40.00%,60.00%', content)
            self.assertIn('summary_category,商户,1,200.0,80.0,120.0,40.00%,60.00%', content)
            for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
                self.assertNotIn(hidden, content)

            client_b = self._client(db_url, tenant_name='B汇总导出物业', project_name='B汇总导出项目')
            other = client_b.get('/api/exports/reports/breakdown.csv?period=2027-01')
            self.assertEqual(other.status_code, 200)
            self.assertNotIn('A座', other.json()['content'])


if __name__ == '__main__':
    unittest.main()


def test_report_page_and_arrears_export_show_arrears_bill_and_target_counts():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = TestSaasReportPageEnhancements()._client(db_url, tenant_name='欠费户数物业', project_name='欠费户数项目')
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 1}).json()['item']

        def seed(room, due, paid):
            target = client.post('/api/charge-targets', json={
                'building': '催缴区', 'unit': '一层', 'room_number': room, 'category': '商户',
                'area': due, 'shop_name': f'{room}店', 'tenant_name': f'{room}承租人',
            }).json()['item']
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-07',
                'service_start': '2028-07-01', 'service_end': '2028-07-31',
            }).json()['item']
            client.post(f"/api/bills/{bill['id']}/approve", json={})
            if paid:
                client.post('/api/payments', json={
                    'bill_id': bill['id'], 'amount': paid, 'method': 'cash',
                    'idempotency_key': f'ARREARS-COUNT-{room}',
                })

        seed('Q101', 100, 0)
        seed('Q102', 300, 50)
        seed('Q103', 200, 200)

        page = client.get('/backoffice/reports?period=2028-07')
        exported = client.get('/api/exports/reports/arrears-bills.csv?period=2028-07')

        assert page.status_code == 200
        for text in ['欠费笔数', '2', '欠费对象数', '2', '重点催缴对象', 'Q102店 / Q102承租人：欠费250.0']:
            assert text in page.text
        assert exported.status_code == 200
        content = exported.json()['content']
        assert 'arrears_rank' in content
        assert '1,' in content
        assert content.index('Q102店') < content.index('Q101店')
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', 'idempotency_key']:
            assert hidden not in page.text
            assert hidden not in content
