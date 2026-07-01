#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 02."""

from tests.integration_base import *


class TestIntegration02(IntegrationTestBase):
    def test_vendor_assets_are_served_locally(self):
        assets = {
            '/static/vendor/bootstrap/bootstrap.min.css': 'text/css',
            '/static/vendor/bootstrap/bootstrap.bundle.min.js': 'application/javascript',
            '/static/vendor/bootstrap-icons/bootstrap-icons.min.css': 'text/css',
            '/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2': 'application/octet-stream',
            '/static/vendor/chart/chart.umd.min.js': 'application/javascript',
        }
        for path, expected_type in assets.items():
            conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
            conn.request('GET', path)
            resp = conn.getresponse()
            data = resp.read()
            content_type = resp.getheader('Content-Type', '')
            conn.close()
            self.assertEqual(resp.status, 200, path)
            self.assertIn(expected_type, content_type, path)
            self.assertGreater(len(data), 1000, path)


    def test_readonly_user_cannot_create_room(self):
        username = 'readonly_test'
        http_post('/users/create', {
            'username': username,
            'password': 'readonly123',
            'display_name': '只读测试',
            'role': 'readonly',
            'is_active': 'on',
        }, self.cookie, TEST_PORT)

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': username, 'password': 'readonly123'})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        resp.read()
        readonly_cookie = resp.getheader('Set-Cookie', '').split(';')[0]
        conn.close()

        status, body, loc = http_post('/rooms/create', {
            'building': 'READONLY-BLD', 'unit': 'A座', 'room_number': 'R001',
            'floor': '1', 'category': '居民', 'area': '10',
        }, readonly_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        _, body = http_get('/rooms?keyword=READONLY-BLD', self.cookie, TEST_PORT)
        self.assertNotIn('R001', body)


    def test_rooms_page_supports_batch_delete_selection(self):
        import server.db as db_module
        db = db_module.get_db()
        keep_id = db.execute("INSERT INTO rooms(building,unit,room_number,floor,category,area) VALUES(?,?,?,?,?,?)", ('BATCHDEL', 'A座', 'KEEP', 1, '居民', 10)).lastrowid
        delete_id = db.execute("INSERT INTO rooms(building,unit,room_number,floor,category,area) VALUES(?,?,?,?,?,?)", ('BATCHDEL', 'A座', 'DEL', 1, '居民', 10)).lastrowid
        db.commit(); db.close()
        try:
            status, body = http_get('/rooms?keyword=BATCHDEL', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn('name="room_ids"', body)
            self.assertIn('/rooms/batch_delete', body)
            self.assertIn('批量删除', body)

            status, _, loc = http_post('/rooms/batch_delete', {'room_ids': str(delete_id)}, self.cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('/rooms?flash=', loc)

            db = db_module.get_db()
            keep = db.execute('SELECT COUNT(*) FROM rooms WHERE id=?', (keep_id,)).fetchone()[0]
            gone = db.execute('SELECT COUNT(*) FROM rooms WHERE id=?', (delete_id,)).fetchone()[0]
            db.execute('DELETE FROM rooms WHERE id=?', (keep_id,))
            db.commit(); db.close()
            self.assertEqual(keep, 1)
            self.assertEqual(gone, 0)
        finally:
            db = db_module.get_db()
            db.execute("DELETE FROM rooms WHERE building='BATCHDEL'")
            db.commit(); db.close()


    def test_rooms_page_groups_rows_by_unit_and_search_keeps_matching_group_open(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("INSERT INTO rooms(building,unit,room_number,floor,category,area,tenant_name,business_type) VALUES(?,?,?,?,?,?,?,?)", ('GROUPROOM', 'B座', '1401', 14, '居民', 88, '普通租户', '住宅'))
        db.execute("INSERT INTO rooms(building,unit,room_number,floor,category,area,tenant_name,business_type) VALUES(?,?,?,?,?,?,?,?)", ('GROUPROOM', '商场', 'S-101', 1, '商户', 55, '搜索租户', '餐饮'))
        db.commit(); db.close()
        try:
            status, body = http_get('/rooms?building=GROUPROOM', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn('class="room-unit-group"', body)
            self.assertIn('data-unit="B座"', body)
            self.assertIn('data-unit="商场"', body)
            self.assertIn('B座 · 1间', body)
            self.assertIn('商场 · 1间', body)
            self.assertIn('data-group-open="1"', body)
            self.assertIn('GROUPROOM', body)
            self.assertIn('1401', body)
            self.assertIn('S-101', body)
            self.assertIn('name="room_ids"', body)
            self.assertIn('/rooms/batch_delete', body)

            status, searched = http_get('/rooms?building=GROUPROOM&keyword=%E9%A4%90%E9%A5%AE', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn('class="room-unit-group"', searched)
            self.assertIn('商场 · 1间', searched)
            self.assertIn('S-101', searched)
            self.assertNotIn('1401', searched)
            self.assertIn('data-group-open="1"', searched)
        finally:
            db = db_module.get_db()
            db.execute("DELETE FROM rooms WHERE building='GROUPROOM'")
            db.commit(); db.close()


    def test_room_delete_skips_rooms_with_business_records_and_batch_delete_is_admin_only(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '删除保护业主', '13900001234')
        linked_room = create_room(db, building='SAFEDEL', unit='A座', room_number='LINKED', owner_id=owner_id)
        empty_room = create_room(db, building='SAFEDEL', unit='A座', room_number='EMPTY', owner_id=owner_id)
        bill_id = create_bill(db, room_id=linked_room, owner_id=owner_id, fee_type_id=1, period='2039-01', amount=88, status='paid')
        create_payment(db, bill_id=bill_id, amount=88, method='cash', operator='删除保护')
        db.commit(); db.close()
        try:
            operator_cookie = self._create_user_and_login('room_batch_delete_operator', 'operator123', 'operator', '批删财务')
            status, _, loc = http_post('/rooms/batch_delete', {'room_ids': str(empty_room)}, operator_cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('无权限', urllib.parse.unquote(loc))

            status, _, loc = http_post(f'/rooms/{linked_room}/delete', {}, self.cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('存在账单或抄表记录，不能删除', urllib.parse.unquote(loc))

            status, _, loc = http_post('/rooms/batch_delete', [('room_ids', str(linked_room)), ('room_ids', str(empty_room))], self.cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('已删除房间1间', urllib.parse.unquote(loc))
            self.assertIn('跳过1间有关联记录的房间', urllib.parse.unquote(loc))

            db = db_module.get_db()
            self.assertIsNotNone(db.execute('SELECT id FROM rooms WHERE id=?', (linked_room,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT id FROM bills WHERE id=?', (bill_id,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT id FROM payments WHERE bill_id=?', (bill_id,)).fetchone())
            self.assertIsNone(db.execute('SELECT id FROM rooms WHERE id=?', (empty_room,)).fetchone())
            db.close()
        finally:
            db = db_module.get_db()
            db.execute("DELETE FROM payments WHERE bill_id IN (SELECT id FROM bills WHERE room_id IN (SELECT id FROM rooms WHERE building='SAFEDEL'))")
            db.execute("DELETE FROM bills WHERE room_id IN (SELECT id FROM rooms WHERE building='SAFEDEL')")
            db.execute("DELETE FROM rooms WHERE building='SAFEDEL'")
            db.execute("DELETE FROM owners WHERE name='删除保护业主'")
            db.commit(); db.close()


    def test_fee_types_page_groups_company_sections(self):
        status, body = http_get('/fee_types', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('物业公司', body)
        self.assertIn('商业公司', body)
        self.assertIn('其他', body)

        status, body = http_get('/fee_types?group=property', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('物业费(居民)', body)
        self.assertIn('物业费(商户)', body)
        self.assertIn('电梯费', body)
        self.assertIn('二次供水运行费', body)
        self.assertIn('公摊能耗费', body)
        self.assertIn('生活垃圾费', body)
        self.assertNotIn('装修押金', body)

        status, body = http_get('/fee_types?group=commercial', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('电费(商业)', body)
        self.assertIn('装修管理费', body)
        self.assertIn('装修押金', body)
        self.assertIn('泄水费', body)
        self.assertIn('空调能源费', body)
        self.assertNotIn('物业费(居民)', body)

        status, body = http_get('/fee_types?group=other', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('垃圾清运费', body)
        self.assertIn('水费(非居民)', body)
        self.assertIn('水费(特行)', body)
        self.assertIn('停车费', body)
        self.assertIn('临时收费', body)
        self.assertNotIn('电梯费', body)


    def test_fee_type_overview_counts_match_group_detail_pages(self):
        import re

        def detail_count(group):
            status, detail = http_get(f'/fee_types?group={group}', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            return detail.count('class="card fee-card h-100"')

        expected = {
            'commercial': ('商业公司', detail_count('commercial')),
            'other': ('其他', detail_count('other')),
        }
        status, overview = http_get('/fee_types', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for label, count in expected.values():
            summary = re.search(rf'<div class="label">{label}</div><strong>(\d+)</strong>', overview)
            self.assertIsNotNone(summary)
            self.assertEqual(int(summary.group(1)), count)
            card = re.search(rf'<div class="label"><i class="bi [^"]+"></i> {label}</div><strong>(\d+) 项</strong>', overview)
            self.assertIsNotNone(card)
            self.assertEqual(int(card.group(1)), count)


    def test_room_form_explains_unit_category_and_business_type(self):
        status, body = http_get('/rooms/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('单元/区域', body)
        self.assertIn('房间类型', body)
        self.assertIn('商业', body)
        room_type_select = body.split('name="category"', 1)[1].split('</select>', 1)[0]
        self.assertNotIn('<option value="非居民"', room_type_select)
        self.assertNotIn('<option value="特行"', room_type_select)
        self.assertIn('非居民/特行只是水费档位', body)
        self.assertIn('水费标准', body)
        self.assertIn('value="特行"', body)
        self.assertIn('业态/商户类别', body)
        self.assertIn('餐饮、零售、美容、办公', body)
        self.assertIn('value="yearly"', body)
        self.assertIn('年付', body)


    def test_rooms_list_filters_all_commercial_categories_and_searches_business_type(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '业态统计业主', '13900000002')
        create_room(db, building='金莎国际', unit='商场', room_number='Y101', category='商业', owner_id=owner_id)
        db.execute("UPDATE rooms SET business_type='餐饮' WHERE room_number='Y101'")
        db.commit(); db.close()

        status, body = http_get('/rooms?category=%E5%95%86%E4%B8%9A', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('Y101', body)
        self.assertIn('餐饮', body)

        status, body = http_get('/rooms?keyword=%E9%A4%90%E9%A5%AE', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('Y101', body)
