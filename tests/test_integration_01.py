#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 01."""

from tests.integration_base import *


class TestIntegration01(IntegrationTestBase):
    def test_system_update_page_renders_current_version(self):
        from server.app_version import APP_VERSION
        status, body = http_get('/system_update', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('系统更新', body)
        self.assertIn(APP_VERSION, body)
        self.assertIn('检查更新', body)
        self.assertIn('半自动更新', body)


    def test_system_update_check_uses_manifest_url_and_reports_latest_version(self):
        manifest = {
            'version': '9.9.9',
            'notes': '测试更新说明',
            'assets': {'mac': {'url': 'https://example.test/mac.zip', 'sha256': 'abc'}},
        }
        manifest_url = 'https://updates.example.test/update_manifest.json'
        with mock.patch('server.system_update.SystemUpdateService.fetch_manifest', return_value=manifest):
            status, body, loc = http_post('/system_update/check', {'manifest_url': manifest_url}, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('发现新版本', body)
        self.assertIn('9.9.9', body)
        self.assertIn('测试更新说明', body)
        self.assertIn(manifest_url, body)


    def test_system_update_page_is_admin_only(self):
        operator_cookie = self._create_user_and_login('operator_update_test', 'operator123', 'operator', '更新测试财务')
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/system_update', headers={'Cookie': operator_cookie})
        resp = conn.getresponse()
        resp.read()
        loc = resp.getheader('Location', '')
        conn.close()
        self.assertEqual(resp.status, 302)
        self.assertIn('无权限访问', urllib.parse.unquote(loc))


    def test_trial_data_reset_requires_admin_and_clears_business_data_only(self):
        import server.db as db_module
        db = db_module.get_db()
        fee_id = db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", ('保留收费项', 'fixed', 12)).lastrowid
        owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", ('清空测试业主', '13800130000')).lastrowid
        room_id = db.execute("INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)", ('RESET', 'A座', '101', 1, '居民', 10, owner_id)).lastrowid
        bill_id = db.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number) VALUES(?,?,?,?,?,?,?)", (room_id, owner_id, fee_id, '2031-01', 12, 'unpaid', 'RESET-BILL')).lastrowid
        db.execute("INSERT INTO payments(bill_id,amount_paid,payment_method,operator) VALUES(?,?,?,?)", (bill_id, 5, 'cash', 'tester'))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,status) VALUES(?,?,?,?,?)", (room_id, fee_id, '203101', 8, 'confirmed'))
        db.commit(); db.close()

        status, confirm_page = http_get('/trial_data_reset', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('清空试用业务数据', confirm_page)
        self.assertIn('会删除', confirm_page)
        self.assertIn('业主、收费对象、账单、缴费、抄表、发票、结账、公摊等业务记录', confirm_page)
        self.assertIn('不会删除', confirm_page)
        self.assertIn('操作员账号、收费项目/单价配置、备份文件、系统更新文件、程序文件', confirm_page)
        self.assertIn('执行前会自动生成数据库备份', confirm_page)
        self.assertIn('RESET', confirm_page)

        operator_cookie = self._create_user_and_login('reset_operator', 'op123456', 'operator', '清空操作员')
        status, _, loc = http_post('/trial_data_reset', {'confirm_text': 'RESET'}, operator_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_post('/trial_data_reset', {'confirm_text': 'WRONG'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('请输入RESET', urllib.parse.unquote(loc))

        before_backups = set(os.listdir(db_module.BACKUP_DIR)) if os.path.exists(db_module.BACKUP_DIR) else set()
        status, _, loc = http_post('/trial_data_reset', {'confirm_text': 'RESET'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/trial_data_reset', loc)

        db = db_module.get_db()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM owners').fetchone()[0], 0)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0], 0)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM bills').fetchone()[0], 0)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0], 0)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM meter_readings').fetchone()[0], 0)
        self.assertIsNotNone(db.execute('SELECT id FROM fee_types WHERE id=?', (fee_id,)).fetchone())
        self.assertIsNotNone(db.execute("SELECT id FROM users WHERE username='admin'").fetchone())
        db.close()
        after_backups = set(os.listdir(db_module.BACKUP_DIR))
        self.assertTrue(any(name.startswith('auto_before_trial_data_reset_') for name in after_backups - before_backups))


    def test_hidden_modules_are_not_accessible_by_direct_url(self):
        status, body = http_get('/', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for text in ['href="/repairs"', 'href="/parking"', 'href="/deposits"', '维修管理', '停车管理', '押金管理']:
            self.assertNotIn(text, body)

        for path in ['/repairs', '/repairs/create', '/repairs/1', '/parking', '/parking/create', '/parking/1/edit', '/deposits', '/deposits/create', '/deposits/1/edit', '/deposits/1/refund']:
            status, body = http_get(path, self.cookie, TEST_PORT)
            self.assertEqual(status, 404, path)
            self.assertIn('页面未找到', body)

        for path in ['/repairs/create', '/repairs/1/status', '/repairs/1/delete', '/parking/create', '/parking/1/edit', '/parking/1/delete', '/deposits/create', '/deposits/1/edit', '/deposits/1/refund', '/deposits/1/delete']:
            status, body, _ = http_post(path, {'confirm_text': 'RESET'}, self.cookie, TEST_PORT)
            self.assertEqual(status, 404, path)


    def test_admin_system_health_page_reports_and_repairs_schema_and_bill_status(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('健康检查业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('HEALTH', 'A座', '9001', 9, '居民', 10, owner_id)
        ).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 1, '2025-01', 50, '2025-01-01', 'paid', 'HEALTH-WEB-PAID-NO-PAYMENT')
        ).lastrowid
        db.commit(); db.close()
        try:
            status, page = http_get('/system_health', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn('系统健康检查', page)
            self.assertIn('已缴状态但收款不足', page)
            self.assertIn('HEALTH-WEB-PAID-NO-PAYMENT', page)

            status, body, loc = http_post('/system_health/repair', {'repair': 'bill_status'}, self.cookie, TEST_PORT)
            self.assertEqual(status, 302)
            db = db_module.get_db()
            fixed = db.execute("SELECT status FROM bills WHERE id=?", (bill_id,)).fetchone()['status']
            db.close()
            self.assertEqual(fixed, 'unpaid')
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM payments WHERE bill_id=?', (bill_id,))
            db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()


    def test_login_page_accessible_without_auth(self):
        status, body = http_get('/login', '', TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('物业收费管理系统', body)


    def test_public_account_request_creates_inactive_operator_pending_admin_review(self):
        username = 'pending_request_user'
        status, body = http_get('/register', '', TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('申请账号', body)

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({
            'username': username,
            'password': 'pending123',
            'password_confirm': 'pending123',
            'display_name': '待审核账号',
        })
        conn.request('POST', '/register', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        resp.read()
        location = resp.getheader('Location', '')
        conn.close()
        self.assertEqual(resp.status, 302)
        self.assertIn('已提交', urllib.parse.unquote(location))

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': username, 'password': 'pending123'})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        resp.read()
        inactive_location = resp.getheader('Location', '')
        conn.close()
        self.assertIn('待管理员启用', urllib.parse.unquote(inactive_location))

        status, body = http_get('/users', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(username, body)
        self.assertIn('待审核', body)


    def test_home_redirects_to_login_without_auth(self):
        status, body = http_get('/', '', TEST_PORT)
        # Without auth should get login page or redirect
        self.assertIn(status, (200, 302))


    def test_admin_session_cookie_has_local_safe_attributes(self):
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse(); resp.read(); conn.close()
        cookie = resp.getheader('Set-Cookie', '')

        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Lax', cookie)
        self.assertIn('Path=/', cookie)


    def test_expired_session_token_redirects_to_login(self):
        c = login_and_get_client(TEST_PORT)
        token = re.search(r"session_token=([^;]+)", c).group(1)
        from server.db import get_db
        db = get_db()
        db.execute("UPDATE sessions SET created_at=datetime('now','-2 day') WHERE token=?", (token,))
        db.commit(); db.close()

        status, body, loc = http_get_with_location('/', c, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertEqual(loc, '/login')


    def test_logout_clears_session(self):
        # Re-login to ensure cookie is fresh
        c = login_and_get_client(TEST_PORT)
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/logout', headers={'Cookie': c})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        # After logout, the cookie should be invalid
        status, body = http_get('/', c, TEST_PORT)
        self.assertIn(status, (200, 302))
        # Should show login page content, not dashboard
        body_lower = body.lower()
        self.assertNotIn('快捷操作', body_lower)


    def test_static_path_traversal_is_blocked(self):
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/static/../property.db')
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 404)


    def test_static_js_uses_javascript_content_type(self):
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/static/billing.js')
        resp = conn.getresponse()
        resp.read()
        content_type = resp.getheader('Content-Type', '')
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn('application/javascript', content_type)


