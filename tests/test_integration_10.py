#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 10."""

from tests.integration_base import *


class TestIntegration10(IntegrationTestBase):
    def test_job_roles_limit_contract_and_master_data_changes(self):
        finance_cookie = self._create_user_and_login(
            'finance_contract_scope', 'finance123', 'finance', '合同财务'
        )
        cashier_cookie = self._create_user_and_login(
            'cashier_contract_scope', 'cashier123', 'cashier', '合同收费员'
        )
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('岗位边界业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('ROLEJOB', 'B座', '3001', 30, '居民', 80, owner_id)
        ).lastrowid
        db.commit(); db.close()
        try:
            status, body = http_get('/merchant_contracts/create', finance_cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn('商户合同', body)

            status, _, loc = http_get_with_location('/merchant_contracts/create', cashier_cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('无权限', urllib.parse.unquote(loc))

            status, _, loc = http_post(f'/rooms/{room_id}/edit', {
                'building': 'ROLEJOB',
                'unit': 'B座',
                'room_number': '3001',
                'floor': '30',
                'category': '居民',
                'area': '81',
                'owner_id': str(owner_id),
            }, cashier_cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('无权限', urllib.parse.unquote(loc))

            status, _, loc = http_post(f'/rooms/{room_id}/edit', {
                'building': 'ROLEJOB',
                'unit': 'B座',
                'room_number': '3001',
                'floor': '30',
                'category': '居民',
                'area': '82',
                'owner_id': str(owner_id),
            }, finance_cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertNotIn('无权限', urllib.parse.unquote(loc))

            db = db_module.get_db()
            area = db.execute('SELECT area FROM rooms WHERE id=?', (room_id,)).fetchone()['area']
            db.close()
            self.assertEqual(float(area), 82.0)
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()


    def test_sensitive_report_exports_are_finance_or_manager_only(self):
        finance_cookie = self._create_user_and_login(
            'finance_export_scope', 'finance123', 'finance', '导出财务'
        )
        blocked_roles = (
            ('cashier', 'cashier_export_scope'),
            ('frontdesk', 'frontdesk_export_scope'),
            ('executive', 'executive_export_scope'),
        )

        status, body = http_get('/reports', finance_cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('导出经营分析Excel', body)
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/reports/enterprise_analysis.xlsx?period=2026-06', headers={'Cookie': finance_cookie})
        resp = conn.getresponse(); data = resp.read(); conn.close()
        self.assertEqual(resp.status, 200)
        self.assertGreater(len(data), 100)

        for role, username in blocked_roles:
            cookie = self._create_user_and_login(username, 'export123', role, role)
            status, page = http_get('/reports', cookie, TEST_PORT)
            self.assertEqual(status, 200, role)
            status, _, loc = http_get_with_location('/reports/enterprise_analysis.xlsx?period=2026-06', cookie, TEST_PORT)
            self.assertEqual(status, 302, role)
            self.assertIn('无权限', urllib.parse.unquote(loc), role)


    def test_admin_role_is_reserved_and_not_creatable_from_user_form(self):
        status, form = http_get('/users/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="manager"', form)
        self.assertIn('业务管理员', form)
        for role_value in ('finance', 'cashier', 'frontdesk', 'executive'):
            self.assertIn(f'value="{role_value}"', form)
        self.assertNotIn('value="operator"', form)
        self.assertNotIn('value="readonly"', form)
        self.assertNotIn('value="admin"', form)
        self.assertNotIn('>管理员</option>', form)

        status, _, loc = http_post('/users/create', {
            'username': 'forged_admin_create',
            'password': 'admin12345',
            'display_name': '伪造管理员',
            'role': 'admin',
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('超级管理员账号不可新增', urllib.parse.unquote(loc))

        from server.db import get_db
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username='forged_admin_create'").fetchone()
        db.close()
        self.assertIsNone(existing)


    def test_existing_user_cannot_be_upgraded_to_super_admin(self):
        http_post('/users/create', {
            'username': 'operator_upgrade_guard',
            'password': 'operator123',
            'display_name': '升级保护',
            'role': 'operator',
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        from server.db import get_db
        db = get_db()
        uid = db.execute("SELECT id FROM users WHERE username='operator_upgrade_guard'").fetchone()['id']
        db.close()

        status, _, loc = http_post(f'/users/{uid}/edit', {
            'username': 'operator_upgrade_guard',
            'display_name': '升级保护',
            'role': 'admin',
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('超级管理员账号不可新增或升级', urllib.parse.unquote(loc))

        db = get_db()
        role = db.execute('SELECT role FROM users WHERE id=?', (uid,)).fetchone()['role']
        db.close()
        self.assertEqual(role, 'operator')


    def test_system_admin_alias_cannot_be_created_or_assigned_from_user_forms(self):
        status, _, loc = http_post('/users/create', {
            'username': 'forged_system_admin_create',
            'password': 'admin12345',
            'display_name': '伪造系统管理员',
            'role': 'system_admin',
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('超级管理员账号不可新增', urllib.parse.unquote(loc))

        from server.db import get_db
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username='forged_system_admin_create'").fetchone()
        uid = db.execute("SELECT id FROM users WHERE username='operator_upgrade_guard'").fetchone()
        if not uid:
            db.execute(
                "INSERT INTO users(username,password_hash,display_name,role,is_active) VALUES(?,?,?,?,1)",
                ('operator_upgrade_guard', 'unused', '升级保护', 'operator')
            )
            uid = {'id': db.execute("SELECT id FROM users WHERE username='operator_upgrade_guard'").fetchone()['id']}
            db.commit()
        else:
            uid = {'id': uid['id']}
        db.close()
        self.assertIsNone(existing)

        status, _, loc = http_post(f'/users/{uid["id"]}/edit', {
            'username': 'operator_upgrade_guard',
            'display_name': '升级保护',
            'role': 'system_admin',
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('超级管理员账号不可新增或升级', urllib.parse.unquote(loc))

        db = get_db()
        role = db.execute('SELECT role FROM users WHERE id=?', (uid['id'],)).fetchone()['role']
        db.close()
        self.assertEqual(role, 'operator')


    def test_manager_can_manage_business_users_but_not_system_maintenance(self):
        manager_cookie = self._create_user_and_login(
            'manager_scope_test', 'manager123', 'manager', '业务管理员测试'
        )

        status, body = http_get('/', manager_cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('业务管理员测试', body)
        self.assertIn('业务管理员', body)
        for text in ['收费项目', '数据导入', '自动出账', '公摊分摊', '发票管理', '期末结账', '操作员管理']:
            self.assertIn(text, body)
        for text in ['数据备份', '系统健康', '系统更新', '清空试用业务数据']:
            self.assertNotIn(text, body)

        status, users_body = http_get('/users', manager_cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('添加操作员', users_body)
        self.assertIn('业务管理员', users_body)

        status, _, loc = http_post('/users/create', {
            'username': 'manager_created_finance',
            'password': 'finance123',
            'display_name': '业务管理员创建财务',
            'role': 'operator',
            'is_active': 'on',
        }, manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/users?flash=', loc)

        for path in ['/backups', '/audit_logs', '/system_health', '/system_update', '/trial_data_reset']:
            status, _, loc = http_get_with_location(path, manager_cookie, TEST_PORT)
            self.assertEqual(status, 302, path)
            self.assertIn('无权限', urllib.parse.unquote(loc), path)


    def test_manager_cannot_delete_or_downgrade_super_admin(self):
        manager_cookie = self._create_user_and_login(
            'manager_super_guard_test', 'manager123', 'manager', '业务管理员保护测试'
        )

        status, _, loc = http_post('/users/1/delete', {}, manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('超级管理员不可删除', urllib.parse.unquote(loc))

        status, _, loc = http_post('/users/1/edit', {
            'username': 'admin',
            'display_name': '管理员',
            'role': 'manager',
            'is_active': 'on',
        }, manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('超级管理员不可降级', urllib.parse.unquote(loc))


