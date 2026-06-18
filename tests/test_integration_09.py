#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 09."""

from tests.integration_base import *


class TestIntegration09(IntegrationTestBase):
    def test_frontdesk_menu_supports_customer_service_workflow(self):
        frontdesk_cookie = self._create_user_and_login(
            'frontdesk_menu_test', 'frontdesk123', 'frontdesk', '客服业务'
        )

        status, body = http_get('/', frontdesk_cookie, TEST_PORT)

        self.assertEqual(status, 200)
        for text in ['业主管理', '收费对象管理', '合同档案', '抄表管理', '数据导入', '催缴管理', '客服催费对象', '账单管理', '对账报表']:
            self.assertIn(text, body)
        for href in ['/billing', '/commercial_billing', '/auto_billing', '/shared_expenses', '/payments', '/invoices', '/closing', '/backups', '/users']:
            self.assertNotIn(f'href="{href}"', body)


    def test_frontdesk_can_edit_customer_master_data_but_not_delete_or_bill(self):
        import server.db as db_module
        from server.permissions import is_readonly_role, role_allows

        self.assertFalse(is_readonly_role('frontdesk'))
        self.assertTrue(role_allows('frontdesk', 'customer_service'))
        self.assertFalse(role_allows('frontdesk', 'finance'))
        self.assertFalse(role_allows('frontdesk', 'admin'))

        frontdesk_cookie = self._create_user_and_login(
            'frontdesk_write_test', 'frontdesk123', 'frontdesk', '客服业务编辑'
        )
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", ('客服可改业主', '13000000000')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('客服权限楼', 'B座', '901', 9, '居民', 80, owner_id),
        ).lastrowid
        db.commit(); db.close()
        try:
            status, _, loc = http_post(f'/rooms/{room_id}/edit', {
                'building': '客服权限楼',
                'unit': 'B座',
                'room_number': '901',
                'floor': '9',
                'category': '居民',
                'area': '88',
                'owner_id': str(owner_id),
                'owner_name': '客服已修正业主',
                'owner_phone': '13100000000',
            }, frontdesk_cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertNotIn('无权限', urllib.parse.unquote(loc))

            blocked_posts = [
                f'/rooms/{room_id}/delete',
                '/bills/generate',
                '/billing/calc',
                '/commercial_receivables/confirm',
                '/auto_billing/confirm',
                '/shared_expenses/allocate',
                '/closing/close',
            ]
            for path in blocked_posts:
                status, _, loc = http_post(path, {}, frontdesk_cookie, TEST_PORT)
                self.assertEqual(status, 302, path)
                self.assertIn('无权限', urllib.parse.unquote(loc), path)

            db = db_module.get_db()
            row = db.execute('SELECT r.area,o.name,o.phone FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id WHERE r.id=?', (room_id,)).fetchone()
            db.close()
            self.assertEqual(float(row['area']), 88.0)
            self.assertEqual(row['name'], '客服已修正业主')
            self.assertEqual(row['phone'], '13100000000')
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE name IN (?,?)', ('客服可改业主', '客服已修正业主'))
            db.commit(); db.close()


    def test_readonly_menu_is_limited_and_shows_customer_collection(self):
        readonly_cookie = self._create_user_and_login(
            'readonly_menu_test', 'readonly123', 'readonly', '客服测试'
        )

        status, body = http_get('/', readonly_cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('客服催费对象', body)
        self.assertIn('账单管理', body)
        self.assertIn('对账报表', body)
        self.assertNotIn('href="/billing"', body)
        self.assertNotIn('href="/commercial_billing"', body)
        self.assertNotIn('数据备份', body)
        self.assertNotIn('数据导入', body)
        self.assertNotIn('操作员管理', body)
        self.assertNotIn('维修管理', body)
        self.assertNotIn('停车管理', body)
        self.assertNotIn('押金管理', body)


    def test_customer_collection_page_lists_arrears_for_readonly(self):
        from server.db import get_db
        db = get_db()
        owner_id = db.execute(
            "INSERT INTO owners(name, phone) VALUES(?, ?)",
            ('催费业主', '13911112222')
        ).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id) VALUES(?,?,?,?,?,?,?)",
            ('催费楼', 'A座', '1801', 18, '商业', 88, owner_id)
        ).lastrowid
        fee_type_id = db.execute(
            "INSERT INTO fee_types(name, calc_method, unit_price, unit) VALUES(?,?,?,?)",
            ('物业服务费', 'area', 12, '元/㎡')
        ).lastrowid
        db.execute(
            "INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_type_id, '2026-03', 1500, '2026-03-31', 'unpaid', 'COLLECT_TEST_001')
        )
        db.commit(); db.close()
        readonly_cookie = self._create_user_and_login(
            'readonly_collection_test', 'readonly123', 'readonly', '客服催费'
        )

        status, body = http_get('/collections', readonly_cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('客服催费对象', body)
        self.assertIn('催费楼', body)
        self.assertIn('1801', body)
        self.assertIn('催费业主', body)
        self.assertIn('13911112222', body)
        self.assertIn('2026-03', body)
        self.assertIn('物业服务费', body)
        self.assertIn('1,500.00', body)
        self.assertIn('高', body)


    def test_customer_collection_page_uses_natural_date_range_filter(self):
        from server.db import get_db
        db = get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES(?, ?)", ('区间催费业主', '13922223333')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id) VALUES(?,?,?,?,?,?,?)",
            ('催费区间楼', 'A座', '1901', 19, '居民', 80, owner_id)
        ).lastrowid
        fee_type_id = db.execute("INSERT INTO fee_types(name, calc_method, unit_price, unit) VALUES(?,?,?,?)", ('区间物业费', 'area', 2, '元/㎡')).lastrowid
        db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, fee_type_id, '2034-05', 500, '2034-05-31', 'unpaid', 'COLLECT_RANGE_IN', '2034-05-01', '2034-05-31'))
        db.execute("""INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (room_id, owner_id, fee_type_id, '2034-07', 600, '2034-07-31', 'unpaid', 'COLLECT_RANGE_OUT', '2034-07-01', '2034-07-31'))
        db.commit(); db.close()

        status, body = http_get('/collections?period_start=2034-05-01&period_end=2034-05-31', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('name="period_start"', body)
        self.assertIn('name="period_end"', body)
        self.assertIn('2034-05-01', body)
        self.assertIn('2034-05-31', body)
        self.assertIn('2034-05', body)
        self.assertIn('500.00', body)
        self.assertNotIn('2034-07', body)
        self.assertNotIn('600.00', body)
        self.assertNotIn('name="period"', body)


    def test_readonly_cannot_post_financial_changes(self):
        readonly_cookie = self._create_user_and_login(
            'readonly_finance_test', 'readonly123', 'readonly', '客服只读'
        )

        status, body, loc = http_post('/bills/generate', {
            'period': '2026-05',
            'fee_type_id': '1',
            'due_date': '2026-05-31',
        }, readonly_cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_operator_cannot_delete_master_or_financial_records(self):
        operator_cookie = self._create_user_and_login(
            'operator_delete_guard_test', 'operator123', 'operator', '财务收费'
        )
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('权限测试业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('AUTHZ', 'A座', '1001', 10, '居民', 10, owner_id)
        ).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 1, '2027-01', 10, '2027-01-31', 'unpaid', 'AUTHZ-BILL-1')
        ).lastrowid
        db.commit(); db.close()
        try:
            for path in (f'/rooms/{room_id}/delete', f'/bills/{bill_id}/delete'):
                status, body, loc = http_post(path, {}, operator_cookie, TEST_PORT)
                self.assertEqual(status, 302)
                self.assertIn('无权限', urllib.parse.unquote(loc))
            db = db_module.get_db()
            self.assertIsNotNone(db.execute('SELECT id FROM rooms WHERE id=?', (room_id,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT id FROM bills WHERE id=?', (bill_id,)).fetchone())
            db.close()
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()


    def test_legacy_sha256_password_upgrades_after_login(self):
        import hashlib
        import server.db as db_module
        username = 'legacy_hash_user'
        legacy_hash = hashlib.sha256('legacy123'.encode()).hexdigest()
        db = db_module.get_db()
        db.execute(
            "INSERT INTO users(username,password_hash,display_name,role,is_active) VALUES(?,?,?,?,1)",
            (username, legacy_hash, '旧密码用户', 'operator')
        )
        db.commit(); db.close()

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': username, 'password': 'legacy123'})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse(); resp.read(); conn.close()

        self.assertEqual(resp.status, 302)
        db = db_module.get_db()
        upgraded = db.execute('SELECT password_hash FROM users WHERE username=?', (username,)).fetchone()['password_hash']
        db.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE username=?)', (username,))
        db.execute('DELETE FROM users WHERE username=?', (username,))
        db.commit(); db.close()
        self.assertTrue(upgraded.startswith('pbkdf2_sha256$'))


    def test_operator_menu_excludes_system_maintenance_and_high_risk_pages(self):
        operator_cookie = self._create_user_and_login(
            'operator_role_scope_test', 'operator123', 'operator', '财务权限测试'
        )

        status, body = http_get('/', operator_cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('物业收费', body)
        self.assertIn('href="/billing"', body)
        self.assertIn('商业收费', body)
        self.assertIn('href="/commercial_billing"', body)
        self.assertIn('自动出账', body)
        self.assertIn('公摊分摊', body)
        self.assertIn('发票管理', body)
        self.assertIn('期末结账', body)
        self.assertNotIn('数据备份', body)
        self.assertNotIn('操作日志', body)
        self.assertNotIn('系统健康', body)
        self.assertNotIn('系统更新', body)
        self.assertNotIn('清空', body)
        self.assertNotIn('操作员管理', body)

        for path in ['/backups', '/audit_logs', '/system_health', '/system_update', '/trial_data_reset', '/users']:
            status, _, loc = http_get_with_location(path, operator_cookie, TEST_PORT)
            self.assertEqual(status, 302, path)
            self.assertIn('无权限', urllib.parse.unquote(loc), path)


    def test_readonly_cannot_direct_access_write_modules_added_recently(self):
        readonly_cookie = self._create_user_and_login(
            'readonly_role_scope_test', 'readonly123', 'readonly', '客服权限测试'
        )

        for path in ['/billing', '/commercial_billing', '/auto_billing', '/shared_expenses', '/payments', '/invoices', '/closing', '/import']:
            status, _, loc = http_get_with_location(path, readonly_cookie, TEST_PORT)
            self.assertEqual(status, 302, path)
            self.assertIn('无权限', urllib.parse.unquote(loc), path)


    def test_readonly_job_roles_cannot_post_general_write_actions(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('新岗位只读业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('ROLE2', 'A座', '2001', 20, '居民', 90, owner_id)
        ).lastrowid
        db.commit(); db.close()
        try:
            for role in ('executive', 'readonly'):
                cookie = self._create_user_and_login(f'{role}_post_guard', 'role12345', role, role)
                status, _, loc = http_post(f'/rooms/{room_id}/edit', {
                    'building': 'ROLE2',
                    'unit': 'A座',
                    'room_number': '2001',
                    'floor': '20',
                    'category': '居民',
                    'area': '91',
                    'owner_id': str(owner_id),
                }, cookie, TEST_PORT)
                self.assertEqual(status, 302, role)
                self.assertIn('无权限', urllib.parse.unquote(loc), role)
            db = db_module.get_db()
            area = db.execute('SELECT area FROM rooms WHERE id=?', (room_id,)).fetchone()['area']
            db.close()
            self.assertEqual(float(area), 90.0)
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE username LIKE '%_post_guard')")
            db.execute("DELETE FROM users WHERE username LIKE '%_post_guard'")
            db.commit(); db.close()
