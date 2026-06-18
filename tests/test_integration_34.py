#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 34."""

from tests.integration_base import *


class TestIntegration34(IntegrationTestBase):
    def test_missing_user_edit_redirects_instead_of_dropping_connection(self):
        status, body = http_get('/users/999999/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 302)


    def test_users_page_guides_first_run_roles_without_cloud_registration(self):
        status, body = http_get('/users', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('首次账号设置建议', body)
        self.assertIn('财务：资料维护', body)
        self.assertIn('客服业务编辑：业主、收费对象、合同、抄表、导入和催缴', body)


    def test_large_bill_volume_pages_remain_paginated_and_accessible(self):
        import server.db as db_module

        db = db_module.get_db()
        fee_ids = [r['id'] for r in db.execute("SELECT id FROM fee_types WHERE is_active=1 ORDER BY sort_order LIMIT 6").fetchall()]
        period = '2036-06'
        db.execute('BEGIN')
        for i in range(350):
            owner_id = db.execute(
                "INSERT INTO owners(name,phone) VALUES(?,?)",
                (f'规模商户{i:04d}', f'139{i:08d}'[:11])
            ).lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
                (f'S{i % 8 + 1:02d}', 'A座', f'{700 + i // 100}{i % 100:02d}', 7 + i % 20, '商户', 60 + i % 120, owner_id)
            ).lastrowid
            for month in range(1, 7):
                bill_period = f'2036-{month:02d}'
                for fee_id in fee_ids:
                    status_value = 'paid' if (i + fee_id) % 6 == 0 else 'unpaid'
                    db.execute(
                        "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
                        (room_id, owner_id, fee_id, bill_period, 100 + fee_id + i % 50, bill_period + '-28', status_value, f'SCALEHTTP_{room_id}_{fee_id}_{bill_period}')
                    )
        db.commit()
        total = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period=?", (period,)).fetchone()[0]
        db.close()

        status, bills_html = http_get(f'/bills?period={period}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('共 ' + str(total) + ' 条', bills_html)
        self.assertIn('第 1 / ', bills_html)
        self.assertIn('每页 50 条', bills_html)
        self.assertIn('首页', bills_html)
        self.assertIn('下一页', bills_html)
        self.assertIn('尾页', bills_html)
        self.assertIn('page-ellipsis', bills_html)
        self.assertIn('name="per_page"', bills_html)
        self.assertIn('name="page"', bills_html)
        self.assertIn('规模商户', bills_html)

        status, page5 = http_get(f'/bills?period={period}&page=5&per_page=100&building=S03&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('每页 100 条', page5)
        self.assertIn('第 3 / 3 页', page5)
        self.assertIn('building=S03', page5)
        self.assertIn('status=unpaid', page5)
        self.assertIn('per_page=100', page5)

        status, filtered_html = http_get(f'/bills?period={period}&building=S03&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('S03', filtered_html)
        self.assertIn('未缴', filtered_html)

        status, reports_html = http_get(f'/reports?period={period}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('楼栋对账统计', reports_html)
        self.assertIn('账期对账', reports_html)

    def test_payments_page_uses_reusable_pagination_and_preserves_filters(self):
        import server.db as db_module

        db = db_module.get_db()
        fee_id = db.execute("SELECT id FROM fee_types WHERE is_active=1 ORDER BY sort_order LIMIT 1").fetchone()['id']
        period = '2037-01'
        db.execute('BEGIN')
        for i in range(130):
            owner_id = db.execute(
                "INSERT INTO owners(name,phone) VALUES(?,?)",
                (f'缴费分页业主{i:03d}', f'13877{i:06d}'[:11]),
            ).lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
                ('缴费分页楼', 'B座', f'P{i:03d}', 8, '商户', 80, owner_id, f'缴费分页租户{i:03d}'),
            ).lastrowid
            bill_id = db.execute(
                "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
                (room_id, owner_id, fee_id, period, 10 + i, period + '-28', 'paid', f'PAYPAGE-{i:03d}'),
            ).lastrowid
            db.execute(
                "INSERT INTO payments(bill_id,amount_paid,payment_date,payment_method,operator,receipt_number) VALUES(?,?,?,?,?,?)",
                (bill_id, 10 + i, period + '-15', 'cash', '分页收费员', f'R-PAYPAGE-{i:03d}'),
            )
        db.commit()
        db.close()

        query = urllib.parse.urlencode({'keyword': '缴费分页', 'method': 'cash', 'operator': '分页收费员'})
        status, body = http_get('/payments?' + query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 130 条 / 3 页 / 每页 50 条', body)
        self.assertIn('缴费记录分页', body)
        self.assertIn('name="per_page"', body)
        self.assertIn('method=cash', body)
        self.assertIn('operator=%E5%88%86%E9%A1%B5%E6%94%B6%E8%B4%B9%E5%91%98', body)

        page_query = urllib.parse.urlencode({'keyword': '缴费分页', 'method': 'cash', 'operator': '分页收费员', 'page': '9', 'per_page': '100'})
        status, page3 = http_get('/payments?' + page_query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 130 条 / 2 页 / 每页 100 条', page3)
        self.assertIn('value="2"', page3)
        self.assertIn('R-PAYPAGE-', page3)

    def test_rooms_and_owners_pages_paginate_master_data(self):
        import server.db as db_module

        db = db_module.get_db()
        db.execute('BEGIN')
        for i in range(125):
            owner_id = db.execute(
                "INSERT INTO owners(name,phone) VALUES(?,?)",
                (f'分页档案业主{i:03d}', f'13666{i:06d}'[:11]),
            ).lastrowid
            db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
                ('分页档案楼', '商场', f'R{i:03d}', 1, '商户', 30 + i, owner_id, f'分页档案租户{i:03d}'),
            )
        db.commit()
        db.close()

        room_query = urllib.parse.urlencode({'building': '分页档案楼', 'category': '商户', 'keyword': '分页档案'})
        status, rooms_html = http_get('/rooms?' + room_query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 125 条 / 3 页 / 每页 50 条', rooms_html)
        self.assertIn('收费对象分页', rooms_html)
        self.assertIn('building=%E5%88%86%E9%A1%B5%E6%A1%A3%E6%A1%88%E6%A5%BC', rooms_html)

        status, rooms_page2 = http_get('/rooms?' + room_query + '&page=2&per_page=100', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 125 条 / 2 页 / 每页 100 条', rooms_page2)
        self.assertIn('value="2"', rooms_page2)

        owner_query = urllib.parse.urlencode({'keyword': '分页档案业主'})
        status, owners_html = http_get('/owners?' + owner_query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 125 条 / 3 页 / 每页 50 条', owners_html)
        self.assertIn('业主分页', owners_html)
        self.assertIn('keyword=%E5%88%86%E9%A1%B5%E6%A1%A3%E6%A1%88%E4%B8%9A%E4%B8%BB', owners_html)

    def test_rooms_page_keeps_peer_units_visible_across_pagination(self):
        import server.db as db_module

        db = db_module.get_db()
        db.execute('BEGIN')
        for i in range(150):
            owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", (f'同级分页B座业主{i:03d}', '13600000000')).lastrowid
            db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
                ('同级分页楼', 'B座', f'B{i:03d}', 3, '居民', 60, owner_id, f'同级分页B座租户{i:03d}'),
            )
        for i in range(3):
            owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", (f'同级分页商场业主{i:03d}', '13700000000')).lastrowid
            db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
                ('同级分页楼', '商场', f'S{i:03d}', 1, '商户', 45, owner_id, f'同级分页商场租户{i:03d}'),
            )
        db.commit()
        db.close()

        query = urllib.parse.urlencode({'building': '同级分页楼'})
        status, body = http_get('/rooms?' + query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('B座 · ', body)
        self.assertIn('商场 · ', body)
        self.assertIn('当前筛选共 153 条 / 4 页 / 每页 50 条', body)
        self.assertIn('同级分页商场租户', body)

    def test_bills_page_keeps_peer_areas_visible_across_pagination(self):
        import server.db as db_module

        db = db_module.get_db()
        fee_id = db.execute("SELECT id FROM fee_types WHERE is_active=1 ORDER BY sort_order LIMIT 1").fetchone()['id']
        db.execute('BEGIN')
        for i in range(150):
            owner_id = db.execute(
                "INSERT INTO owners(name,phone) VALUES(?,?)",
                (f'账单同级B座业主{i:03d}', '13600000000'),
            ).lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
                ('账单同级楼', 'B座', f'B{i:03d}', 3, '居民', 60, owner_id, f'账单同级B座租户{i:03d}'),
            ).lastrowid
            db.execute(
                "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
                (room_id, owner_id, fee_id, '2040-01', 100 + i, '2040-01-31', 'unpaid', f'PEER-BILL-B-{i:03d}'),
            )
        for i in range(3):
            space_id = db.execute(
                "INSERT INTO commercial_spaces(space_no,floor,area,shop_name,merchant_name,business_type,status) VALUES(?,?,?,?,?,?,?)",
                (f'PEER-S-{i:03d}', 1, 45, f'账单同级商铺{i:03d}', f'账单同级商户{i:03d}', '零售', 'active'),
            ).lastrowid
            db.execute(
                "INSERT INTO bills(commercial_space_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?)",
                (space_id, fee_id, '2040-01', 300 + i, '2040-01-31', 'unpaid', f'PEER-BILL-S-{i:03d}'),
            )
        db.commit()
        db.close()

        query = urllib.parse.urlencode({'period_start': '2040-01-01', 'period_end': '2040-01-31'})
        status, body = http_get('/bills?' + query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 153 条 / 4 页 / 每页 50 条', body)
        self.assertIn('账单同级商户', body)
        self.assertIn('账单同级B座租户', body)

    def test_merchant_contracts_and_spaces_paginate_commercial_master_data(self):
        import server.db as db_module

        db = db_module.get_db()
        db.execute('BEGIN')
        for i in range(115):
            space_id = db.execute(
                "INSERT INTO commercial_spaces(space_no,floor,area,shop_name,merchant_name,business_type,water_rate_type,status) VALUES(?,?,?,?,?,?,?,?)",
                (f'PAGE-S-{i:03d}', 1, 40 + i, f'分页商铺{i:03d}', f'分页商户{i:03d}', '零售', '非居民', 'active'),
            ).lastrowid
            db.execute(
                "INSERT INTO merchant_contracts(commercial_space_id,contract_no,merchant_name,shop_name,rent_amount,rent_cycle,property_rate,property_cycle,deposit_amount,contract_area,start_date,end_date,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (space_id, f'PAGE-C-{i:03d}', f'分页商户{i:03d}', f'分页商铺{i:03d}', 1000 + i, 'monthly', 4.5, 'monthly', 3000, 40 + i, '2038-01-01', '2038-12-31', 'active'),
            )
        db.commit()
        db.close()

        contract_query = urllib.parse.urlencode({'keyword': '分页商户'})
        status, contracts_html = http_get('/merchant_contracts?' + contract_query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 115 条 / 3 页 / 每页 50 条', contracts_html)
        self.assertIn('合同档案分页', contracts_html)
        self.assertIn('PAGE-C-', contracts_html)

        status, contracts_page2 = http_get('/merchant_contracts?' + contract_query + '&page=9&per_page=100', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 115 条 / 2 页 / 每页 100 条', contracts_page2)
        self.assertIn('value="2"', contracts_page2)

        space_query = urllib.parse.urlencode({'keyword': '分页商铺'})
        status, spaces_html = http_get('/commercial_spaces?' + space_query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 115 条 / 3 页 / 每页 50 条', spaces_html)
        self.assertIn('商铺档案分页', spaces_html)
        self.assertIn('PAGE-S-', spaces_html)

    def test_merchant_contracts_page_keeps_peer_contract_groups_visible_across_pagination(self):
        import server.db as db_module

        db = db_module.get_db()
        db.execute('BEGIN')
        for i in range(150):
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,tenant_name) VALUES(?,?,?,?,?,?,?)",
                ('合同同级楼', 'B座', f'B{i:03d}', 5, '商户', 80, f'合同同级B座租户{i:03d}'),
            ).lastrowid
            db.execute(
                "INSERT INTO merchant_contracts(room_id,contract_no,merchant_name,shop_name,rent_amount,rent_cycle,property_rate,property_cycle,deposit_amount,contract_area,start_date,end_date,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (room_id, f'PEER-CONTRACT-B-{i:03d}', f'合同同级B座商户{i:03d}', f'合同同级B座店铺{i:03d}', 1000, 'monthly', 4.5, 'monthly', 3000, 80, '2040-01-01', '2040-12-31', 'active'),
            )
        for i in range(3):
            space_id = db.execute(
                "INSERT INTO commercial_spaces(space_no,floor,area,shop_name,merchant_name,business_type,status) VALUES(?,?,?,?,?,?,?)",
                (f'PEER-CONTRACT-S-{i:03d}', 1, 45, f'合同同级商业店铺{i:03d}', f'合同同级商业商户{i:03d}', '零售', 'active'),
            ).lastrowid
            db.execute(
                "INSERT INTO merchant_contracts(commercial_space_id,contract_no,merchant_name,shop_name,rent_amount,rent_cycle,property_rate,property_cycle,deposit_amount,contract_area,start_date,end_date,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (space_id, f'PEER-CONTRACT-S-{i:03d}', f'合同同级商业商户{i:03d}', f'合同同级商业店铺{i:03d}', 1000, 'monthly', 4.5, 'monthly', 3000, 45, '2040-01-01', '2040-12-31', 'active'),
            )
        db.commit()
        db.close()

        query = urllib.parse.urlencode({'keyword': '合同同级'})
        status, body = http_get('/merchant_contracts?' + query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 153 条 / 4 页 / 每页 50 条', body)
        self.assertIn('B座合同', body)
        self.assertIn('商业合同', body)
        self.assertIn('合同同级商业商户', body)
        self.assertIn('合同同级B座商户', body)

    def test_meter_readings_page_paginate_records_and_preserves_filters(self):
        import server.db as db_module

        db = db_module.get_db()
        fee_id = db.execute("SELECT id FROM fee_types WHERE calc_method='meter' AND is_active=1 ORDER BY sort_order LIMIT 1").fetchone()['id']
        db.execute('BEGIN')
        for i in range(112):
            owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", (f'抄表分页业主{i:03d}', '13500000000')).lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
                ('抄表分页楼', 'B座', f'M{i:03d}', 3, '商户', 20, owner_id, f'抄表分页租户{i:03d}'),
            ).lastrowid
            db.execute(
                "INSERT INTO meter_readings(room_id,fee_type_id,period,previous_reading,current_reading,consumption,reading_date,status) VALUES(?,?,?,?,?,?,?,?)",
                (room_id, fee_id, '203902', i, i + 10, 10, '2039-02-10', 'draft'),
            )
        db.commit()
        db.close()

        query = urllib.parse.urlencode({'period': '2039-02-01', 'status': 'draft', 'keyword': '抄表分页', 'fee_type_id': str(fee_id)})
        status, body = http_get('/meter_readings?' + query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 112 条 / 3 页 / 每页 50 条', body)
        self.assertIn('抄表分页', body)
        self.assertIn('抄表分页楼', body)
        self.assertIn('fee_type_id=' + str(fee_id), body)

    def test_collections_and_reminders_paginate_grouped_worklists(self):
        import server.db as db_module

        db = db_module.get_db()
        fee_id = db.execute("SELECT id FROM fee_types WHERE is_active=1 ORDER BY sort_order LIMIT 1").fetchone()['id']
        db.execute('BEGIN')
        for i in range(118):
            owner_id = db.execute(
                "INSERT INTO owners(name,phone) VALUES(?,?)",
                (f'分组分页业主{i:03d}', f'13777{i:06d}'[:11]),
            ).lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
                ('分组分页楼', 'B座', f'G{i:03d}', 5, '居民', 70, owner_id, f'分组分页租户{i:03d}'),
            ).lastrowid
            db.execute(
                "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
                (room_id, owner_id, fee_id, '2026-05', 1200 + i, '2026-05-01', 'unpaid', f'GROUPPAGE-{i:03d}'),
            )
        db.commit()
        db.close()

        collection_query = urllib.parse.urlencode({'building': '分组分页楼', 'period_start': '2026-05-01', 'period_end': '2026-05-31'})
        status, collections_html = http_get('/collections?' + collection_query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 118 条 / 3 页 / 每页 50 条', collections_html)
        self.assertIn('客服催收分页', collections_html)
        self.assertIn('分组分页楼', collections_html)

        reminder_query = urllib.parse.urlencode({'building': '分组分页楼', 'period_start': '2026-05-01', 'period_end': '2026-05-31', 'keyword': '分组分页'})
        status, reminders_html = http_get('/reminders?' + reminder_query, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前筛选共 118 条 / 3 页 / 每页 50 条', reminders_html)
        self.assertIn('催缴分页', reminders_html)
        self.assertIn('keyword=%E5%88%86%E7%BB%84%E5%88%86%E9%A1%B5', reminders_html)


    def test_projects_api_lists_default_project(self):
        status, body = http_get('/api/v1/projects', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        items = json.loads(body)['data']['items']
        self.assertTrue(any(item['code'] == 'default' and item['name'] == '默认项目' for item in items))

        default_id = next(item['id'] for item in items if item['code'] == 'default')
        status, body = http_get(f'/api/v1/projects/{default_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['data']['code'], 'default')


    def test_api_v1_requires_auth_and_returns_json_error(self):
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/api/v1/owners/1')
        resp = conn.getresponse()
        body = resp.read().decode('utf-8')
        content_type = resp.getheader('Content-Type', '')
        conn.close()

        self.assertEqual(resp.status, 401)
        self.assertIn('application/json', content_type)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'unauthorized')


    def test_api_v1_owner_room_and_bill_readonly_details(self):
        import server.db as db_module

        db = db_module.get_db()
        owner_id = db.execute(
            "INSERT INTO owners(name,phone,id_card) VALUES(?,?,?)",
            ('接口业主', '13800138001', '610100199002021111'),
        ).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('API座', '1单元', '2201', 22, '商户', 66.6, owner_id),
        ).lastrowid
        fee_type_id = db.execute(
            "INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)",
            ('接口测试费', 'fixed', 200.0),
        ).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_type_id, '2026-09', 200.0, '2026-09-30', 'unpaid', 'API-BILL-1'),
        ).lastrowid
        db.execute(
            "INSERT INTO payments(bill_id,amount_paid,payment_date,payment_method,operator) "
            "VALUES(?,?,datetime('now','localtime'),?,?)",
            (bill_id, 50.0, 'cash', 'admin'),
        )
        db.commit()
        db.close()

        status, owner_body = http_get(f'/api/v1/owners/{owner_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        owner_payload = json.loads(owner_body)
        self.assertTrue(owner_payload['ok'])
        self.assertEqual(owner_payload['data']['name'], '接口业主')
        self.assertEqual(owner_payload['data']['id_card_masked'], '610100********1111')
        self.assertNotIn('id_card', owner_payload['data'])

        status, room_body = http_get(f'/api/v1/rooms/{room_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        room_payload = json.loads(room_body)
        self.assertEqual(room_payload['data']['room_number'], '2201')
        self.assertEqual(room_payload['data']['owner']['name'], '接口业主')

        status, bill_body = http_get(f'/api/v1/bills/{bill_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        bill_payload = json.loads(bill_body)
        self.assertEqual(bill_payload['data']['bill_number'], 'API-BILL-1')
        self.assertEqual(bill_payload['data']['amount'], '200.00')
        self.assertEqual(bill_payload['data']['paid_amount'], '50.00')
        self.assertEqual(bill_payload['data']['unpaid_amount'], '150.00')

        db = db_module.get_db()
        db.execute('DELETE FROM payments WHERE bill_id=?', (bill_id,))
        db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
        db.execute('DELETE FROM fee_types WHERE id=?', (fee_type_id,))
        db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
        for table_name in ('payments', 'bills', 'fee_types', 'rooms', 'owners'):
            remaining = db.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
            if remaining == 0:
                db.execute('DELETE FROM sqlite_sequence WHERE name=?', (table_name,))
        db.commit()
        db.close()


    def test_api_v1_payment_preview_requires_auth_and_returns_json_error(self):
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'bill_id': '1', 'amount': '10.00'})
        conn.request('POST', '/api/v1/payments/preview', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        body = resp.read().decode('utf-8')
        content_type = resp.getheader('Content-Type', '')
        conn.close()

        self.assertEqual(resp.status, 401)
        self.assertIn('application/json', content_type)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'unauthorized')


    def test_api_v1_payment_preview_returns_impact_without_writing_payment(self):
        import server.db as db_module

        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", ('预览业主', '13800138002')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('PREVIEW座', '1单元', '2301', 23, '商户', 70, owner_id),
        ).lastrowid
        fee_type_id = db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", ('预览测试费', 'fixed', 120)).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_type_id, '2026-10', 120, '2026-10-31', 'unpaid', 'API-PREVIEW-1'),
        ).lastrowid
        db.commit()
        before = db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (bill_id,)).fetchone()[0]
        db.close()

        status, body, _ = http_post('/api/v1/payments/preview', {
            'bill_id': str(bill_id),
            'amount': '40.00',
            'method': 'cash',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['amount'], '40.00')
        self.assertEqual(payload['data']['unpaid_before'], '120.00')
        self.assertEqual(payload['data']['unpaid_after'], '80.00')
        self.assertFalse(payload['data']['will_mark_paid'])

        db = db_module.get_db()
        after = db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (bill_id,)).fetchone()[0]
        self.assertEqual(before, after)
        db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
        db.execute('DELETE FROM fee_types WHERE id=?', (fee_type_id,))
        db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
        for table_name in ('payments', 'bills', 'fee_types', 'rooms', 'owners'):
            remaining = db.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
            if remaining == 0:
                db.execute('DELETE FROM sqlite_sequence WHERE name=?', (table_name,))
        db.commit()
        db.close()
