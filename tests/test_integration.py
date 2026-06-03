#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP integration tests — starts a real server and tests via HTTP.

Covers:
  1. Server startup and page accessibility (21 pages)
  2. Login/logout flow
  3. Room CRUD
  4. Owner CRUD
  5. Bill generation and payment
  6. API endpoints
  7. CSV export
  8. Backup/restore

NOTE: Each test gets its own fresh cookie (setUp re-logs in).
"""

import unittest, os, sys, http.server, threading, time, json, tempfile, urllib.parse, re, http.client

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from datetime import date
from unittest import mock
from tests.conftest import (
    BASE_URL, TEST_PORT,
    login_and_get_client, http_get, http_post,
    create_owner, create_room, create_bill, create_payment,
)


def _start_server():
    """Start the server once for the whole test class."""
    os.environ['PM_DB_PATH'] = os.path.join(
        tempfile.gettempdir(), f'test_integration_{int(time.time())}.db'
    )

    import server.db as db_module
    db_module.DB_PATH = os.environ['PM_DB_PATH']
    db_module.BACKUP_DIR = os.path.join(os.path.dirname(db_module.DB_PATH), 'backups')

    from server import db_init
    from server.base import BaseHandler
    from server.auth import AuthMixin
    from server.index import IndexMixin
    from server.rooms import RoomMixin
    from server.owners import OwnerMixin
    from server.fees import FeeMixin
    from server.meter import MeterMixin
    from server.bill_list import BillListMixin
    from server.bill_detail import BillDetailMixin
    from server.bill_generation import BillGenerationMixin
    from server.bill_export import BillExportMixin
    from server.bill_print import BillPrintMixin
    from server.bill_receipt import BillReceiptMixin
    from server.payments import PaymentMixin
    from server.billing_ui import BillingUiMixin
    from server.auto_billing import AutoBillingMixin
    from server.repairs import RepairMixin
    from server.parking import ParkingMixin
    from server.invoices import InvoiceMixin
    from server.deposits import DepositMixin
    from server.reminders import ReminderMixin
    from server.collections import CollectionMixin
    from server.closing import ClosingMixin
    from server.reports import ReportMixin
    from server.import_data import ImportMixin
    from server.backups import BackupMixin
    from server.data_health import DataHealthMixin
    from server.system_update_pages import SystemUpdateMixin
    from server.trial_data_reset import TrialDataResetMixin
    from server.api import ApiMixin

    class Handler(
        AuthMixin, IndexMixin, RoomMixin, OwnerMixin,
        FeeMixin, MeterMixin,
        BillListMixin, BillDetailMixin, BillGenerationMixin,
        BillExportMixin, BillPrintMixin, BillReceiptMixin,
        PaymentMixin, BillingUiMixin, AutoBillingMixin,
        RepairMixin, ParkingMixin, InvoiceMixin, DepositMixin,
        ReminderMixin, CollectionMixin, ClosingMixin, ReportMixin,
        ImportMixin, BackupMixin, DataHealthMixin, SystemUpdateMixin, TrialDataResetMixin, ApiMixin, BaseHandler,
    ): pass

    db_init()
    srv = http.server.ThreadingHTTPServer((BASE_URL, TEST_PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    return srv


class TestIntegration(unittest.TestCase):
    """Full-stack HTTP integration tests."""

    @classmethod
    def setUpClass(cls):
        cls.server = _start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.server_close()
        time.sleep(0.1)

    def setUp(self):
        """Get a fresh cookie before each test."""
        self.cookie = login_and_get_client(TEST_PORT)


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
        self.assertIn('无权限访问系统更新', urllib.parse.unquote(loc))

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
        self.assertIn('业主、房间、账单、缴费、抄表、发票、结账、公摊等业务记录', confirm_page)
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


    # ── Login/Logout ────────────────────────────────────────────

    def test_login_page_accessible_without_auth(self):
        status, body = http_get('/login', '', TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('物业管理收费系统', body)


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


    def _create_user_and_login(self, username, password, role, display_name='测试用户'):
        http_post('/users/create', {
            'username': username,
            'password': password,
            'display_name': display_name,
            'role': role,
            'is_active': 'on',
        }, self.cookie, TEST_PORT)
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode({'username': username, 'password': password})
        conn.request('POST', '/login', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        resp.read()
        cookie = resp.getheader('Set-Cookie', '').split(';')[0]
        conn.close()
        return cookie




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

    def test_payments_page_groups_by_room_and_exports_csv(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '缴费业主', '13900000000')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='1801', owner_id=owner_id)
        fee_id = db.execute("INSERT INTO fee_types(name, calc_method, unit_price, sort_order, is_active) VALUES(?,?,?,?,1)",
                            ('物业服务费', 'area', 2.5, 10)).lastrowid
        db.commit()
        bill_id = create_bill(db, room_id=room_id, fee_type_id=fee_id, period='2026-05', amount=250, owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=250, method='transfer', operator='测试经手人')
        db.close()

        status, body = http_get('/payments?period=2026-05-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('导出CSV', body)
        self.assertIn('payment-group', body)
        self.assertIn('金莎国际-B座-1801', body)
        self.assertIn('缴费业主', body)

        status, csv_body = http_get('/payments/export.csv?period=2026-05-01&method=transfer&operator=%E6%B5%8B%E8%AF%95%E7%BB%8F%E6%89%8B%E4%BA%BA', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('payment_date,receipt_number,bill_number', csv_body)
        self.assertIn('金莎国际', csv_body)
        self.assertIn('测试经手人', csv_body)




    def test_property_billing_excludes_commercial_only_fee_names_even_if_sort_order_is_low(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '物业B座商户业主', '13900000008')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='B-M01', category='商户', owner_id=owner_id)
        db.execute("UPDATE fee_types SET sort_order=17, is_active=1 WHERE name='泄水费'")
        db.commit(); db.close()

        status, body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('金莎国际-B座-B-M01', body)
        self.assertNotIn('泄水费', body)
        self.assertNotIn('装修押金', body)
        self.assertNotIn('空调能源费', body)

    def test_commercial_billing_shows_water_fees_for_every_merchant_and_uses_water_standard(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商业水费业主', '13900000004')
        normal_id = create_room(db, building='金莎国际', unit='商场', room_number='CW101', category='商户', owner_id=owner_id)
        special_id = create_room(db, building='金莎国际', unit='商场', room_number='CW102', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (normal_id,))
        db.execute("UPDATE rooms SET water_rate_type='特行' WHERE id=?", (special_id,))
        normal_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()[0]
        special_fee = db.execute("SELECT id FROM fee_types WHERE name='水费(特行)'").fetchone()[0]
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (normal_id, normal_fee, '202605', 10, 0, 10, 'confirmed'))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (special_id, special_fee, '202605', 10, 0, 10, 'confirmed'))
        db.commit(); db.close()

        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('水费(非居民)', body)
        self.assertIn('水费(特行)', body)
        self.assertIn('data-water="非居民"', body)
        self.assertIn('data-water="特行"', body)

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(normal_id),
            'fee_types': [str(normal_fee), str(special_fee)],
            'period_start': '2026-05-01',
            'period_end': '2026-05-28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = get_db()
        normal_count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=? AND fee_type_id=?", (normal_id, normal_fee)).fetchone()[0]
        wrong_count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=? AND fee_type_id=?", (normal_id, special_fee)).fetchone()[0]
        db.close()
        self.assertEqual(normal_count, 1)
        self.assertEqual(wrong_count, 0)

    def test_room_water_rate_type_controls_water_fee_standard(self):
        from server.db import get_db
        from server.billing_engine import calculate_bill_amount, fee_applies_to_room
        db = get_db()
        owner_id = create_owner(db, '水费档位业主', '13900000003')
        normal_id = create_room(db, building='金莎国际', unit='商场', room_number='W101', category='商户', owner_id=owner_id)
        special_id = create_room(db, building='金莎国际', unit='商场', room_number='W102', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (normal_id,))
        db.execute("UPDATE rooms SET water_rate_type='特行' WHERE id=?", (special_id,))
        normal_room = db.execute("SELECT * FROM rooms WHERE id=?", (normal_id,)).fetchone()
        special_room = db.execute("SELECT * FROM rooms WHERE id=?", (special_id,)).fetchone()
        normal_fee = db.execute("SELECT * FROM fee_types WHERE name='水费(非居民)'").fetchone()
        special_fee = db.execute("SELECT * FROM fee_types WHERE name='水费(特行)'").fetchone()
        self.assertTrue(fee_applies_to_room(normal_fee['name'], normal_room))
        self.assertFalse(fee_applies_to_room(special_fee['name'], normal_room))
        self.assertTrue(fee_applies_to_room(special_fee['name'], special_room))
        self.assertFalse(fee_applies_to_room(normal_fee['name'], special_room))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (normal_id, normal_fee['id'], '202605', 10, 0, 10, 'confirmed'))
        db.execute("INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)", (special_id, special_fee['id'], '202605', 10, 0, 10, 'confirmed'))
        db.commit()
        self.assertEqual(calculate_bill_amount(db, normal_room, normal_fee, '2026-05')['amount'], 58.0)
        self.assertEqual(calculate_bill_amount(db, special_room, special_fee, '2026-05')['amount'], 201.1)
        db.close()

    def test_meter_billing_sums_confirmed_readings_across_selected_range(self):
        from server.db import get_db
        from server.billing_engine import calculate_bill_amount
        db = get_db()
        owner_id = create_owner(db, '跨月水费业主', '13900000005')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM101', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (room_id,))
        room = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
        fee = db.execute("SELECT * FROM fee_types WHERE name='水费(非居民)'").fetchone()
        for period, consumption, status in [('202606', 10, 'confirmed'), ('202607', 8, 'confirmed'), ('202608', 4, 'draft')]:
            db.execute(
                "INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)",
                (room_id, fee['id'], period, consumption, 0, consumption, status),
            )
        db.commit()

        calc = calculate_bill_amount(db, room, fee, '2026-06~2026-08', 3)

        self.assertEqual(calc['amount'], 104.4)
        self.assertIn('用量合计18', calc['formula'])
        self.assertNotIn('×3个月', calc['formula'])
        db.close()

    def test_billing_page_embeds_confirmed_meter_readings_for_frontend_calculation(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '收费页抄表业主', '13900000006')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='WM102', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET water_rate_type='非居民' WHERE id=?", (room_id,))
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='水费(非居民)'").fetchone()[0]
        db.execute(
            "INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status) VALUES(?,?,?,?,?,?,?)",
            (room_id, fee_id, '202606', 16, 0, 16, 'confirmed'),
        )
        db.commit(); db.close()

        status, body = http_get('/billing', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('window.METER_READINGS=', body)
        self.assertIn(f'"{room_id}:{fee_id}:202606": 16.0', body)

    def test_nonresident_and_special_water_fees_apply_to_commercial_rooms_not_as_room_types(self):
        from server.billing_engine import fee_applies_to_category
        self.assertTrue(fee_applies_to_category('水费(非居民)', '商户'))
        self.assertTrue(fee_applies_to_category('水费(特行)', '商业'))
        self.assertFalse(fee_applies_to_category('水费(非居民)', '居民'))
        self.assertFalse(fee_applies_to_category('水费(特行)', '居民'))
        self.assertFalse(fee_applies_to_category('空调费(商业)', '居民'))
        self.assertTrue(fee_applies_to_category('空调费(商业)', '商业'))

    def test_commercial_billing_only_lists_commercial_room_categories(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商业过滤业主', '13900000001')
        create_room(db, building='金莎国际', unit='B座', room_number='1901', category='居民', owner_id=owner_id)
        create_room(db, building='金莎国际', unit='商场', room_number='C101', category='商户', owner_id=owner_id)
        db.close()

        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<optgroup label="商场">', body)
        self.assertIn('金莎国际-商场-C101', body)
        self.assertNotIn('金莎国际-B座-1901', body)

    def test_mall_commercial_billing_uses_room_rate_cycle_and_excludes_other_units(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商场规则业主', '13900008888')
        mall_id = create_room(db, building='金莎国际', unit='商场', room_number='1F-101', category='商户', area=88.5, owner_id=owner_id)
        db.execute("UPDATE rooms SET custom_rate=4.8, payment_cycle='quarterly', shop_name='甲店' WHERE id=?", (mall_id,))
        a_id = create_room(db, building='金莎国际', unit='A座', room_number='A101', category='商户', area=100, owner_id=owner_id)
        db.execute("UPDATE rooms SET custom_rate=9.9, payment_cycle='semiannual' WHERE id=?", (a_id,))
        b_id = create_room(db, building='金莎国际', unit='B座', room_number='B201', category='居民', area=100, owner_id=owner_id)
        commercial_fee = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        db.commit(); db.close()

        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<optgroup label="商场">', body)
        self.assertIn('金莎国际-商场-1F-101 / 甲店', body)
        self.assertNotIn('金莎国际-A座-A101', body)
        self.assertNotIn('金莎国际-B座-B201', body)
        self.assertIn('data-cycle="quarterly"', body)
        self.assertIn('data-rate="4.8"', body)

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(mall_id),
            'fee_types': str(commercial_fee),
            'period_start': '2033-01-01',
            'period_end': '2033-01-31',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = get_db()
        bill = db.execute("SELECT amount,billing_period FROM bills WHERE room_id=? AND fee_type_id=?", (mall_id, commercial_fee)).fetchone()
        a_count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=?", (a_id,)).fetchone()[0]
        b_count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=?", (b_id,)).fetchone()[0]
        self.assertEqual(bill['amount'], 1274.4)
        self.assertEqual(bill['billing_period'], '2033-01~2033-03')
        self.assertEqual(a_count, 0)
        self.assertEqual(b_count, 0)
        db.execute("UPDATE rooms SET area=100 WHERE id=?", (mall_id,))
        room = db.execute("SELECT * FROM rooms WHERE id=?", (mall_id,)).fetchone()
        ft = db.execute("SELECT * FROM fee_types WHERE id=?", (commercial_fee,)).fetchone()
        from server.billing_engine import calculate_bill_amount
        self.assertEqual(calculate_bill_amount(db, room, ft, '2033-04', months=3)['amount'], 1440.0)
        self.assertEqual(bill['amount'], 1274.4)
        db.close()

    def test_auto_billing_page_is_independent_and_confirms_contract_based_bills(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动出账页面业主', '13900007777')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOHTTP', 'B座', '2701', 27, '居民', 100, owner_id, '页面租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        status, body = http_get('/auto_billing?advance_days=30', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动出账预览', body)
        self.assertIn('收费项目选择', body)
        self.assertIn('name="period_cycle"', body)
        self.assertIn('按租户资料周期', body)
        self.assertIn('季度', body)
        self.assertIn('按租户合同开始日、结束日、缴费周期计算下一期账单', body)
        self.assertIn('提前 30 天只是筛选即将到期的下一期', body)
        self.assertIn('生成后按缴费截止日进入催缴管理', body)
        self.assertIn('预览汇总', body)
        self.assertRegex(body, r'可生成 \d+ 笔')
        self.assertRegex(body, r'已存在 \d+ 笔')
        self.assertRegex(body, r'涉及租户 \d+ 户')
        self.assertRegex(body, r'涉及房间 \d+ 间')
        self.assertRegex(body, r'应收合计 ¥\d+\.\d{2}')
        self.assertIn('进入生成确认', body)
        self.assertNotIn('确认生成选中账单', body)
        self.assertIn('页面租户', body)
        self.assertIn('2026-06-27 至 2026-09-26', body)
        self.assertIn('2026-06-26', body)
        self.assertIn('href="/auto_billing"', body)

        status, body = http_get('/auto_billing?advance_days=30&fee_ids=1&fee_ids=3', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('电梯费', body)

        status, quarter_body = http_get(f'/auto_billing?advance_days=30&period_cycle=quarterly&fee_ids={fee_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-06-27 至 2026-09-26', quarter_body)
        self.assertIn('value="quarterly" selected', quarter_body)

        db = get_db()
        existing_owner = create_owner(db, '已存在筛选业主', '13900008888')
        existing_room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOEXIST', 'B座', '2703', 27, '居民', 100, existing_owner, '已存在租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        db.execute("""
            INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,source,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (existing_room_id, existing_owner, fee_id, '2026-06~2026-09', 570, '2026-06-26', 'unpaid', 'AUTOEXIST-001', 'auto_contract', '2026-06-27', '2026-09-26'))
        db.commit(); db.close()

        status, only_can = http_get('/auto_billing?advance_days=30&preview_status=can_generate', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('只看可生成', only_can)
        self.assertIn('页面租户', only_can)
        self.assertNotIn('已存在租户', only_can)

        status, only_existing = http_get('/auto_billing?advance_days=30&preview_status=existing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('只看已存在', only_existing)
        self.assertIn('已存在租户', only_existing)
        self.assertNotIn('页面租户', only_existing)
        self.assertIn('同房间、同收费项目、同服务期已存在账单', only_existing)
        self.assertIn('当前筛选条件下没有可生成账单', only_existing)
        self.assertIn('可切换到“全部”或“只看已存在”查看原因', only_existing)
        self.assertIn('检查租户合同开始/结束日期、缴费周期、收费项目是否适用', only_existing)
        self.assertIn('disabled', only_existing)
        self.assertIn('暂无可生成账单', only_existing)
        self.assertNotIn('进入生成确认</button>', only_existing)

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing/runs/', loc)
        self.assertNotIn('keyword=', urllib.parse.unquote(loc))

        db = get_db()
        bill = db.execute(
            "SELECT service_start,service_end,due_date,billing_period,source,auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?",
            (room_id, fee_id)
        ).fetchone()
        db.close()
        self.assertIn(bill['auto_batch_no'], loc)
        status, detail = http_get(loc, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动出账批次详情', detail)
        self.assertIn('查看本批次账单', detail)
        self.assertIn('查看相关催缴', detail)
        status, reminders = http_get('/reminders?period=2026-06-01&status=approaching', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('页面租户', reminders)
        self.assertIn('自动出账', reminders)
        self.assertIn('服务期 2026-06-27 至 2026-09-26', reminders)
        self.assertEqual(bill['service_start'], '2026-06-27')
        self.assertEqual(bill['service_end'], '2026-09-26')
        self.assertEqual(bill['due_date'], '2026-06-26')
        self.assertEqual(bill['billing_period'], '2026-06~2026-09')
        self.assertEqual(bill['source'], 'auto_contract')

    def test_auto_billing_confirm_page_allows_editing_before_final_write(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动确认编辑业主', '13900009991')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOEDITHTTP', 'B座', '2502', 25, '居民', 100, owner_id, '自动确认编辑租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()
        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'

        status, html, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('确认后才会写入账单', html)
        self.assertIn(f'name="amount__{item_key}"', html)
        self.assertIn(f'name="due_date__{item_key}"', html)
        self.assertIn('value="570.00"', html)

        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'confirm': '1',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            f'amount__{item_key}': '618.88',
            f'due_date__{item_key}': '2026-07-05',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing/runs/', loc)

        db = get_db()
        bill = db.execute("SELECT amount,due_date,auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        self.assertEqual(bill['amount'], 618.88)
        self.assertEqual(bill['due_date'], '2026-07-05')
        db.execute("DELETE FROM bills WHERE room_id=?", (room_id,))
        db.execute("DELETE FROM auto_billing_runs WHERE batch_no=?", (bill['auto_batch_no'],))
        db.execute("DELETE FROM rooms WHERE id=?", (room_id,))
        db.execute("DELETE FROM owners WHERE id=?", (owner_id,))
        db.commit(); db.close()

    def test_auto_billing_confirm_page_previews_before_writing_bills(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动确认业主', '13922221111')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOCONFIRM', 'B座', '2702', 27, '居民', 100, owner_id, '确认页租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, html, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('自动出账确认', html)
        self.assertIn('将生成 1 笔账单', html)
        self.assertIn('确认页租户', html)
        self.assertIn('AUTOCONFIRM-B座-2702', html)
        self.assertIn('2026-06-27 至 2026-09-26', html)
        self.assertIn('2026-06-26', html)
        self.assertIn('应收合计', html)
        self.assertIn('¥570.00', html)
        self.assertIn('confirm', html)
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()[0]
        db.close()
        self.assertEqual(count, 0)

    def test_auto_billing_page_lists_and_rolls_back_recent_batch(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动撤回业主', '13933334444')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOROLL', 'B座', '2602', 26, '居民', 100, owner_id, '自动撤回租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        status, page = http_get('/auto_billing?advance_days=30', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('最近自动出账记录', page)
        self.assertIn('撤回未缴账单', page)

        db = get_db()
        batch_no = db.execute("SELECT auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()['auto_batch_no']
        db.close()
        status, body, loc = http_post(f'/auto_billing/runs/{batch_no}/rollback', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing', loc)
        db = get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()[0], 0)
        run = db.execute("SELECT status,rollback_count FROM auto_billing_runs WHERE batch_no=?", (batch_no,)).fetchone()
        db.close()
        self.assertEqual(run['status'], 'rolled_back')
        self.assertEqual(run['rollback_count'], 1)

    def test_auto_billing_batch_detail_lists_generated_bills(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动详情业主', '13955556666')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTODETAIL', 'B座', '2603', 26, '居民', 100, owner_id, '自动详情租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = get_db()
        batch_no = db.execute("SELECT auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()['auto_batch_no']
        db.close()

        status, detail = http_get(f'/auto_billing/runs/{batch_no}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动出账批次详情', detail)
        self.assertIn(batch_no, detail)
        self.assertIn('自动详情租户', detail)
        self.assertIn('AUTODETAIL-B座-2603', detail)
        self.assertIn('物业费(居民)', detail)
        self.assertIn('2026-06-27 至 2026-09-26', detail)
        self.assertIn('2026-06-26', detail)
        self.assertIn('570.00', detail)
        self.assertIn('批次汇总', detail)
        self.assertIn('应收合计', detail)
        self.assertIn('已收合计', detail)
        self.assertIn('未收合计', detail)
        self.assertIn('¥570.00', detail)
        self.assertIn('可撤回', detail)
        self.assertIn('按租户/房间分组', detail)
        self.assertIn('自动详情租户 / AUTODETAIL-B座-2603', detail)
        self.assertIn('1 笔', detail)
        self.assertIn(f'/bills?auto_batch_no={batch_no}', detail)

        status, bills_page = http_get(f'/bills?auto_batch_no={batch_no}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前正在查看自动出账批次', bills_page)
        self.assertIn(batch_no, bills_page)
        self.assertIn(f'/auto_billing/runs/{batch_no}', bills_page)
        self.assertIn('返回批次详情', bills_page)
        self.assertIn('/bills', bills_page)
        self.assertIn('清除批次筛选', bills_page)
        self.assertIn('自动详情租户', bills_page)
        self.assertIn('AUTODETAIL-B座-2603', bills_page)
        self.assertIn('自动出账服务期 2026-06-27 至 2026-09-26', bills_page)

    def test_auto_billing_bill_shows_service_period_in_approaching_reminders(self):
        from server.db import get_db
        db = get_db()
        owner_id = db.execute(
            "INSERT INTO owners(name, phone) VALUES(?, ?)",
            ('自动催缴业主', '13922223333')
        ).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
            ('AUTOREM', 'B座', '2601', 26, '居民', 100, owner_id, '自动催缴租户')
        ).lastrowid
        db.execute(
            """INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,
            bill_number,source,service_start,service_end) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (room_id, owner_id, 1, '2026-06~2026-09', 570, '2026-06-26', 'unpaid',
             'AUTO-REMINDER-001', 'auto_contract', '2026-06-27', '2026-09-26')
        )
        db.commit(); db.close()

        status, body = http_get('/reminders?period=2026-06-01&status=approaching', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动催缴业主', body)
        self.assertIn('自动出账', body)
        self.assertIn('服务期 2026-06-27 至 2026-09-26', body)
        self.assertIn('截止 2026-06-26', body)

    def test_auto_billing_outputs_show_service_period(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动输出业主', '13966667777')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOOUTPUT', 'B座', '2801', 28, '居民', 100, owner_id, '自动输出租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        bill_id = db.execute("""
            INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,
            bill_number,source,service_start,service_end,auto_batch_no)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            room_id, owner_id, fee_id, '2026-06~2026-09', 570, '2026-06-26', 'unpaid',
            'AUTO-OUTPUT-001', 'auto_contract', '2026-06-27', '2026-09-26', 'AUTO-OUTPUT-BATCH'
        )).lastrowid
        db.commit(); db.close()

        status, print_html, loc = http_post('/bills/print_selected', {
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动出账服务期 2026-06-27 至 2026-09-26', print_html)

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动出账服务期 2026-06-27 至 2026-09-26', receipt_html)

        status, csv_body, loc = http_post('/bills/export_selected', {
            'bill_ids': str(bill_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('服务开始日', csv_body)
        self.assertIn('服务结束日', csv_body)
        self.assertIn('2026-06-27', csv_body)
        self.assertIn('2026-09-26', csv_body)

    def test_auto_billing_paid_bill_flows_to_reports_invoice_and_blocks_rollback(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '自动链路业主', '13977778888')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOFLOW', 'B座', '2901', 29, '居民', 100, owner_id, '自动链路租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        db.commit(); db.close()

        item_key = f'{room_id}:{fee_id}:2026-06-27:2026-09-26'
        status, body, loc = http_post('/auto_billing/confirm', {
            'advance_days': '30',
            'item_keys': item_key,
            'fee_ids': str(fee_id),
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/auto_billing/runs/', loc)

        db = get_db()
        bill = db.execute("SELECT id,auto_batch_no FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        bill_id = bill['id']
        batch_no = bill['auto_batch_no']
        db.execute("INSERT INTO payments(bill_id,amount_paid,payment_method,operator) VALUES(?,?,?,?)", (bill_id, 570, 'cash', '自动链路收费员'))
        db.execute("UPDATE bills SET status='paid' WHERE id=?", (bill_id,))
        db.commit(); db.close()

        status, report_html = http_get('/reports?period=2026-07&building=AUTOFLOW&status=paid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('AUTOFLOW', report_html)
        self.assertIn('570.00', report_html)
        self.assertIn('已收合计', report_html)
        self.assertIn('自动链路收费员', report_html)

        status, report_csv = http_get('/reports/reconciliation.csv?period=2026-07&building=AUTOFLOW&status=paid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('AUTOFLOW', report_csv)
        self.assertIn('自动链路业主', report_csv)
        self.assertIn('570.00', report_csv)

        status, invoice_html = http_get('/invoices?period=2026-07-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'value="{bill_id}"', invoice_html)
        self.assertIn('AUTOFLOW-2901', invoice_html)
        self.assertIn('自动链路业主', invoice_html)

        status, body, loc = http_post(f'/auto_billing/runs/{batch_no}/rollback', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('保留1笔不可撤回账单', urllib.parse.unquote(loc))
        db = get_db()
        self.assertIsNotNone(db.execute("SELECT id FROM bills WHERE id=?", (bill_id,)).fetchone())
        run = db.execute("SELECT status,rollback_count FROM auto_billing_runs WHERE batch_no=?", (batch_no,)).fetchone()
        db.close()
        self.assertEqual(run['status'], 'blocked')
        self.assertEqual(run['rollback_count'], 0)

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

    def test_operator_cannot_access_user_management(self):
        operator_cookie = self._create_user_and_login(
            'operator_user_mgmt_test', 'operator123', 'operator', '财务收费'
        )

        status, body = http_get('/users', operator_cookie, TEST_PORT)

        self.assertEqual(status, 302)


    def test_home_is_finance_charge_workbench(self):
        status, body = http_get('/', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('收费工作台', body)
        self.assertIn('今日收款', body)
        self.assertIn('本月应收', body)
        self.assertIn('本月已收', body)
        self.assertIn('本月欠费', body)
        self.assertIn('待收费账单', body)
        self.assertIn('生成账单', body)
        self.assertIn('收费登记', body)
        self.assertIn('打印收据', body)
        self.assertIn('对账报表', body)
        self.assertIn('发票管理', body)
        self.assertNotIn('维修', body)

    def test_navigation_names_are_scoped_to_charge_software(self):
        status, body = http_get('/', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('收费工作台', body)
        self.assertIn('收费项目', body)
        self.assertIn('发票管理', body)
        self.assertIn('对账报表', body)
        self.assertNotIn('首页看板', body)
        self.assertNotIn('费用类型', body)
        self.assertNotIn('电子发票', body)
        self.assertNotIn('统计报表', body)

    def test_non_core_modules_hidden_from_main_menu_but_invoice_and_reports_kept(self):
        status, body = http_get('/', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertNotIn('维修管理', body)
        self.assertNotIn('停车管理', body)
        self.assertNotIn('押金管理', body)
        self.assertIn('催缴管理', body)
        self.assertIn('发票管理', body)
        self.assertIn('对账报表', body)
        self.assertNotIn('更多功能', body)

    def test_fee_type_created_without_group_redirects_to_visible_inferred_group(self):
        unique_name = '根页面新增可见测试费'
        status, body, loc = http_post('/fee_types/create', {
            'return_group': '',
            'name': unique_name,
            'calc_method': 'fixed',
            'unit_price': '15',
            'unit': '元/月',
            'billing_cycle': 'monthly',
            'sort_order': '0',
            'is_active': 'on',
            'notes': '根页面新增后应直接可见',
            'reminder_advance_days': '30',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('/fee_types?group=property', loc)

        status, group_page = http_get('/fee_types?group=property', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(unique_name, group_page)

    def test_fee_type_created_from_group_stays_visible_in_that_group(self):
        unique_name = '物业专项测试费'
        status, body, loc = http_post('/fee_types/create', {
            'return_group': 'property',
            'name': unique_name,
            'calc_method': 'fixed',
            'unit_price': '12',
            'unit': '元/月',
            'billing_cycle': 'monthly',
            'sort_order': '0',
            'is_active': 'on',
            'notes': '分组新增可见性测试',
            'reminder_advance_days': '30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/fee_types?group=property', loc)

        status, group_page = http_get('/fee_types?group=property', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn(unique_name, group_page)
        self.assertIn('分组新增可见性测试', group_page)

    def test_system_maintenance_links_render_as_compact_buttons(self):
        status, body = http_get('/system_health', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('maintenance-tools', body)
        self.assertIn('system-tool-btn active', body)
        self.assertIn('href="/system_health"', body)
        self.assertIn('href="/system_update"', body)
        self.assertNotIn('<a class="nav-link active" href="/system_health"', body)

    def test_global_topbar_does_not_repeat_charge_actions_on_every_page(self):
        for path in ['/owners', '/rooms', '/payments', '/reports', '/import']:
            with self.subTest(path=path):
                status, body = http_get(path, self.cookie, TEST_PORT)
                self.assertEqual(status, 200)
                actions = re.search(r'<div class="topbar-actions[^"]*">(.*?)</div>', body, re.S)
                self.assertIsNotNone(actions)
                self.assertNotIn('href="/bills/generate"', actions.group(1))
                self.assertNotIn('href="/billing"', actions.group(1))

    # ── All page accessibility ──────────────────────────────────

    def test_secondary_pages_show_global_back_button(self):
        for path in ['/fee_types/11/edit', '/rooms/create', '/bills/generate']:
            with self.subTest(path=path):
                status, body = http_get(path, self.cookie, TEST_PORT)
                self.assertEqual(status, 200)
                self.assertIn('data-back-button="1"', body)
                self.assertIn('返回', body)
                self.assertIn('topbar-actions d-flex', body)
                self.assertNotIn('topbar-actions d-none d-md-flex', body)

    def test_primary_pages_do_not_show_global_back_button(self):
        for path in ['/', '/rooms', '/fee_types']:
            with self.subTest(path=path):
                status, body = http_get(path, self.cookie, TEST_PORT)
                self.assertEqual(status, 200)
                self.assertNotIn('data-back-button="1"', body)

    def test_all_pages_return_200(self):
        pages = {
            '/': '收费工作台', '/rooms': '房间管理', '/owners': '业主管理',
            '/fee_types': '收费标准', '/meter_readings': '抄表管理',
            '/billing': '物业收费', '/commercial_billing': '商业收费', '/bills': '账单管理', '/payments': '缴费记录',
            '/invoices': '发票管理',
            '/reminders': '催缴管理', '/closing': '期末结账',
            '/backups': '数据备份', '/import': '数据导入', '/reports': '对账报表',
            '/users': '操作员管理', '/late_fee_config': '滞纳金设置',
            '/elevator_tiers': '电梯费阶梯设置', '/bills/generate': '生成账单',
        }
        for path, title in pages.items():
            with self.subTest(path=path):
                status, body = http_get(path, self.cookie, TEST_PORT)
                self.assertEqual(status, 200, msg=f'{path} returned {status}')
                self.assertIn(title, body, msg=f'{path} missing title [{title}]')


    def test_first_run_home_guides_charge_setup_flow(self):
        status, body = http_get('/', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('首次使用建议流程', body)
        self.assertIn('下载导入模板', body)
        self.assertIn('导入基础资料', body)
        self.assertIn('设置收费项目', body)
        self.assertIn('生成账单', body)
        self.assertIn('收费登记', body)
        self.assertIn('对账报表', body)
        self.assertIn('/import/template/basic.csv', body)
        self.assertIn('/import', body)
        self.assertIn('/fee_types', body)
        self.assertIn('/bills/generate', body)

    def test_empty_rooms_page_points_to_template_import_and_manual_add(self):
        status, body = http_get('/rooms?keyword=__NO_ROOM_GUIDE__', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('还没有房间资料', body)
        self.assertIn('推荐先按模板导入', body)
        self.assertIn('下载基础资料模板', body)
        self.assertIn('导入基础资料', body)
        self.assertIn('手动添加房间', body)
        self.assertIn('/import/template/basic.csv', body)
        self.assertIn('/import', body)
        self.assertIn('/rooms/create', body)

    def test_bill_generate_without_rooms_guides_first_run_import(self):
        status, body, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period': '2033-01',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': '__NO_ROOM_GUIDE__',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('生成账单前需要先导入房间资料', body)
        self.assertIn('下载基础资料模板', body)
        self.assertIn('导入基础资料', body)
        self.assertIn('手动添加房间', body)
        self.assertIn('/import/template/basic.csv', body)
        self.assertIn('/import', body)
        self.assertIn('/rooms/create', body)

    # ── Room CRUD ───────────────────────────────────────────────

    def test_room_create_and_list(self):
        status, body, loc = http_post('/rooms/create', {
            'building': 'A栋', 'unit': 'A座', 'room_number': '1001',
            'floor': '10', 'category': '居民', 'area': '120',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/rooms?flash=', loc)

        # Verify listing shows it
        _, body = http_get('/rooms', self.cookie, TEST_PORT)
        self.assertIn('A栋', body)
        self.assertIn('1001', body)

    def test_room_form_field_order_matches_business_layout(self):
        status, body = http_get('/rooms/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        labels = re.findall(r'<label>([^<]+)</label>', body)
        ordered = [label.replace(' *', '') for label in labels]
        expected = [
            '楼栋', '单元/区域', '铺位号/房号', '楼层',
            '房间类型', '面积(m²)', '物业费单价(元/m²·月)', '水费标准',
            '业主姓名', '业主电话', '身份证号', '身份证正面', '身份证反面',
            '租户姓名', '租户电话', '租户身份证号', '租户身份证正面', '租户身份证反面',
            '合同起始', '合同到期', '缴费周期', '店铺名称', '业态/商户类别',
            '备注',
        ]
        self.assertEqual(ordered, expected)

    def test_room_edit_form(self):
        # First create a room
        http_post('/rooms/create', {
            'building': 'X栋', 'unit': 'A座', 'room_number': '666',
            'floor': '6', 'category': '居民', 'area': '80',
        }, self.cookie, TEST_PORT)
        # Then request edit form for room id 1
        status, body = http_get('/rooms/1/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('编辑房间', body)
        self.assertIn('租户姓名', body)
        self.assertIn('name="tenant_name"', body)

    def test_room_create_and_edit_tenant_name(self):
        status, _, loc = http_post('/rooms/create', {
            'building': 'T栋', 'unit': '商场', 'room_number': '1F-101',
            'floor': '1', 'category': '商户', 'area': '88',
            'tenant_name': '测试租户A',
            'tenant_phone': '13800138001',
            'tenant_id_card': '610101199001011234',
            'tenant_id_card_front': 'front-data',
            'tenant_id_card_back': 'back-data',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/rooms?flash=', loc)

        _, body = http_get('/rooms?keyword=%E6%B5%8B%E8%AF%95%E7%A7%9F%E6%88%B7A', self.cookie, TEST_PORT)
        self.assertIn('测试租户A', body)

        room_id = re.search(r'/rooms/(\d+)/edit', body).group(1)
        status, body = http_get(f'/rooms/{room_id}/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="测试租户A"', body)
        self.assertIn('租户电话', body)
        self.assertIn('value="13800138001"', body)
        self.assertIn('租户身份证号', body)
        self.assertIn('value="610101199001011234"', body)
        self.assertIn('租户身份证正面', body)
        self.assertIn('value="front-data"', body)
        self.assertIn('租户身份证反面', body)
        self.assertIn('value="back-data"', body)

        status, _, loc = http_post(f'/rooms/{room_id}/edit', {
            'building': 'T栋', 'unit': '商场', 'room_number': '1F-101',
            'floor': '1', 'category': '商户', 'area': '88',
            'tenant_name': '测试租户B',
            'tenant_phone': '13800138002',
            'tenant_id_card': '610101199002022345',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/rooms?flash=', loc)

        _, body = http_get('/rooms?keyword=%E6%B5%8B%E8%AF%95%E7%A7%9F%E6%88%B7B', self.cookie, TEST_PORT)
        self.assertIn('测试租户B', body)

        status, body = http_get(f'/rooms/{room_id}/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="13800138002"', body)
        self.assertIn('value="610101199002022345"', body)

    # ── Owner CRUD ──────────────────────────────────────────────

    def test_owner_create_and_list(self):
        status, body, loc = http_post('/owners/create', {
            'name': '张三', 'phone': '13900001111',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/owners?flash=', loc)

        _, body = http_get('/owners', self.cookie, TEST_PORT)
        self.assertIn('张三', body)

    # ── Fee types ───────────────────────────────────────────────

    def test_fee_type_list_has_presets(self):
        _, body = http_get('/fee_types', self.cookie, TEST_PORT)
        for name in ['物业费(居民)', '电梯费', '水费(非居民)']:
            with self.subTest(fee=name):
                self.assertIn(name, body)

    # ── Bill generation + payment (core workflow) ───────────────

    def _ensure_room_for_billing(self):
        """Helper: create a room if none exists."""
        _, body = http_get('/rooms', self.cookie, TEST_PORT)
        if '暂无房间' in body:
            http_post('/rooms/create', {
                'building': 'B座', 'unit': 'A座', 'room_number': '801',
                'floor': '8', 'category': '居民', 'area': '100',
            }, self.cookie, TEST_PORT)



    def test_core_charge_workflow_health_check(self):
        """体检第一阶段核心收费链路：收费项目→生成预览→确认→核对→收费→收据→报表→结账锁定。"""
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute(
            "INSERT INTO owners(name, phone) VALUES(?, ?)",
            ('主流程业主', '13812345678')
        ).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id) VALUES(?,?,?,?,?,?,?)",
            ('HEALTH', 'A座', '1201', 12, '商户', 50, owner_id)
        ).lastrowid
        fee_type_id = db.execute("""
            INSERT INTO fee_types(name, calc_method, unit_price, unit, sort_order, notes)
            VALUES(?, ?, ?, ?, ?, ?)
        """, ('体检自定义服务费', 'area', 0, '元/㎡', 20, '第一阶段收费体检')).lastrowid
        db.execute(
            "INSERT INTO fee_type_tiers(fee_type_id, category, rate, is_default) VALUES(?,?,?,?)",
            (fee_type_id, '商户', 2.5, 1)
        )
        db.commit(); db.close()

        status, preview_html, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period': '2032-01',
            'fee_type_ids': str(fee_type_id),
            'due_day': '28',
            'building': 'HEALTH',
            'category': '商户',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('生成账单预览', preview_html)
        self.assertIn('体检自定义服务费', preview_html)
        self.assertIn('50.0×2.5', preview_html)
        self.assertIn('125.00', preview_html)

        db = db_module.get_db()
        preview_count = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2032-01' AND room_id=?", (room_id,)).fetchone()[0]
        db.close()
        self.assertEqual(preview_count, 0)

        status, result_html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2032-01',
            'fee_type_ids': str(fee_type_id),
            'due_day': '28',
            'building': 'HEALTH',
            'category': '商户',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', result_html)
        self.assertIn('本次生成账单', result_html)
        self.assertIn('125.00', result_html)
        self.assertIn('异常核对清单', result_html)

        db = db_module.get_db()
        bill = db.execute("""
            SELECT id, amount, due_date, status FROM bills
            WHERE billing_period='2032-01' AND room_id=? AND fee_type_id=?
        """, (room_id, fee_type_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['amount'], 125)
        self.assertEqual(bill['due_date'], '2032-01-28')
        self.assertEqual(bill['status'], 'unpaid')

        status, list_html = http_get('/bills?period=2032-01&building=HEALTH', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('主流程业主', list_html)
        self.assertIn('体检自定义服务费', list_html)
        self.assertIn('125.00', list_html)

        status, review_html = http_get('/bills/review?period=2032-01&building=HEALTH&scope=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单核对工作台', review_html)
        self.assertIn('HEALTH-A座-1201', review_html)
        self.assertIn('125.00', review_html)

        status, pay_html = http_get(f'/bills/{bill["id"]}/pay', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('录入缴费', pay_html)
        self.assertIn('125.00', pay_html)

        status, body, loc = http_post(f'/bills/{bill["id"]}/pay', {
            'amount_paid': '125.00',
            'payment_method': 'wechat',
            'operator': '体检收费员',
            'notes': '核心收费体检',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = db_module.get_db()
        paid = db.execute("SELECT status FROM bills WHERE id=?", (bill['id'],)).fetchone()['status']
        payment = db.execute("SELECT amount_paid, payment_method, operator FROM payments WHERE bill_id=?", (bill['id'],)).fetchone()
        db.close()
        self.assertEqual(paid, 'paid')
        self.assertEqual(payment['amount_paid'], 125)
        self.assertEqual(payment['payment_method'], 'wechat')
        self.assertEqual(payment['operator'], '体检收费员')

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': str(bill['id']),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('主流程业主', receipt_html)
        self.assertIn('体检收费员', receipt_html)
        self.assertIn('125.00', receipt_html)

        status, report_html = http_get('/reports?period=2032-01&building=HEALTH&status=paid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账期对账', report_html)
        self.assertIn('125.00', report_html)
        self.assertIn('100.0%', report_html)

        status, precheck_html, loc = http_post('/closing/close', {
            'period': '2032-01',
            'notes': '体检结账',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('结账前检查', precheck_html)
        self.assertIn('125.00', precheck_html)

        status, body, loc = http_post('/closing/close', {
            'period': '2032-01',
            'notes': '体检结账',
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        status, body, loc = http_post(f'/bills/{bill["id"]}/pay', {
            'amount_paid': '1.00',
            'payment_method': 'cash',
            'operator': '结账后误操作',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('已结账', urllib.parse.unquote(loc))

    def test_billing_engine_matches_single_and_batch_amounts(self):
        import server.db as db_module
        db = db_module.get_db()
        try:
            owner_id = db.execute("INSERT INTO owners(name) VALUES('统一计算业主')").lastrowid
            room_id = db.execute(
                "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
                ('ENGINE', 'A座', '901', 9, '居民', 10, owner_id)
            ).lastrowid
            ft = db.execute("SELECT * FROM fee_types WHERE id=1").fetchone()
            room = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
            from server.billing_engine import calculate_bill_amount
            monthly = calculate_bill_amount(db, room, ft, '2026-12')
            multi = calculate_bill_amount(db, room, ft, '2026-12', months=3)
            self.assertEqual(monthly['amount'], 19)
            self.assertEqual(monthly['formula'], '10.0×1.9')
            self.assertEqual(multi['amount'], 57)
            self.assertEqual(multi['monthly_amount'], 19)
        finally:
            db.close()

    def test_billing_fee_checkbox_changes_recalculate_total(self):
        status, html = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('class="fee-check"', html)
        self.assertIn('id="checkAll"', html)
        self.assertNotIn('id="checkAll" onchange=', html)

        with open(os.path.join(PROJECT_ROOT, 'static', 'billing.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn('window.isFeeRowSelected', js)
        self.assertIn('if(!window.isFeeRowSelected(row)) return;', js)
        self.assertIn('e.target.id === "checkAll"', js)
        self.assertIn('if(e.target.classList.contains("fee-check")) calcFees();', js)
        self.assertIn('inp.disabled = !selected;', js)
        self.assertIn('row.querySelectorAll(".fee-check")', js)

    def test_billing_amount_recalculation_uses_fee_name_in_calculation_loop(self):
        with open(os.path.join(PROJECT_ROOT, 'static', 'billing.js'), encoding='utf-8') as f:
            js = f.read()
        calculation_loop = js.split('document.querySelectorAll(".fee-row").forEach(function(row){', 2)[2]
        calculation_loop = calculation_loop.split('// Extra rooms', 1)[0]
        self.assertIn('var n = row.dataset.name || "";', calculation_loop)
        self.assertIn("n.indexOf('物业费')", calculation_loop)

    def test_property_billing_date_range_overrides_room_payment_cycle(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '物业日期区间业主', '13900000009')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='1427', category='居民', area=59.42, owner_id=owner_id)
        db.execute("UPDATE rooms SET payment_cycle='monthly', custom_rate=NULL WHERE id=?", (room_id,))
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()[0]
        db.commit(); db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'fee_types': [str(fee_id)],
            'period_start': '2026-06-02',
            'period_end': '2026-10-02',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = get_db()
        bill = db.execute("SELECT amount,billing_period,due_date FROM bills WHERE room_id=? AND fee_type_id=?", (room_id, fee_id)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2026-06~2026-10')
        self.assertEqual(bill['due_date'], '2026-10-02')
        self.assertAlmostEqual(float(bill['amount']), 451.60)

    def test_billing_frontend_uses_room_cycle_only_in_commercial_mode(self):
        status, property_body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('window.BILLING_MODE="property"', property_body)

        status, commercial_body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('window.BILLING_MODE="commercial"', commercial_body)

        with open(os.path.join(PROJECT_ROOT, 'static', 'billing.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn('window.shouldUseRoomCycle', js)
        self.assertIn('window.BILLING_MODE === "commercial"', js)
        self.assertNotIn('if(roomCycle) months = window.cycleMonths(roomCycle);', js)


    def test_bills_start_month_filter_includes_multi_month_billing_period(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '多月账单业主', '13900000010')
        room_id = create_room(db, building='金莎国际', unit='B座', room_number='1427', category='居民', area=59.42, owner_id=owner_id)
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()[0]
        bill_id = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=fee_id, period='2026-06~2026-10', amount=451.60, status='paid')
        create_payment(db, bill_id=bill_id, amount=451.60)
        db.close()

        status, body = http_get('/bills?period=2026-06-01&keyword=1427', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2026-06~2026-10', body)
        self.assertIn('金莎国际-B座-1427', body)
        self.assertNotIn('暂无账单', body)

    def test_bills_range_filter_keeps_existing_single_month_bills_visible(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '范围过滤业主', '13900006666')
        room_id = create_room(db, building='RANGEKEEP', unit='B座', room_number='1408', category='商户', owner_id=owner_id)
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2035-06', amount=100, status='unpaid')
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2035-06~2035-09', amount=400, status='unpaid')
        create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2035-05', amount=50, status='unpaid')
        db.close()

        status, body = http_get('/bills?period=2035-06~2035-09&keyword=1408', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2035-06', body)
        self.assertIn('2035-06~2035-09', body)
        self.assertIn('¥100.00', body)
        self.assertIn('¥400.00', body)
        self.assertNotIn('2035-05', body)
        self.assertNotIn('¥50.00', body)
        self.assertNotIn('暂无账单', body)

    def test_billing_page_labels_extra_rooms_by_tenant_not_owner(self):
        status, body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('同租户其他房间', body)
        self.assertNotIn('同业主其他房间', body)

        status, commercial_body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('同租户其他房间', commercial_body)

    def test_billing_extra_rooms_are_grouped_by_tenant_not_owner(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '同一业主不同租户', '13900005555')
        room_a = create_room(db, building='TENANT', unit='B座', room_number='1402', category='商户', owner_id=owner_id)
        room_b = create_room(db, building='TENANT', unit='B座', room_number='1403', category='商户', owner_id=owner_id)
        room_c = create_room(db, building='TENANT', unit='B座', room_number='1404', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='奈思美发店', shop_name='奈思美发店' WHERE id IN (?,?)", (room_a, room_b))
        db.execute("UPDATE rooms SET tenant_name='其他租户', shop_name='其他租户' WHERE id=?", (room_c,))
        db.commit(); db.close()

        status, body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        match = re.search(r'window\.OWNER_ROOMS=(.*?);window\.BILLING_MODE', body)
        self.assertIsNotNone(match)
        tenant_rooms = json.loads(match.group(1))
        groups = [[r['id'] for r in rooms] for rooms in tenant_rooms.values()]
        self.assertIn([room_a, room_b], [sorted(g) for g in groups])
        self.assertNotIn(sorted([room_a, room_b, room_c]), [sorted(g) for g in groups])
        self.assertIn('data-tenant-key=', body)

    def test_commercial_billing_redirect_shows_generated_range_bill(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商场跳转租户', '13900001111')
        room_id = create_room(db, building='金莎国际', unit='商场', room_number='JUMP101', category='商户', area=20, owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name='跳转租户', payment_cycle='monthly', custom_rate=5 WHERE id=?", (room_id,))
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()[0]
        db.commit(); db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2034-02-01',
            'period_end': '2034-04-01',
            'fee_types': str(fee_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        decoded = urllib.parse.unquote(loc)
        self.assertIn('/bills?period=2034-02~2034-04', decoded)
        self.assertNotIn('keyword=', decoded)

        status, list_html = http_get('/bills?period=2034-02~2034-04&keyword=JUMP101', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('JUMP101', list_html)
        self.assertIn('2034-02~2034-04', list_html)
        self.assertNotIn('暂无账单', list_html)

    def test_payments_page_has_print_receipt_and_export_actions(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '缴费打印业主', '13900002222')
        room_id = create_room(db, building='PAYACT', unit='A座', room_number='501', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-03', amount=120, status='paid', owner_id=owner_id)
        payment_id = create_payment(db, bill_id=bill_id, amount=120, method='cash', operator='打印员')
        db.close()

        status, body = http_get('/payments?period=2034-03-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('/payments/print', body)
        self.assertIn('/payments/receipts', body)
        self.assertIn('导出', body)
        self.assertIn('name="payment_ids"', body)
        self.assertIn('class="payment-group-chk"', body)
        self.assertIn('togglePaymentSelection', body)

        status, print_html, _ = http_post('/payments/print', {'payment_ids': str(payment_id)}, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('缴费记录打印', print_html)
        self.assertIn('PAYACT-A座-501', print_html)

    def test_paid_bills_available_for_invoice_even_without_existing_invoice(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '待开发票业主', '13900003333')
        room_id = create_room(db, building='INVAVAIL', unit='B座', room_number='701', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-04', amount=188, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=188, method='transfer', operator='开票员')
        db.close()

        status, body = http_get('/invoices?period=2034-04-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'value="{bill_id}"', body)
        self.assertIn('INVAVAIL-701', body)
        self.assertIn('待开发票业主', body)

    def test_range_paid_bills_are_available_for_invoice_by_inner_month(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '区间待开发票业主', '13900007777')
        room_id = create_room(db, building='INVRANGE', unit='B座', room_number='808', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-06~2034-09', amount=488, status='paid', owner_id=owner_id)
        create_payment(db, bill_id=bill_id, amount=488, method='transfer', operator='开票员')
        db.close()

        status, body = http_get('/invoices?period=2034-07-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'value="{bill_id}"', body)
        self.assertIn('INVRANGE-808', body)
        self.assertIn('区间待开发票业主', body)

    def test_invoice_print_link_opens_in_current_window_and_has_content(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '发票打印业主', '13900005555')
        room_id = create_room(db, building='INVOICEPRINT', unit='A座', room_number='1701', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, fee_type_id=1, period='2034-06', amount=188, status='paid', owner_id=owner_id)
        invoice_id = db.execute("""
            INSERT INTO invoices(bill_id, invoice_number, amount, issue_date, buyer_name, buyer_tax_id)
            VALUES(?, 'INV-PRINT-001', 188, '2034-06-02', '发票打印抬头', 'TAX001')
        """, (bill_id,)).lastrowid
        db.commit()
        db.close()

        status, page = http_get('/invoices?period=2034-06', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'href="/invoices/{invoice_id}/print"', page)
        self.assertNotIn(f'href="/invoices/{invoice_id}/print" class="btn btn-sm btn-outline-info" target="_blank"', page)

        status, print_page = http_get(f'/invoices/{invoice_id}/print', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('电子发票', print_page)
        self.assertIn('INV-PRINT-001', print_page)
        self.assertIn('发票打印抬头', print_page)
        self.assertIn('188.00', print_page)
        self.assertIn('电子发票（普通发票）', print_page)
        self.assertIn('购买方信息', print_page)
        self.assertIn('销售方信息', print_page)
        self.assertIn('价税合计（大写）', print_page)
        self.assertIn('价税合计（小写）', print_page)
        self.assertIn('壹佰捌拾捌元整', print_page)
        self.assertIn('本系统打印样式，仅用于内部留存', print_page)

    def test_audit_logs_details_are_readable_and_admin_can_delete_selected(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,old_value,new_value,reason) VALUES(?,?,?,?,?,?,?,?,?)",
                   ('乱码测试', 'bill', 1, 'admin', 'admin', '127.0.0.1', '{"amount":100}', '{"amount":120}', '详情核对'))
        log_id = db.execute("SELECT MAX(id) FROM audit_logs WHERE action='乱码测试'").fetchone()[0]
        db.commit(); db.close()

        status, html = http_get('/audit_logs?keyword=%E4%B9%B1%E7%A0%81%E6%B5%8B%E8%AF%95', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('选择', html)
        self.assertIn('格式化详情', html)
        self.assertIn('action="/audit_logs/delete"', html)
        self.assertIn('amount', html)

        status, body, loc = http_post('/audit_logs/delete', {'log_ids': str(log_id)}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        exists = db.execute('SELECT COUNT(*) FROM audit_logs WHERE id=?', (log_id,)).fetchone()[0]
        db.close()
        self.assertEqual(exists, 0)

    def test_backup_page_has_direct_preview_action(self):
        import server.db as db_module
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, page = http_get('/backups', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'/backups/{name}/preview', page)

        status, preview = http_get(f'/backups/{name}/preview', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('备份预览', preview)
        self.assertIn('备份数据摘要', preview)
        self.assertNotIn('确认恢复', preview)

    def test_closing_page_has_non_writing_preview_button(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '结账预览业主', '13900004444')
        room_id = create_room(db, building='CLOSEPRE', unit='A座', room_number='601', owner_id=owner_id)
        create_bill(db, room_id=room_id, fee_type_id=1, period='2034-05', amount=99, status='unpaid', owner_id=owner_id)
        db.close()

        status, page = http_get('/closing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('提前预览', page)
        self.assertIn('name="preview" value="1"', page)

        status, preview, loc = http_post('/closing/close', {'period': '2034-05', 'preview': '1'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('结账前预览', preview)
        self.assertIn('本次将结账的账单明细', preview)
        self.assertIn('CLOSEPRE-A座-601', preview)
        self.assertIn('99.00', preview)
        self.assertIn('未缴', preview)
        self.assertIn('确认结账', preview)
        db = db_module.get_db()
        closed = db.execute("SELECT COUNT(*) FROM closing_records WHERE period='2034-05'").fetchone()[0]
        db.close()
        self.assertEqual(closed, 0)


    def test_owner_portal_routes_are_removed(self):
        for path in ['/owner-portal', '/owner-portal/login', '/owner-portal/bills', '/owner-portal/payment-orders']:
            status, body = http_get(path, '', TEST_PORT)
            self.assertEqual(status, 404, path)
            self.assertIn('页面未找到', body)
            self.assertNotIn('业主端已停用', body)

        for path in ['/api/v1/owner-portal/send-code', '/api/v1/owner-portal/login']:
            status, body, loc = http_post(path, {'phone': '13800138000', 'code': '123456'}, '', TEST_PORT)
            self.assertEqual(status, 404, path)
            payload = json.loads(body)
            self.assertFalse(payload['ok'])
            self.assertEqual(payload['error']['code'], 'not_found')

    def test_payment_orders_module_is_removed_from_backend(self):
        status, body = http_get('/payment_orders', self.cookie, TEST_PORT)
        self.assertEqual(status, 404)
        self.assertIn('页面未找到', body)

        status, body = http_get('/', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('href="/payment_orders"', body)
        self.assertNotIn('支付订单', body)

    def test_billing_period_filter_helper_uses_start_month_for_range_periods(self):
        from server.billing_periods import period_filter_clause
        clause, params = period_filter_clause('2026-06-01', 'b.billing_period')
        self.assertIn('substr', clause)
        self.assertEqual(params, ['2026-06', '2026-06', '2026-06'])


    def test_fee_scope_helper_centralizes_property_and_commercial_fee_groups(self):
        from server.billing_rules import fee_in_scope
        self.assertTrue(fee_in_scope({'name': '物业费(商户)', 'sort_order': 10}, 'property'))
        self.assertFalse(fee_in_scope({'name': '泄水费', 'sort_order': 17}, 'property'))
        self.assertTrue(fee_in_scope({'name': '泄水费', 'sort_order': 17}, 'commercial'))
        self.assertTrue(fee_in_scope({'name': '水费(非居民)', 'sort_order': 5}, 'commercial'))


    def test_billing_calc_get_redirects_back_to_billing_page(self):
        status, body = http_get('/billing/calc', self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        # Browser refresh/back after submit must not leave user on an invalid POST-only URL.
        import http.client
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/billing/calc', headers={'Cookie': self.cookie})
        resp = conn.getresponse()
        resp.read()
        loc = resp.getheader('Location', '')
        conn.close()
        self.assertTrue(loc.startswith('/billing?flash='), loc)

    def test_billing_calc_generates_only_selected_fee_types(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('选择收费业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('SELECTFEE', 'A座', '901', 9, '居民', 10, owner_id)
        ).lastrowid
        db.commit()
        db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2031-01-01',
            'period_end': '2031-02-01',
            'fee_types': '1',
            'custom_amount_1': '19.00',
            'custom_amount_3': '99.00',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = db_module.get_db()
        rows = db.execute(
            "SELECT fee_type_id,amount FROM bills WHERE room_id=? AND billing_period='2031-01~2031-02' ORDER BY fee_type_id",
            (room_id,)
        ).fetchall()
        db.close()
        self.assertEqual([r['fee_type_id'] for r in rows], [1])
        self.assertEqual(rows[0]['amount'], 19)

    def test_billing_calc_existing_bill_redirects_to_room_all_statuses(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('重复收费业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('EXISTBILL', 'A座', '1705', 17, '商户', 85.4, owner_id)
        ).lastrowid
        db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, 2, '2031-11~2031-12', 854, '2031-12-01', 'paid', 'EXIST-1705-001')
        )
        db.commit()
        db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2031-11-01',
            'period_end': '2031-12-01',
            'fee_types': '2',
            'custom_amount_2': '854.00',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        decoded = urllib.parse.unquote(loc)
        self.assertIn('/bills?period=2031-11~2031-12', decoded)
        self.assertNotIn('keyword=', decoded)
        self.assertIn('已存在账单，未重复生成', decoded)

    def test_bill_generate_preview_does_not_write_until_confirmed(self):
        http_post('/rooms/create', {
            'building': 'PREVIEW', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period': '2026-10',
            'fee_type_ids': '1',
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('生成账单预览', html)
        self.assertIn('将生成账单', html)
        self.assertIn('跳过重复', html)
        self.assertIn('PREVIEW', html)
        self.assertIn('确认生成账单', html)

        import server.db as db_module
        db = db_module.get_db()
        before = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2026-10'").fetchone()[0]
        db.close()
        self.assertEqual(before, 0)

        status, body, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2026-10',
            'fee_type_ids': '1',
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)
        db = db_module.get_db()
        after = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2026-10'").fetchone()[0]
        db.close()
        self.assertGreater(after, 0)


    def test_bill_generate_filters_by_building_before_confirm(self):
        http_post('/rooms/create', {
            'building': 'FILTER-A', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/rooms/create', {
            'building': 'FILTER-B', 'unit': 'A座', 'room_number': '802',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'preview',
            'period': '2026-11',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'FILTER-A',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('FILTER-A', html)
        self.assertNotIn('FILTER-B', html)

        status, body, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2026-11',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'FILTER-A',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)

        import server.db as db_module
        db = db_module.get_db()
        counts = dict(db.execute(
            "SELECT r.building, COUNT(*) FROM bills b JOIN rooms r ON b.room_id=r.id WHERE b.billing_period='2026-11' GROUP BY r.building"
        ).fetchall())
        db.close()
        self.assertEqual(counts.get('FILTER-A'), 1)
        self.assertIsNone(counts.get('FILTER-B'))










    def test_bills_review_workbench_lists_adjusted_bills_with_edit_links(self):
        http_post('/rooms/create', {
            'building': 'REVIEW', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-11',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'REVIEW',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2027-11' LIMIT 1").fetchone()['id'])
        db.close()

        http_post('/bills/batch_edit/apply', {
            'bill_ids': bid,
            'due_date': '2027-11-30',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '核对工作台测试',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills/review?period=2027-11&scope=adjusted', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单核对工作台', html)
        self.assertIn('人工修正', html)
        self.assertIn('REVIEW-A座-801', html)
        self.assertIn('19.00', html)
        self.assertIn('20.90', html)
        self.assertIn('2027-11-30', html)
        self.assertIn(f'href="/bills/{bid}/edit"', html)

    def test_bill_generation_result_links_to_review_workbench(self):
        http_post('/rooms/create', {
            'building': 'REVIEWLINK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-12',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'REVIEWLINK',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('去核对工作台', html)
        self.assertIn('/bills/review?period=2027-12', html)

    def test_bill_batch_edit_preview_shows_changes_without_updating(self):
        http_post('/rooms/create', {
            'building': 'BATCHPREVIEW', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-10',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHPREVIEW',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2027-10' LIMIT 1").fetchone()['id'])
        db.close()

        status, preview_html, loc = http_post('/bills/batch_edit/preview', {
            'bill_ids': bid,
            'due_date': '2027-10-31',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '预览确认测试',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正预览', preview_html)
        self.assertIn('原金额', preview_html)
        self.assertIn('新金额', preview_html)
        self.assertIn('19.00', preview_html)
        self.assertIn('20.90', preview_html)
        self.assertIn('2027-10-28', preview_html)
        self.assertIn('2027-10-31', preview_html)
        self.assertIn('action="/bills/batch_edit/apply"', preview_html)
        self.assertIn('确认执行批量修正', preview_html)

        db = db_module.get_db()
        bill = db.execute("SELECT amount,due_date,notes FROM bills WHERE id=?", (bid,)).fetchone()
        db.close()
        self.assertEqual(bill['amount'], 19)
        self.assertEqual(bill['due_date'], '2027-10-28')
        self.assertTrue(not bill['notes'])

    def test_bill_edit_creates_auto_backup_before_adjustment(self):
        http_post('/rooms/create', {
            'building': 'EDITBACKUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-08', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'EDITBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = db.execute("SELECT id FROM bills WHERE billing_period='2028-08' LIMIT 1").fetchone()['id']
        db.close()
        before = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_bill_adjustment_')] if os.path.exists(db_module.BACKUP_DIR) else []

        status, body, loc = http_post(f'/bills/{bid}/edit', {
            'new_amount': '18.00',
            'due_date': '2028-08-31',
            'notes': '单笔修正自动备份测试',
            'approved_by': '备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        after = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_bill_adjustment_')]
        self.assertGreater(len(after), len(before))

    def test_bill_batch_edit_result_shows_auto_backup_restore_link(self):
        http_post('/rooms/create', {
            'building': 'BATCHBACKUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-09', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BATCHBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-09' LIMIT 1").fetchone()['id'])
        db.close()

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': bid,
            'due_date': '2028-09-30',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '批量修正自动备份测试',
            'approved_by': '备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动备份', result_html)
        self.assertRegex(result_html, r'action="/backups/auto_before_batch_adjustment_[^"]+\.db/restore"')

    def test_bill_batch_edit_result_shows_before_after_details(self):
        http_post('/rooms/create', {
            'building': 'BATCHDETAIL', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-09',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHDETAIL',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2027-09' LIMIT 1").fetchone()['id'])
        db.close()

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': bid,
            'due_date': '2027-09-30',
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '结果详情测试',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正明细', result_html)
        self.assertIn('原金额', result_html)
        self.assertIn('新金额', result_html)
        self.assertIn('19.00', result_html)
        self.assertIn('20.90', result_html)
        self.assertIn('2027-09-28', result_html)
        self.assertIn('2027-09-30', result_html)
        self.assertIn('/bills/review?scope=adjusted', result_html)

    def test_bill_batch_edit_adjusts_amount_by_percent_and_records_adjustments(self):
        for room_no in ('803', '804'):
            http_post('/rooms/create', {
                'building': 'BATCHAMT', 'unit': 'A座', 'room_number': room_no,
                'floor': '8', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-08',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHAMT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2027-08' ORDER BY id").fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': ','.join(ids),
            'amount_adjust_mode': 'percent',
            'amount_percent': '10',
            'notes': '统一上调10%',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正结果', result_html)

        db = db_module.get_db()
        amounts = [r['amount'] for r in db.execute("SELECT amount FROM bills WHERE id IN (?, ?) ORDER BY id", ids).fetchall()]
        adj_count = db.execute("SELECT COUNT(*) FROM bill_adjustments WHERE bill_id IN (?, ?)", ids).fetchone()[0]
        db.close()
        self.assertEqual(amounts, [20.9, 20.9])
        self.assertEqual(adj_count, 2)

    def test_bill_batch_edit_updates_due_date_and_notes_for_selected_bills(self):
        for room_no in ('801', '802'):
            http_post('/rooms/create', {
                'building': 'BATCHEDIT', 'unit': 'A座', 'room_number': room_no,
                'floor': '8', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-07',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'BATCHEDIT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2027-07' ORDER BY id").fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        back_url = '/bills?period=2027-07&building=BATCHEDIT'
        status, form_html, loc = http_post('/bills/batch_edit', {
            'bill_ids': ','.join(ids),
            'back': back_url,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正账单', form_html)
        self.assertIn('name="due_date"', form_html)
        self.assertIn('name="notes"', form_html)
        self.assertIn(f'name="back" value="{back_url.replace("&", "&amp;")}"', form_html)
        self.assertIn(f'href="{back_url.replace("&", "&amp;")}"', form_html)

        status, preview_html, loc = http_post('/bills/batch_edit/preview', {
            'bill_ids': ','.join(ids),
            'due_date': '2027-07-31',
            'notes': '统一调整截止日',
            'back': back_url,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'name="back" value="{back_url.replace("&", "&amp;")}"', preview_html)
        self.assertIn(f'href="{back_url.replace("&", "&amp;")}"', preview_html)

        status, result_html, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': ','.join(ids),
            'due_date': '2027-07-31',
            'notes': '统一调整截止日',
            'back': back_url,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量修正结果', result_html)
        self.assertIn('更新账单', result_html)
        self.assertIn(f'href="{back_url.replace("&", "&amp;")}"', result_html)

        db = db_module.get_db()
        rows = db.execute("SELECT due_date, notes FROM bills WHERE id IN (?, ?) ORDER BY id", ids).fetchall()
        db.close()
        self.assertEqual([r['due_date'] for r in rows], ['2027-07-31', '2027-07-31'])
        self.assertEqual([r['notes'] for r in rows], ['统一调整截止日', '统一调整截止日'])

    def test_bill_edit_updates_amount_due_date_and_notes(self):
        http_post('/rooms/create', {
            'building': 'EDITBILL', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-06',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'EDITBILL',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = db.execute("SELECT id FROM bills WHERE billing_period='2027-06' ORDER BY id DESC LIMIT 1").fetchone()['id']
        db.close()

        status, form = http_get(f'/bills/{bid}/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="due_date"', form)
        self.assertIn('name="notes"', form)

        status, body, loc = http_post(f'/bills/{bid}/edit', {
            'new_amount': '88.88',
            'due_date': '2027-06-30',
            'notes': '人工核对修正',
            'approved_by': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = db_module.get_db()
        bill = db.execute("SELECT amount,due_date,notes FROM bills WHERE id=?", (bid,)).fetchone()
        db.close()
        self.assertEqual(bill['amount'], 88.88)
        self.assertEqual(bill['due_date'], '2027-06-30')
        self.assertEqual(bill['notes'], '人工核对修正')

    def test_bill_generate_result_has_direct_edit_links(self):
        http_post('/rooms/create', {
            'building': 'EDITLINK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-05',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'EDITLINK',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('直接修正', html)
        self.assertRegex(html, r'href="/bills/\d+/edit"')

    def test_bill_generate_result_can_undo_created_unpaid_bills(self):
        http_post('/rooms/create', {
            'building': 'UNDO', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-03',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'UNDO',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('撤销本次生成', html)

        import re
        action = re.search(r'action="(/bills/undo_generated)"', html).group(1)
        ids = re.search(r'name="bill_ids" value="([^"]+)"', html).group(1)
        status, result_html, loc = http_post(action, {
            'period': '2027-03',
            'bill_ids': ids,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('撤销生成结果', result_html)
        self.assertIn('删除账单', result_html)
        self.assertIn('跳过账单', result_html)

        import server.db as db_module
        db = db_module.get_db()
        count = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period='2027-03'").fetchone()[0]
        db.close()
        self.assertEqual(count, 0)

    def test_bill_generate_undo_skips_paid_bills(self):
        http_post('/rooms/create', {
            'building': 'UNDOPAID', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-04',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'UNDOPAID',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bill = db.execute("SELECT id, amount FROM bills WHERE billing_period='2027-04' LIMIT 1").fetchone()
        db.close()
        self.assertIsNotNone(bill)

        http_post(f'/bills/{bill["id"]}/pay', {
            'amount_paid': str(bill['amount']),
            'payment_method': 'cash',
            'operator': '测试',
        }, self.cookie, TEST_PORT)

        status, result_html, loc = http_post('/bills/undo_generated', {
            'period': '2027-04',
            'bill_ids': str(bill['id']),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('撤销生成结果', result_html)
        self.assertIn('跳过账单', result_html)
        self.assertIn('已有缴费记录', result_html)

        db = db_module.get_db()
        count = db.execute("SELECT COUNT(*) FROM bills WHERE id=?", (bill['id'],)).fetchone()[0]
        db.close()
        self.assertEqual(count, 1)

    def test_bill_generate_result_can_export_created_bills_csv(self):
        http_post('/rooms/create', {
            'building': 'EXPORTGEN', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-02',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'EXPORTGEN',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('/bills/export_generated?', html)

        import re
        path = re.search(r'href="(/bills/export_generated\?ids=[^"]+)"', html).group(1).replace('&amp;', '&')
        status, csv_body = http_get(path, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('票据编号,楼栋,房号', csv_body)
        self.assertIn('EXPORTGEN', csv_body)
        self.assertIn('物业费(居民)', csv_body)

    def test_bill_generate_result_shows_review_warnings(self):
        http_post('/rooms/create', {
            'building': 'WARN', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '0',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2027-01',
            'fee_type_ids': '7',
            'due_day': '28',
            'building': 'WARN',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('异常核对清单', html)
        self.assertIn('无业主', html)
        self.assertIn('面积为0', html)
        self.assertIn('WARN-801', html)

    def test_bill_generate_confirm_creates_auto_backup_restore_link(self):
        http_post('/rooms/create', {
            'building': 'GENBACKUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-10', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'GENBACKUP',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动备份', html)
        self.assertRegex(html, r'action="/backups/auto_before_bill_generation_[^"]+\.db/restore"')

    def test_bill_generate_confirm_shows_result_details(self):
        http_post('/rooms/create', {
            'building': 'RESULT', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)

        status, html, loc = http_post('/bills/generate', {
            'mode': 'confirm',
            'period': '2026-12',
            'fee_type_ids': '1',
            'due_day': '28',
            'building': 'RESULT',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', html)
        self.assertIn('本次生成账单', html)
        self.assertIn('金额合计', html)
        self.assertIn('RESULT-801', html)
        self.assertIn('物业费(居民)', html)
        self.assertIn('查看账单列表', html)

    def test_bill_generate(self):
        self._ensure_room_for_billing()
        status, body, loc = http_post('/bills/generate', {
            'period': '2026-06',
            'fee_type_ids': '1,3,4,7,8',
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)
        self.assertIn('本次生成账单', body)

    def test_bills_list_shows_generated(self):
        self._ensure_room_for_billing()
        http_post('/bills/generate', {
            'period': '2026-06', 'fee_type_ids': '1,3', 'due_day': '28',
        }, self.cookie, TEST_PORT)
        _, body = http_get('/bills?period=2026-06', self.cookie, TEST_PORT)
        self.assertIn('2026-06', body)

    def test_bills_default_list_shows_paid_bills_after_returning_from_print(self):
        http_post('/rooms/create', {
            'building': 'BILLDEFAULT', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2026-05', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BILLDEFAULT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bill = db.execute(
            "SELECT id,bill_number FROM bills WHERE billing_period='2026-05' AND room_id=(SELECT id FROM rooms WHERE building='BILLDEFAULT' LIMIT 1)"
        ).fetchone()
        bid = str(bill['id'])
        bill_number = bill['bill_number']
        db.close()

        http_post(f'/bills/{bid}/pay', {
            'amount_paid': '19',
            'payment_method': 'cash',
            'operator': '默认列表测试员',
        }, self.cookie, TEST_PORT)

        status, body = http_get('/bills?period=2026-05', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(bill_number, body)
        self.assertIn('已缴', body)

    def test_bill_detail_return_preserves_list_filters(self):
        http_post('/rooms/create', {
            'building': 'BACKFILTER', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-09', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BACKFILTER',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2029-09' LIMIT 1").fetchone()['id'])
        db.close()

        status, html = http_get('/bills?period=2029-09&building=BACKFILTER&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'/bills/{bid}?back=', html)
        self.assertIn('period%3D2029-09', html)
        self.assertIn('building%3DBACKFILTER', html)

        status, detail = http_get(f'/bills/{bid}?back=/bills%3Fperiod%3D2029-09%26building%3DBACKFILTER%26status%3Dunpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('href="/bills?period=2029-09&amp;building=BACKFILTER&amp;status=unpaid"', detail)

    def test_bill_batch_edit_without_selection_preserves_current_bill_filters(self):
        http_post('/rooms/create', {
            'building': 'BATCHBACK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-07', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BATCHBACK',
        }, self.cookie, TEST_PORT)

        status, _, loc = http_post('/bills/batch_edit', {
            'back': '/bills?period=2029-07&building=BATCHBACK',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills?period=2029-07&building=BATCHBACK', loc)
        self.assertIn('flash=', loc)

    def test_bill_list_can_select_owner_and_room_bill_groups(self):
        http_post('/rooms/create', {
            'building': 'SELECTGROUP', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-08', 'fee_type_ids': '1,3',
            'due_day': '28', 'building': 'SELECTGROUP',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills?period=2029-08&building=SELECTGROUP', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('class="owner-group-chk"', html)
        self.assertIn('class="room-group-chk"', html)
        self.assertIn('data-owner-group="o1"', html)
        self.assertIn('data-room-group="o1r', html)
        self.assertIn('toggleBillGroup', html)
        self.assertIn(".bill-chk[data-owner-group=", html)
        self.assertIn(".bill-chk[data-room-group=", html)

    def test_bill_list_room_summary_rows_expand_their_bill_details(self):
        http_post('/rooms/create', {
            'building': 'ROOMFOLD', 'unit': 'B座', 'room_number': '1401',
            'floor': '14', 'category': '商户', 'area': '10', 'tenant_name': '房间折叠租户',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-11', 'fee_type_ids': '1,3',
            'due_day': '28', 'building': 'ROOMFOLD',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills?period=2029-11&building=ROOMFOLD', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn("onclick=\"toggleBillRoom('o1r1')\"", html)
        self.assertIn('id="icon_o1r1"', html)
        self.assertIn('class="bill-detail-o1r1"', html)
        self.assertIn('function toggleBillRoom(roomGroup)', html)
        self.assertIn('room-detail-o1 bill-room-row', html)

    def test_bill_list_groups_by_tenant_name_before_owner_name(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '账单分组业主', '13900008801')
        room_a = create_room(db, building='TENANTBILL', unit='B座', room_number='1401', category='商户', owner_id=owner_id)
        room_b = create_room(db, building='TENANTBILL', unit='B座', room_number='1402', category='商户', owner_id=owner_id)
        db.execute("UPDATE rooms SET tenant_name=? WHERE id=?", ('租户甲', room_a))
        db.execute("UPDATE rooms SET tenant_name=? WHERE id=?", ('租户乙', room_b))
        create_bill(db, room_id=room_a, owner_id=owner_id, fee_type_id=1, period='2037-01', amount=100, status='unpaid')
        create_bill(db, room_id=room_b, owner_id=owner_id, fee_type_id=1, period='2037-01', amount=200, status='unpaid')
        db.close()

        status, html = http_get('/bills?period=2037-01&building=TENANTBILL', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<strong>租户甲</strong>', html)
        self.assertIn('<strong>租户乙</strong>', html)
        self.assertNotIn('<strong>账单分组业主</strong>', html)

    def test_bill_list_delete_buttons_are_not_nested_in_batch_form(self):
        http_post('/rooms/create', {
            'building': 'DELETEONE', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-10', 'fee_type_ids': '1,3',
            'due_day': '28', 'building': 'DELETEONE',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/bills?period=2029-10&building=DELETEONE&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<form method=POST id="billActionForm"><input type="hidden" name="back" value="/bills?period=2029-10&amp;building=DELETEONE&amp;status=unpaid"></form>', html)
        self.assertIn('class=bill-chk form="billActionForm"', html)
        self.assertIn('form="billActionForm" onclick="this.form.action=', html)
        self.assertIn('/delete" style=display:inline', html)
        self.assertIn('name="back" value="/bills?period=2029-10&amp;building=DELETEONE&amp;status=unpaid"', html)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute(
            "SELECT id FROM bills WHERE billing_period='2029-10' AND room_id=(SELECT id FROM rooms WHERE building='DELETEONE' LIMIT 1) ORDER BY id"
        ).fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        status, body, loc = http_post(f'/bills/{ids[0]}/delete', {
            'back': '/bills?period=2029-10&building=DELETEONE&status=unpaid'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('period=2029-10', loc)
        self.assertIn('building=DELETEONE', loc)

        db = db_module.get_db()
        remaining = [str(r['id']) for r in db.execute(
            "SELECT id FROM bills WHERE billing_period='2029-10' AND room_id=(SELECT id FROM rooms WHERE building='DELETEONE' LIMIT 1) ORDER BY id"
        ).fetchall()]
        db.close()
        self.assertEqual(remaining, [ids[1]])

    def test_print_selected_bills_combines_multiple_items_on_one_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '合并打印业主', '13911112222')
        room_id = create_room(db, building='PRINTMERGE', unit='商场', room_number='1F-201', category='商户', area=50, owner_id=owner_id)
        bill_a = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period='2031-01', amount=100, status='unpaid')
        bill_b = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=2, period='2031-01', amount=200, status='unpaid')
        db.close()

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        params = urllib.parse.urlencode([
            ('bill_ids', str(bill_a)),
            ('bill_ids', str(bill_b)),
            ('back', '/bills?period=2031-01&building=PRINTMERGE'),
        ])
        conn.request('POST', '/bills/print_selected', params, {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        print_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('选中账单合并打印', print_html)
        self.assertIn('合计应缴', print_html)
        self.assertIn('¥300.00', print_html)
        self.assertIn('物业费(居民)', print_html)
        self.assertIn('物业费(商户)', print_html)
        self.assertEqual(print_html.count('物业管理缴费单'), 1)
        self.assertNotIn('<div class="page-break"', print_html)

    def test_bill_list_print_and_receipt_preserve_current_back_url(self):
        http_post('/rooms/create', {
            'building': 'PRINTBACK', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2029-11', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PRINTBACK',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute(
            "SELECT id FROM bills WHERE billing_period='2029-11' AND room_id=(SELECT id FROM rooms WHERE building='PRINTBACK' LIMIT 1)"
        ).fetchone()['id'])
        db.close()

        status, list_html = http_get('/bills?period=2029-11&building=PRINTBACK&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('name="back" value="/bills?period=2029-11&amp;building=PRINTBACK&amp;status=unpaid"', list_html)

        status, print_html, loc = http_post('/bills/print_selected', {
            'bill_ids': bid,
            'back': '/bills?period=2029-11&building=PRINTBACK&status=unpaid',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('href="/bills?period=2029-11&amp;building=PRINTBACK&amp;status=unpaid"', print_html)
        self.assertNotIn('href="/"', print_html)

        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': bid,
            'back': '/bills?period=2029-11&building=PRINTBACK&status=unpaid',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('href="/bills?period=2029-11&amp;building=PRINTBACK&amp;status=unpaid"', receipt_html)
        self.assertNotIn('href="/"', receipt_html)

    def test_bill_detail_with_formula(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('账单详情业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('DETAILFORMULA', 'A座', '801', 8, '居民', 100, owner_id)
        ).lastrowid
        db.commit(); db.close()
        try:
            http_post('/bills/generate', {
                'period': '2026-06', 'fee_type_ids': '1', 'due_day': '28',
                'building': 'DETAILFORMULA',
            }, self.cookie, TEST_PORT)
            db = db_module.get_db()
            bill_id = db.execute("SELECT id FROM bills WHERE room_id=? AND billing_period='2026-06' ORDER BY id DESC LIMIT 1", (room_id,)).fetchone()['id']
            db.close()
            status, body = http_get(f'/bills/{bill_id}', self.cookie, TEST_PORT)
            self.assertEqual(status, 200, msg='Bill detail page not found')
            self.assertIn('账单信息', body)
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM payments WHERE bill_id IN (SELECT id FROM bills WHERE room_id=?)', (room_id,))
            db.execute('DELETE FROM bills WHERE room_id=?', (room_id,))
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()

    def test_batch_pay_preview_shows_selected_total_without_writing(self):
        for room_no in ('901', '902'):
            http_post('/rooms/create', {
                'building': 'PAYBATCH', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-01', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYBATCH',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-01' ORDER BY id").fetchall()]
        db.close()
        self.assertEqual(len(ids), 2)

        status, html, loc = http_post('/bills/batch_pay', {
            'bill_ids': ','.join(ids),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量收费确认', html)
        self.assertIn('确认收款', html)
        self.assertIn('38.00', html)

        db = db_module.get_db()
        payment_count = db.execute("SELECT COUNT(*) FROM payments WHERE bill_id IN (?, ?)", ids).fetchone()[0]
        db.close()
        self.assertEqual(payment_count, 0)

    def test_batch_pay_confirm_creates_auto_backup_before_writing(self):
        for room_no in ('909', '910'):
            http_post('/rooms/create', {
                'building': 'PAYBACKUP', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-06', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-06' ORDER BY id").fetchall()]
        db.close()
        before = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_batch_payment_')] if os.path.exists(db_module.BACKUP_DIR) else []

        status, html, loc = http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('自动备份', html)
        after = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_batch_payment_')]
        self.assertGreater(len(after), len(before))

    def test_batch_pay_confirm_records_payments_and_result_details(self):
        for room_no in ('903', '904'):
            http_post('/rooms/create', {
                'building': 'PAYCONFIRM', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-02', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYCONFIRM',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-02' ORDER BY id").fetchall()]
        db.close()

        status, html, loc = http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '批量收费测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('批量收费结果', html)
        self.assertIn('成功收费', html)
        self.assertIn('38.00', html)
        self.assertIn('/bills/receipt_by_ids', html)

        db = db_module.get_db()
        statuses = [r['status'] for r in db.execute("SELECT status FROM bills WHERE id IN (?, ?) ORDER BY id", ids).fetchall()]
        operators = [r['operator'] for r in db.execute("SELECT operator FROM payments WHERE bill_id IN (?, ?) ORDER BY bill_id", ids).fetchall()]
        db.close()
        self.assertEqual(statuses, ['paid', 'paid'])
        self.assertEqual(operators, ['批量收费测试员', '批量收费测试员'])

    def test_receipt_by_ids_accepts_comma_separated_bill_ids(self):
        for room_no in ('905', '906'):
            http_post('/rooms/create', {
                'building': 'PAYRECEIPT', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-03', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYRECEIPT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-03' ORDER BY id").fetchall()]
        db.close()

        http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '收据测试员',
        }, self.cookie, TEST_PORT)
        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': ','.join(ids),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('PAYRECEIPT', receipt_html)
        self.assertIn('38.00', receipt_html)

    def test_single_payment_creates_auto_backup_before_writing(self):
        http_post('/rooms/create', {
            'building': 'PAYSINGLEBACKUP', 'unit': 'A座', 'room_number': '901',
            'floor': '9', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-07', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYSINGLEBACKUP',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-07' LIMIT 1").fetchone()['id'])
        db.close()
        before = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_payment_')] if os.path.exists(db_module.BACKUP_DIR) else []

        status, body, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': '19.00',
            'payment_method': 'cash',
            'operator': '单笔备份测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        after = [n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('auto_before_payment_')]
        self.assertGreater(len(after), len(before))

    def test_single_payment_rejects_amount_greater_than_remaining(self):
        http_post('/rooms/create', {
            'building': 'PAYLIMIT', 'unit': 'A座', 'room_number': '901',
            'floor': '9', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-04', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYLIMIT',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-04' LIMIT 1").fetchone()['id'])
        db.close()

        status, body, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': '20.00',
            'payment_method': 'cash',
            'operator': '超额测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('不能超过待缴金额', urllib.parse.unquote(loc))

        db = db_module.get_db()
        payment_count = db.execute("SELECT COUNT(*) FROM payments WHERE bill_id=?", (bid,)).fetchone()[0]
        status_value = db.execute("SELECT status FROM bills WHERE id=?", (bid,)).fetchone()['status']
        db.close()
        self.assertEqual(payment_count, 0)
        self.assertEqual(status_value, 'unpaid')

    def test_receipt_by_ids_shows_each_room_and_payment_operator(self):
        for room_no in ('907', '908'):
            http_post('/rooms/create', {
                'building': 'PAYRECEIPTROOM', 'unit': 'A座', 'room_number': room_no,
                'floor': '9', 'category': '居民', 'area': '10',
            }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-05', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'PAYRECEIPTROOM',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        ids = [str(r['id']) for r in db.execute("SELECT id FROM bills WHERE billing_period='2028-05' ORDER BY id").fetchall()]
        db.close()

        http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': ','.join(ids),
            'payment_method': 'wechat',
            'operator': '收据核对员',
        }, self.cookie, TEST_PORT)
        status, receipt_html, loc = http_post('/bills/receipt_by_ids', {
            'bill_ids': ','.join(ids),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收据核对信息', receipt_html)
        self.assertIn('收费员', receipt_html)
        self.assertIn('收据核对员', receipt_html)
        self.assertIn('支付方式', receipt_html)
        self.assertIn('wechat', receipt_html)
        self.assertIn('PAYRECEIPTROOM-A座-907', receipt_html)
        self.assertIn('PAYRECEIPTROOM-A座-908', receipt_html)

    def test_bill_payment_workflow(self):
        """Pay a bill, verify status changes to paid."""
        self._ensure_room_for_billing()
        http_post('/bills/generate', {
            'period': '2026-06', 'fee_type_ids': '1', 'due_day': '28',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = db.execute("SELECT id FROM bills WHERE billing_period='2026-06' ORDER BY id DESC LIMIT 1").fetchone()['id']
        db.close()

        # Get bill amount
        _, detail = http_get(f'/bills/{bid}', self.cookie, TEST_PORT)
        self.assertIn('账单信息', detail)

        # Pay the bill
        status, body, loc = http_post(f'/bills/{bid}/pay', {
            'amount_paid': '200.00', 'payment_method': 'wechat', 'operator': '测试员',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        # Verify status
        _, detail2 = http_get(f'/bills/{bid}', self.cookie, TEST_PORT)
        self.assertIn('已缴', detail2)

    # ── API endpoints ───────────────────────────────────────────

    def test_api_stats(self):
        status, body = http_get('/api/stats', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn('total_rooms', data)

    def test_api_owner_info(self):
        http_post('/owners/create', {'name': '李四', 'phone': '13900002222'},
                  self.cookie, TEST_PORT)
        import server.db as db_module
        db = db_module.get_db()
        owner = db.execute("SELECT id FROM owners WHERE phone=? ORDER BY id DESC LIMIT 1", ('13900002222',)).fetchone()
        db.close()
        status, body = http_get(f'/api/owners/{owner["id"]}/info', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data.get('name'), '李四')

    # ── Reports ─────────────────────────────────────────────────


    def test_reports_reconciliation_sections_and_export_links(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('报表对账业主', '13200000000')").lastrowid
        room_a = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('REPORTA', 'A座', '1501', 15, '居民', 70, ?)
        """, (owner_id,)).lastrowid
        room_b = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('REPORTB', 'A座', '1502', 15, '居民', 80, ?)
        """, (owner_id,)).lastrowid
        paid_bill = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-11', 100, '2030-11-28', 'paid', 'RPT-PAID')
        """, (room_a, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 100, 'cash', '报表员')", (paid_bill,))
        partial_bill = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-11', 80, '2030-11-28', 'partial', 'RPT-PARTIAL')
        """, (room_a, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 30, 'cash', '报表员')", (partial_bill,))
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-11', 60, '2030-11-28', 'unpaid', 'RPT-UNPAID')
        """, (room_b, owner_id))
        db.commit()
        db.close()

        status, html = http_get('/reports?period=2030-11', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('账期对账', html)
        self.assertIn('楼栋对账统计', html)
        self.assertIn('欠费清单', html)
        self.assertIn('应收合计', html)
        self.assertIn('已收合计', html)
        self.assertIn('未收合计', html)
        self.assertIn('收缴率', html)
        self.assertIn('240.00', html)
        self.assertIn('130.00', html)
        self.assertIn('110.00', html)
        self.assertIn('REPORTA', html)
        self.assertIn('REPORTB', html)
        self.assertIn('RPT-PARTIAL', html)
        self.assertIn('RPT-UNPAID', html)
        self.assertIn('/reports/reconciliation.csv?period=2030-11', html)

    def test_reports_can_select_multi_month_billing_period(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('跨月报表业主', '13200001111')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('RANGE_REPORT', 'A座', '1601', 16, '商户', 90, ?)
        """, (owner_id,)).lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-07~2030-10', 400, '2030-10-28', 'partial', 'RANGE-RPT')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 150, 'cash', '报表员')", (bill_id,))
        db.commit()
        db.close()

        status, html = http_get('/reports?period=2030-07~2030-10', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('账期对账 <small class="text-muted">(2030-07~2030-10)</small>', html)
        self.assertIn('RANGE-RPT', html)
        self.assertIn('400.00', html)
        self.assertIn('150.00', html)
        self.assertIn('<option value="2030-07~2030-10" selected>2030-07~2030-10</option>', html)
        self.assertIn('/reports/reconciliation.csv?period=2030-07~2030-10', html)

        status, inner_html = http_get('/reports?period=2030-08', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('RANGE-RPT', inner_html)
        self.assertIn('RANGE_REPORT', inner_html)
        self.assertIn('应收总额</div><div class="metric-value money">¥400.00</div>', inner_html)
        self.assertIn('已收总额</div><div class="metric-value money money-paid">¥150.00</div>', inner_html)
        self.assertRegex(inner_html, r'(?s)楼栋缴费统计.*RANGE_REPORT.*¥400\.00.*¥150\.00')



    def test_reports_reconciliation_print_page_uses_current_filters(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('打印对账业主', '12900000000')").lastrowid
        room_a = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('PRINTA', 'A座', '1801', 18, '居民', 70, ?)
        """, (owner_id,)).lastrowid
        room_b = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('PRINTB', 'A座', '1802', 18, '居民', 70, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-10', 120, '2030-10-28', 'unpaid', 'PRINT-A-UNPAID')
        """, (room_a, owner_id))
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-10', 90, '2030-10-28', 'paid', 'PRINT-B-PAID')
        """, (room_b, owner_id))
        db.commit()
        db.close()

        status, html = http_get('/reports?period=2030-10&building=PRINTA&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('/reports/reconciliation/print?period=2030-10&amp;building=PRINTA&amp;status=unpaid', html)

        status, print_html = http_get('/reports/reconciliation/print?period=2030-10&building=PRINTA&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('对账单打印', print_html)
        self.assertIn('2030-10', print_html)
        self.assertIn('PRINTA', print_html)
        self.assertIn('未缴', print_html)
        self.assertIn('PRINT-A-UNPAID', print_html)
        self.assertNotIn('PRINT-B-PAID', print_html)
        self.assertIn('window.print()', print_html)
        self.assertIn('@media print', print_html)

    def test_reports_reconciliation_filters_by_building_and_status(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('筛选对账业主', '13000000000')").lastrowid
        room_a = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('FILTERA', 'A座', '1701', 17, '居民', 70, ?)
        """, (owner_id,)).lastrowid
        room_b = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('FILTERB', 'A座', '1702', 17, '居民', 70, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-09', 70, '2030-09-28', 'unpaid', 'FILTER-A-UNPAID')
        """, (room_a, owner_id))
        paid_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-09', 90, '2030-09-28', 'paid', 'FILTER-B-PAID')
        """, (room_b, owner_id)).lastrowid
        db.execute("INSERT INTO payments(bill_id, amount_paid, payment_method, operator) VALUES(?, 90, 'cash', '筛选员')", (paid_id,))
        db.commit()
        db.close()

        status, html = http_get('/reports?period=2030-09&building=FILTERA&status=unpaid', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('FILTERA', html)
        self.assertIn('FILTER-A-UNPAID', html)
        self.assertNotIn('FILTER-B-PAID', html)
        self.assertIn('name="status"', html)
        self.assertIn('/reports/reconciliation.csv?period=2030-09&amp;building=FILTERA&amp;status=unpaid', html)

        status, csv = http_get('/reports/reconciliation.csv?period=2030-09&building=FILTERA&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('FILTER-A-UNPAID', csv)
        self.assertNotIn('FILTER-B-PAID', csv)

    def test_reports_reconciliation_csv_export(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('CSV对账业主', '13100000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('REPORTCSV', 'A座', '1601', 16, '居民', 75, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-08', 88, '2030-08-28', 'unpaid', 'RPT-CSV')
        """, (room_id, owner_id))
        db.commit()
        db.close()

        status, csv = http_get('/reports/reconciliation.csv?period=2030-08', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('building,room,owner,phone,fee_type,period,amount,paid,due,status,due_date,bill_number', csv)
        self.assertIn('REPORTCSV', csv)
        self.assertIn('RPT-CSV', csv)
        self.assertIn('88.00', csv)

    def test_reports_page(self):
        _, body = http_get('/reports?period=2026-06', self.cookie, TEST_PORT)
        self.assertIn('对账报表', body)
        self.assertIn('应收总额', body)

    # ── CSV export ──────────────────────────────────────────────

    def test_bill_export_csv(self):
        self._ensure_room_for_billing()
        http_post('/bills/generate', {
            'period': '2026-06', 'fee_type_ids': '1', 'due_day': '28',
        }, self.cookie, TEST_PORT)

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', '/bills/export?period=2026-06',
                     headers={'Cookie': self.cookie})
        resp = conn.getresponse()
        data = resp.read().decode('utf-8-sig')
        ct = resp.headers.get('Content-Type', '')
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn('票据编号', data)
        self.assertIn('csv', ct)


    def test_commercial_fee_group_add_button_preserves_group_context(self):
        status, body = http_get('/fee_types?group=commercial', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('/fee_types/create?group=commercial', body)

        status, body = http_get('/fee_types/create?group=commercial', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('添加商业公司收费项目', body)
        self.assertIn('name="return_group" value="commercial"', body)

        status, body, loc = http_post('/fee_types/create', {
            'name': '测试商业收费项',
            'calc_method': 'fixed',
            'unit_price': '12.5',
            'unit': '元',
            'billing_cycle': 'monthly',
            'sort_order': '39',
            'is_active': 'on',
            'notes': '商业测试收费',
            'reminder_advance_days': '15',
            'return_group': 'commercial',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/fee_types?group=commercial&flash=', loc)

        _, body = http_get('/fee_types?group=commercial', self.cookie, TEST_PORT)
        self.assertIn('测试商业收费项', body)

    def test_fee_type_edit_allows_blank_optional_numbers(self):
        status, _, loc = http_post('/fee_types/13/edit', {
            'name': '泄水费',
            'calc_method': 'area',
            'unit_price': '1.5',
            'unit': '元/m²·月',
            'billing_cycle': 'monthly',
            'sort_order': '',
            'is_active': 'on',
            'notes': '排水设施维护费',
            'reminder_advance_days': '',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/fee_types/13/edit?flash=', loc)

    def test_fee_type_edit_stays_on_edit_page_after_save(self):
        status, _, loc = http_post('/fee_types/10/edit', {
            'name': '垃圾清运费',
            'calc_method': 'household',
            'unit_price': '30',
            'unit': '元/户',
            'billing_cycle': 'monthly',
            'sort_order': '32',
            'is_active': 'on',
            'notes': '商业垃圾清运服务费',
            'reminder_advance_days': '30',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/fee_types/10/edit?flash=', loc)

    def test_fee_type_create_saves_new_tiers_and_generates_with_tier_rate(self):
        status, body, loc = http_post('/fee_types/create', {
            'name': '自定义分档面积费',
            'calc_method': 'area',
            'unit_price': '9',
            'unit': '元/m²·月',
            'billing_cycle': 'monthly',
            'sort_order': '96',
            'is_active': 'on',
            'notes': '测试分档',
            'reminder_advance_days': '30',
            'new_tier_cat': '商户',
            'new_tier_rate': '7',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        import server.db as db_module
        db = db_module.get_db()
        ft = db.execute("SELECT id FROM fee_types WHERE name='自定义分档面积费'").fetchone()
        self.assertIsNotNone(ft)
        tier = db.execute("SELECT rate FROM fee_type_tiers WHERE fee_type_id=? AND category='商户'", (ft['id'],)).fetchone()
        db.close()
        self.assertIsNotNone(tier)
        self.assertEqual(tier['rate'], 7)

        http_post('/rooms/create', {
            'building': 'TIER', 'unit': 'A座', 'room_number': '701',
            'floor': '7', 'category': '商户', 'area': '10',
        }, self.cookie, TEST_PORT)
        status, body, loc = http_post('/bills/generate', {
            'period': '2026-09',
            'fee_type_ids': str(ft['id']),
            'due_day': '28',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成结果', body)

        db = db_module.get_db()
        bill = db.execute("""
            SELECT b.amount FROM bills b
            JOIN rooms r ON b.room_id=r.id
            WHERE b.billing_period='2026-09' AND b.fee_type_id=?
              AND r.building='TIER' AND r.room_number='701'
        """, (ft['id'],)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['amount'], 70)

    # ── Backup ──────────────────────────────────────────────────

    def test_backup_page_labels_and_filters_auto_backup_types(self):
        http_post('/rooms/create', {
            'building': 'BACKUPFILTER', 'unit': 'A座', 'room_number': '801',
            'floor': '8', 'category': '居民', 'area': '10',
        }, self.cookie, TEST_PORT)
        http_post('/bills/generate', {
            'mode': 'confirm', 'period': '2028-11', 'fee_type_ids': '1',
            'due_day': '28', 'building': 'BACKUPFILTER',
        }, self.cookie, TEST_PORT)

        import server.db as db_module
        db = db_module.get_db()
        bid = str(db.execute("SELECT id FROM bills WHERE billing_period='2028-11' LIMIT 1").fetchone()['id'])
        db.close()
        http_post('/bills/batch_pay', {
            'confirm': '1',
            'bill_ids': bid,
            'payment_method': 'wechat',
            'operator': '备份分类测试员',
        }, self.cookie, TEST_PORT)

        status, html = http_get('/backups', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成前', html)
        self.assertIn('批量收费前', html)
        self.assertIn('name="type"', html)

        status, filtered = http_get('/backups?type=bill_generation', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('账单生成前', filtered)
        self.assertNotIn('auto_before_batch_payment_', filtered)





    def test_closing_close_shows_precheck_before_writing_record(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('结账检查业主', '13400000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSECHECK', 'A座', '1301', 13, '居民', 90, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-03', 100, '2030-03-28', 'paid', 'CC-PAID')
        """, (room_id, owner_id))
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-03', 80, '2030-03-28', 'partial', 'CC-PARTIAL')
        """, (room_id, owner_id))
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-03', 60, '2030-03-28', 'unpaid', 'CC-UNPAID')
        """, (room_id, owner_id))
        db.commit()
        db.close()

        status, html, loc = http_post('/closing/close', {'period': '2030-03', 'notes': '月末结账'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('结账前检查', html)
        self.assertIn('2030-03', html)
        self.assertIn('未缴账单', html)
        self.assertIn('部分缴费', html)
        self.assertIn('异常提醒', html)
        self.assertIn('应收合计', html)
        self.assertIn('本次将结账的账单明细', html)
        self.assertIn('CC-PAID', html)
        self.assertIn('CC-PARTIAL', html)
        self.assertIn('CC-UNPAID', html)
        self.assertIn('240.00', html)
        self.assertIn('确认结账', html)
        db = db_module.get_db()
        closed = db.execute("SELECT COUNT(*) FROM closing_records WHERE period='2030-03' AND status='closed'").fetchone()[0]
        db.close()
        self.assertEqual(closed, 0)


    def test_reopen_closing_requires_confirm_page_before_writing(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("""
            INSERT INTO closing_records(period, close_date, status, operator, notes, paid_count, total_amount)
            VALUES('2030-05', datetime('now','localtime'), 'closed', '管理员', '测试反结账', 3, 300)
        """)
        db.commit()
        db.close()

        status, html = http_get('/closing/reopen?period=2030-05', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('反结账确认', html)
        self.assertIn('2030-05', html)
        self.assertIn('风险提示', html)
        self.assertIn('结账金额', html)
        self.assertIn('300.00', html)
        self.assertIn('当前账单摘要', html)
        self.assertIn('确认反结账', html)
        db = db_module.get_db()
        status_value = db.execute("SELECT status FROM closing_records WHERE period='2030-05'").fetchone()['status']
        db.close()
        self.assertEqual(status_value, 'closed')

    def test_reopen_closing_post_requires_confirm_flag_and_then_reopens(self):
        import server.db as db_module
        db = db_module.get_db()
        db.execute("""
            INSERT INTO closing_records(period, close_date, status, operator, notes, paid_count, total_amount)
            VALUES('2030-06', datetime('now','localtime'), 'closed', '管理员', '测试确认反结账', 2, 200)
        """)
        db.commit()
        db.close()

        status, html, loc = http_post('/closing/reopen', {'period': '2030-06'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('反结账确认', html)
        db = db_module.get_db()
        status_value = db.execute("SELECT status FROM closing_records WHERE period='2030-06'").fetchone()['status']
        db.close()
        self.assertEqual(status_value, 'closed')

        status, body, loc = http_post('/closing/reopen', {'period': '2030-06', 'confirm': '1'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-06', loc)
        db = db_module.get_db()
        status_value = db.execute("SELECT status FROM closing_records WHERE period='2030-06'").fetchone()['status']
        db.close()
        self.assertEqual(status_value, 'reopened')

    def test_closing_close_confirm_writes_record_after_precheck(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('确认结账业主', '13300000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSECONFIRM', 'A座', '1401', 14, '居民', 50, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-04', 95, '2030-04-28', 'paid', 'CCF-PAID')
        """, (room_id, owner_id))
        db.commit()
        db.close()

        status, body, loc = http_post('/closing/close', {'period': '2030-04', 'notes': '确认结账', 'confirm': '1'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('2030-04', loc)
        db = db_module.get_db()
        row = db.execute("SELECT status, paid_count, total_amount FROM closing_records WHERE period='2030-04'").fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['status'], 'closed')
        self.assertEqual(row['paid_count'], 1)
        self.assertEqual(row['total_amount'], 95)

    def test_closed_period_blocks_batch_pay_batch_edit_and_undo_generated(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('批量锁定业主', '13500000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSEDBATCH', 'A座', '1201', 12, '居民', 80, ?)
        """, (owner_id,)).lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-02', 152, '2030-02-28', 'unpaid', 'CB-001')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO closing_records(period, close_date, status) VALUES('2030-02', datetime('now','localtime'), 'closed')")
        db.commit()
        db.close()

        status, body, loc = http_post('/bills/batch_pay', {
            'confirm': '1', 'bill_ids': str(bill_id), 'payment_method': 'cash', 'operator': 'tester'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-02', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': str(bill_id), 'due_date': '2030-02-20', 'notes': 'closed batch edit'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-02', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post('/bills/undo_generated', {
            'period': '2030-02', 'bill_ids': str(bill_id)
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-02', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        db = db_module.get_db()
        row = db.execute("SELECT amount,due_date,status,(SELECT COUNT(*) FROM payments WHERE bill_id=?) pay_count FROM bills WHERE id=?", (bill_id, bill_id)).fetchone()
        db.close()
        self.assertEqual(row['amount'], 152)
        self.assertEqual(row['due_date'], '2030-02-28')
        self.assertEqual(row['status'], 'unpaid')
        self.assertEqual(row['pay_count'], 0)

    def test_closed_period_blocks_bill_edit_delete_and_payment(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('结账锁定业主', '13600000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSEDLOCK', 'A座', '1101', 11, '居民', 77, ?)
        """, (owner_id,)).lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-01', 146.3, '2030-01-28', 'unpaid', 'CL-001')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO closing_records(period, close_date, status) VALUES('2030-01', datetime('now','localtime'), 'closed')")
        db.commit()
        db.close()

        status, body, loc = http_post(f'/bills/{bill_id}/edit', {
            'new_amount': '99', 'due_date': '2030-01-28', 'notes': 'closed edit', 'approved_by': 'tester'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-01', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post(f'/bills/{bill_id}/pay', {
            'amount_paid': '10', 'payment_method': 'cash', 'operator': 'tester'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-01', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post(f'/bills/{bill_id}/delete', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-01', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        db = db_module.get_db()
        row = db.execute("SELECT amount, status, (SELECT COUNT(*) FROM payments WHERE bill_id=?) AS pay_count FROM bills WHERE id=?", (bill_id, bill_id)).fetchone()
        db.close()
        self.assertEqual(row['amount'], 146.3)
        self.assertEqual(row['status'], 'unpaid')
        self.assertEqual(row['pay_count'], 0)

    def test_backup_cleanup_preview_keeps_manual_backups_and_requires_confirm(self):
        import server.db as db_module
        os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
        prefix = 'auto_before_payment_'
        for old in os.listdir(db_module.BACKUP_DIR):
            if old.startswith(prefix):
                os.remove(os.path.join(db_module.BACKUP_DIR, old))
        auto_names = []
        for i in range(12):
            name = f'{prefix}_{i:02d}.db'
            fp = os.path.join(db_module.BACKUP_DIR, name)
            with open(fp, 'wb') as f:
                f.write(b'x' * (i + 1))
            os.utime(fp, (1700000000 + i, 1700000000 + i))
            auto_names.append(name)
        manual_name = 'backup_cleanup_preview_manual.db'
        with open(os.path.join(db_module.BACKUP_DIR, manual_name), 'wb') as f:
            f.write(b'manual')

        status, html = http_get('/backups/cleanup?keep=10&type=payment', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('自动备份清理预览', html)
        self.assertIn('默认只清理自动备份', html)
        self.assertIn(auto_names[0], html)
        self.assertIn(auto_names[1], html)
        self.assertNotIn(manual_name, html)
        self.assertIn('确认清理', html)
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[0])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, manual_name)))

    def test_backup_cleanup_post_deletes_only_old_auto_backups(self):
        import server.db as db_module
        os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
        prefix = 'auto_before_import_'
        for old in os.listdir(db_module.BACKUP_DIR):
            if old.startswith(prefix):
                os.remove(os.path.join(db_module.BACKUP_DIR, old))
        auto_names = []
        for i in range(12):
            name = f'{prefix}_{i:02d}.db'
            fp = os.path.join(db_module.BACKUP_DIR, name)
            with open(fp, 'wb') as f:
                f.write(b'x')
            os.utime(fp, (1710000000 + i, 1710000000 + i))
            auto_names.append(name)
        manual_name = 'backup_cleanup_post_manual.db'
        with open(os.path.join(db_module.BACKUP_DIR, manual_name), 'wb') as f:
            f.write(b'manual')

        status, body, loc = http_post('/backups/cleanup', {'keep': '10', 'type': 'import'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('%E5%B7%B2%E6%B8%85%E7%90%86%E8%87%AA%E5%8A%A8%E5%A4%87%E4%BB%BD%202%20%E4%B8%AA', loc)
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[0])))
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[1])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[-1])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, manual_name)))


    def test_backup_cleanup_post_deletes_old_startup_and_daily_auto_backups(self):
        import server.db as db_module
        os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
        for prefix in ('auto_startup_', 'auto_daily_'):
            for old in os.listdir(db_module.BACKUP_DIR):
                if old.startswith(prefix):
                    os.remove(os.path.join(db_module.BACKUP_DIR, old))
        startup_names = []
        for i in range(12):
            name = f'auto_startup_{i:02d}.db'
            fp = os.path.join(db_module.BACKUP_DIR, name)
            with open(fp, 'wb') as f:
                f.write(b'x')
            os.utime(fp, (1720000000 + i, 1720000000 + i))
            startup_names.append(name)

        status, body, loc = http_post('/backups/cleanup', {'keep': '10', 'type': 'startup'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, startup_names[0])))
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, startup_names[1])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, startup_names[-1])))

    def test_backup_delete_confirm_page_explains_deleted_backup(self):
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        import server.db as db_module
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, html = http_get(f'/backups/{name}/delete', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('删除备份确认', html)
        self.assertIn(name, html)
        self.assertIn('删除后无法从系统内恢复', html)
        self.assertIn(f'action="/backups/{name}/delete"', html)
        self.assertIn('确认删除', html)


    def test_backup_restore_confirm_page_shows_backup_data_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('备份摘要业主', '13900000000')").lastrowid
        room_id = None
        for idx in range(1, 9):
            cur = db.execute("""
                INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
                VALUES('BACKUPSUMMARY', 'A座', ?, 9, '居民', 88, ?)
            """, (f'90{idx}', owner_id))
            room_id = room_id or cur.lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2029-01', 168.8, '2029-01-28', 'paid', 'BS-001')
        """, (room_id, owner_id)).lastrowid
        db.execute("""
            INSERT INTO payments(bill_id, amount_paid, payment_method, operator)
            VALUES(?, 168.8, 'cash', '备份摘要测试员')
        """, (bill_id,))
        db.commit()
        db.close()
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, html = http_get(f'/backups/{name}/restore', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('备份数据摘要', html)
        self.assertIn('房间数', html)
        self.assertIn('业主数', html)
        self.assertIn('账单数', html)
        self.assertIn('缴费记录数', html)
        self.assertIn('账单金额合计', html)
        self.assertIn('缴费金额合计', html)
        self.assertIn('BACKUPSUMMARY', html)
        self.assertIn('2029-01', html)
        self.assertRegex(html, r'账单金额合计</td><td>\d+\.80')
        self.assertRegex(html, r'缴费金额合计</td><td>\d+\.80')

    def test_backup_restore_confirm_page_explains_risk_and_auto_backup(self):
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        import server.db as db_module
        names = sorted([n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('backup_')], reverse=True)
        self.assertTrue(names)
        name = names[0]

        status, html = http_get(f'/backups/{name}/restore', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('恢复备份确认', html)
        self.assertIn(name, html)
        self.assertIn('当前数据会先自动备份', html)
        self.assertIn(f'action="/backups/{name}/restore"', html)
        self.assertIn('确认恢复', html)


    def test_backup_restore_post_shows_result_page_with_current_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('恢复结果业主', '13700000000')").lastrowid
        room_id = None
        for idx in range(1, 9):
            cur = db.execute("""
                INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
                VALUES('RESTORERESULT', 'A座', ?, 10, '居民', 66, ?)
            """, (f'10{idx:02d}', owner_id))
            room_id = room_id or cur.lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2029-02', 125.4, '2029-02-28', 'unpaid', 'BR-001')
        """, (room_id, owner_id))
        db.commit()
        db.close()
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, html, loc = http_post(f'/backups/{name}/restore', {}, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('恢复完成', html)
        self.assertIn(name, html)
        self.assertIn('恢复前自动备份', html)
        self.assertIn('auto_before_restore_', html)
        self.assertIn('当前数据库摘要', html)
        self.assertIn('RESTORERESULT', html)
        self.assertIn('2029-02', html)
        self.assertIn('去首页', html)
        self.assertIn('查看房间', html)
        self.assertIn('查看账单', html)
        self.assertIn('返回备份', html)

    def test_backup_flow(self):
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        _, bbody = http_get('/backups', self.cookie, TEST_PORT)
        self.assertIn('backup_', bbody)




    def test_import_upload_works_without_stdlib_cgi_module(self):
        cgi_module = sys.modules.pop('cgi', None)
        block_cgi = mock.patch.dict('sys.modules', {'cgi': None})
        boundary = '----PropertyNoCgiBoundary'
        csv_data = '房号,姓名,电话\nB座940,NoCgi业主,13900009940\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="no-cgi.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        try:
            with block_cgi:
                conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
                conn.request('POST', '/import/upload', body, {
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                    'Content-Length': str(len(body)),
                    'Cookie': self.cookie,
                })
                resp = conn.getresponse()
                preview_html = resp.read().decode('utf-8')
                conn.close()
        finally:
            if cgi_module is not None:
                sys.modules['cgi'] = cgi_module

        self.assertEqual(resp.status, 200)
        self.assertIn('字段映射确认', preview_html)
        self.assertIn('NoCgi业主', preview_html)

    def test_payment_ledger_preview_confirms_fee_mapping_without_importing_amounts(self):
        boundary = '----PropertyFeeMappingBoundary'
        csv_data = '房间号,用户名称,物业费,电费,广告费\nB座903,收费项目业主,100,20,5\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\npayment_ledger\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="fee-map.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        preview_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('收费标准匹配确认', preview_html)
        self.assertIn('name="fee_map_物业费"', preview_html)
        self.assertIn('物业费(居民)', preview_html)
        token = re.search(r'name="upload_token" value="([^"]+)"', preview_html).group(1)

        status, result_html, _ = http_post('/import/upload', {
            'mode': 'confirm_fee_mapping',
            'data_type': 'payment_ledger',
            'filename': 'fee-map.csv',
            'upload_token': token,
            'fee_map_物业费': 'fee:物业费(居民)',
            'fee_map_电费': 'fee:电费(商业)',
            'fee_map_广告费': 'ignore',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('收费项目匹配确认结果', result_html)
        self.assertIn('物业费(居民)', result_html)
        self.assertIn('电费(商业)', result_html)
        self.assertIn('忽略', result_html)
        self.assertIn('未导入历史金额', result_html)
        self.assertIn('打印核对清单', result_html)
        match = re.search(r'href="(/import/fee_mapping/[^"]+\.csv)"', result_html)
        self.assertIsNotNone(match)
        status, csv_body = http_get(match.group(1), self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('Excel原始列名,系统识别结果,用户确认匹配,正数行数,负数行数,金额合计,说明,金额入账状态', csv_body)
        self.assertIn('物业费,matched_fee,物业费(居民)', csv_body)
        self.assertIn('广告费,unmatched_fee,忽略', csv_body)
        self.assertIn('未导入历史金额', csv_body)

    def test_import_preview_allows_manual_column_mapping(self):
        boundary = '----PropertyImportPreviewBoundary'
        csv_data = '房号,姓名,电话,备注列\nB座902,自动识别业主,13900008888,手动映射业主\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="manual-map.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        preview_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('字段映射确认', preview_html)
        self.assertIn('name="col_owner_name"', preview_html)
        token = re.search(r'name="upload_token" value="([^"]+)"', preview_html).group(1)

        status, result_html, _ = http_post('/import/upload', {
            'mode': 'import',
            'data_type': 'rooms',
            'filename': 'manual-map.csv',
            'upload_token': token,
            'col_room_number': '0',
            'col_owner_name': '3',
            'col_owner_phone': '2',
            'col_area': '',
            'col_contract_period': '',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('导入结果', result_html)
        self.assertIn('B座', result_html)
        self.assertIn('902', result_html)
        self.assertIn('手动映射业主', result_html)
        self.assertNotIn('自动识别业主</td>', result_html)

    def test_import_preview_shows_audit_sections_and_problem_export(self):
        boundary = '----PropertyImportPreviewAuditBoundary'
        csv_data = (
            '类别,房号,业主姓名,面积㎡,联系电话,合同缴租期\n'
            '商户,B座930,预览正常业主,88.5,13900008881,2026.1.1-2026.12.31\n'
            '商户,美容护肤,广告招商,0,,\n'
            '商户,B座931,日期异常业主,66.0,13900008882,bad-date\n'
        )
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="preview-audit.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        preview_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('导入审核台', preview_html)
        self.assertIn('可导入房间', preview_html)
        self.assertIn('跳过行', preview_html)
        self.assertIn('风险行', preview_html)
        self.assertIn('预览正常业主', preview_html)
        self.assertIn('非房间资料', preview_html)
        self.assertIn('合同日期异常', preview_html)
        match = re.search(r'href="(/import/problem_rows/[^"]+\.csv)"', preview_html)
        self.assertIsNotNone(match)

        status, csv_body = http_get(match.group(1), self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('美容护肤', csv_body)
        self.assertIn('bad-date', csv_body)


    def test_import_result_shows_and_exports_problem_rows(self):
        boundary = '----PropertyImportProblemRowsBoundary'
        csv_data = (
            '类别,房号,业主姓名,面积㎡,联系电话,合同缴租期\n'
            '商户,B座903,正常业主,10,13900007777,2024.1.1-2026.1.1\n'
            '商户,,无房号,10,13900007778,\n'
            '商户,业态,无效房号,10,13900007779,\n'
            '商户,B座904,日期异常,10,13900007770,bad-date\n'
        )
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\nimport\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="problem-rows.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('问题行明细', html)
        self.assertIn('缺少房号', html)
        self.assertIn('房号无效', html)
        self.assertIn('合同日期异常', html)
        match = re.search(r'href="(/import/problem_rows/[^"]+\.csv)"', html)
        self.assertIsNotNone(match)

        status, csv_body = http_get(match.group(1), self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('行号,原因,原始数据', csv_body)
        self.assertIn('缺少房号', csv_body)
        self.assertIn('房号无效', csv_body)
        self.assertIn('合同日期异常', csv_body)



    def test_import_page_downloads_basic_info_template(self):
        status, body = http_get('/import', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('下载基础资料模板', body)
        self.assertIn('/import/template/basic.csv', body)

        status, csv_body = http_get('/import/template/basic.csv', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('楼栋,单元/座,铺位号,楼层,房屋类别,面积㎡,商户名称,联系电话,租户姓名,店铺名称,业态,合同开始日期,合同结束日期,催缴租金租期,物业费单价,缴费周期,水费标准,备注', csv_body)
        self.assertIn('金莎国际,商场,1F-101,1,商户,88.5', csv_body)
        self.assertIn('历史金额不要填在本模板', csv_body)

    def test_import_page_guides_real_data_workflow(self):
        status, body = http_get('/import', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('导入向导', body)
        self.assertIn('基础资料导入', body)
        self.assertIn('收款明细识别', body)
        self.assertIn('安全机制', body)
        self.assertIn('自动备份', body)
        self.assertIn('一键撤销', body)
        self.assertIn('历史金额不会自动入账', body)


    def test_import_result_links_to_filtered_bill_preview(self):
        boundary = '----PropertyImportBillingNextBoundary'
        csv_data = '楼栋,类别,房号,业主姓名,面积㎡,联系电话,合同缴租期\nNEXTBILL,商户,901,导入收费业主,88.5,13900006666,2026.1.1-2026.12.31\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\nimport\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="next-billing.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('下一步生成账单', html)
        self.assertIn('/bills/generate?building=NEXTBILL&amp;category=%E5%95%86%E6%88%B7', html)

        status, page = http_get('/bills/generate?building=NEXTBILL&category=%E5%95%86%E6%88%B7', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="NEXTBILL" selected', page)
        self.assertIn('value="商户" selected', page)

    def test_import_creates_backup_and_shows_result_details(self):
        boundary = '----PropertyImportTestBoundary'
        csv_data = '类别,房号,业主姓名,面积㎡,联系电话,合同缴租期\n商户,B座901,自动备份业主,88.5,13900009999,2024.1.1-2026.12.31\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\nimport\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="rooms.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('导入结果', html)
        self.assertIn('自动备份', html)
        self.assertIn('auto_before_import_', html)
        self.assertIn('新增房间', html)
        self.assertIn('新增业主', html)
        self.assertIn('未导入历史金额', html)
        self.assertIn('历史金额不会自动入账', html)
        self.assertIn('数据核对与修正', html)
        self.assertIn('B座', html)
        self.assertIn('901', html)
        self.assertIn('自动备份业主', html)
        self.assertIn('2024-01-01', html)
        self.assertIn('/rooms/', html)
        self.assertIn('/edit', html)
        self.assertIn('撤销本次导入', html)
        self.assertRegex(html, r'action="/backups/auto_before_import_[^"]+\.db/restore"')

        import server.db as db_module
        backups = os.listdir(db_module.BACKUP_DIR)
        self.assertTrue(any(name.startswith('auto_before_import_') for name in backups))

    # ── 404 ─────────────────────────────────────────────────────

    def test_404_for_unknown_path(self):
        status, body = http_get('/this_does_not_exist', self.cookie, TEST_PORT)
        self.assertEqual(status, 404)

    def test_default_admin_password_warning_guides_local_first_run(self):
        status, body = http_get('/', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('默认管理员密码仍在使用', body)
        self.assertIn('/users/1/edit', body)
        self.assertIn('本地版不需要注册互联网账号', body)

    def test_missing_user_edit_redirects_instead_of_dropping_connection(self):
        status, body = http_get('/users/999999/edit', self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

    def test_users_page_guides_first_run_roles_without_cloud_registration(self):
        status, body = http_get('/users', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('首次账号设置建议', body)
        self.assertIn('财务收费账号', body)
        self.assertIn('客服只读账号', body)
        self.assertIn('本地账号', body)
        self.assertIn('不是互联网开户注册', body)

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
        self.assertIn('规模商户', bills_html)

        status, filtered_html = http_get(f'/bills?period={period}&building=S03&status=unpaid', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('S03', filtered_html)
        self.assertIn('未缴', filtered_html)

        status, reports_html = http_get(f'/reports?period={period}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('楼栋对账统计', reports_html)
        self.assertIn('账期对账', reports_html)


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

    def test_api_v1_payment_preview_rejects_overpay_as_json_validation_error(self):
        import server.db as db_module

        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", ('超额业主', '13800138003')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('OVERPAY座', '1单元', '2401', 24, '商户', 80, owner_id),
        ).lastrowid
        fee_type_id = db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", ('超额测试费', 'fixed', 50)).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_type_id, '2026-11', 50, '2026-11-30', 'unpaid', 'API-PREVIEW-OVERPAY'),
        ).lastrowid
        db.commit()
        db.close()

        status, body, _ = http_post('/api/v1/payments/preview', {
            'bill_id': str(bill_id),
            'amount': '60.00',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'validation_error')
        self.assertIn('收款金额不能超过欠费金额', payload['error']['message'])

        db = db_module.get_db()
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

    def _create_api_payment_bill(self, bill_number, amount=90.0):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", (bill_number + '业主', '13800138004')).lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('PAYAPI座', '1单元', bill_number[-4:], 12, '商户', 90, owner_id),
        ).lastrowid
        fee_type_id = db.execute("INSERT INTO fee_types(name,calc_method,unit_price) VALUES(?,?,?)", (bill_number + '费用', 'fixed', amount)).lastrowid
        bill_id = db.execute(
            "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)",
            (room_id, owner_id, fee_type_id, '2026-12', amount, '2026-12-31', 'unpaid', bill_number),
        ).lastrowid
        db.commit()
        db.close()
        return owner_id, room_id, fee_type_id, bill_id

    def _cleanup_api_payment_bill(self, owner_id, room_id, fee_type_id, bill_id):
        import server.db as db_module
        db = db_module.get_db()
        db.execute('DELETE FROM audit_logs WHERE entity_type=? AND entity_id IN (SELECT id FROM payments WHERE bill_id=?)', ('payment', bill_id))
        db.execute('DELETE FROM payments WHERE bill_id=?', (bill_id,))
        db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
        db.execute('DELETE FROM fee_types WHERE id=?', (fee_type_id,))
        db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
        db.commit()
        db.close()

    def test_api_v1_payment_create_rejects_readonly_user(self):
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('API-PAY-READONLY', 90.0)
        username = 'readonly_api_pay'
        http_post('/users/create', {
            'username': username,
            'password': 'readonly123',
            'display_name': '只读API测试',
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

        status, body, _ = http_post('/api/v1/payments', {
            'bill_id': str(bill_id),
            'amount': '10.00',
            'method': 'cash',
        }, readonly_cookie, TEST_PORT)

        self.assertEqual(status, 403)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'forbidden')
        self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)

    def test_api_v1_payment_create_writes_payment_backup_and_audit(self):
        import server.db as db_module
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('API-PAY-CREATE', 90.0)
        before_backups = set(os.listdir(db_module.BACKUP_DIR)) if os.path.exists(db_module.BACKUP_DIR) else set()

        status, body, _ = http_post('/api/v1/payments', {
            'bill_id': str(bill_id),
            'amount': '90.00',
            'method': 'cash',
            'idempotency_key': 'future-key-1',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['amount'], '90.00')
        self.assertEqual(payload['data']['bill_status'], 'paid')
        self.assertEqual(payload['data']['idempotency_key'], 'future-key-1')
        self.assertTrue(payload['data']['backup_name'].startswith('auto_before_api_payment_'))

        db = db_module.get_db()
        bill = db.execute('SELECT status FROM bills WHERE id=?', (bill_id,)).fetchone()
        payment = db.execute('SELECT id, amount_paid FROM payments WHERE bill_id=?', (bill_id,)).fetchone()
        audit = db.execute(
            "SELECT action FROM audit_logs WHERE action='api_payment_create' AND entity_type='payment' AND entity_id=?",
            (payment['id'],),
        ).fetchone()
        db.close()
        after_backups = set(os.listdir(db_module.BACKUP_DIR))

        self.assertEqual(bill['status'], 'paid')
        self.assertAlmostEqual(payment['amount_paid'], 90.0)
        self.assertIsNotNone(audit)
        self.assertTrue(any(name.startswith('auto_before_api_payment_') for name in after_backups - before_backups))
        self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)

    def test_api_v1_payment_create_rejects_overpay_without_writing(self):
        import server.db as db_module
        owner_id, room_id, fee_type_id, bill_id = self._create_api_payment_bill('API-PAY-OVERPAY', 30.0)

        status, body, _ = http_post('/api/v1/payments', {
            'bill_id': str(bill_id),
            'amount': '31.00',
            'method': 'cash',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'validation_error')
        db = db_module.get_db()
        count = db.execute('SELECT COUNT(*) FROM payments WHERE bill_id=?', (bill_id,)).fetchone()[0]
        db.close()
        self.assertEqual(count, 0)
        self._cleanup_api_payment_bill(owner_id, room_id, fee_type_id, bill_id)

    def test_import_preview_mapping_uses_contract_start_and_end_not_contract_date(self):
        boundary = '----PropertyImportContractDatesBoundary'
        csv_data = (
            '类别,房号,业主姓名,面积㎡,合同开始日期,合同到期日期\n'
            '商户,B座950,独立日期业主,60,2026-01-15,2026-12-31\n'
        )
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="contract-dates.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        preview_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('字段映射确认', preview_html)
        self.assertIn('name="col_contract_start"', preview_html)
        self.assertIn('name="col_contract_end"', preview_html)
        self.assertNotIn('name="col_contract_period"', preview_html)
        self.assertNotIn('>合同日期</label>', preview_html)

    def test_billing_calc_redirected_range_period_is_visible_in_bill_list(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name) VALUES('区间账期业主')").lastrowid
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) VALUES(?,?,?,?,?,?,?)",
            ('RANGEBILL', 'A座', '1808', 18, '居民', 10, owner_id)
        ).lastrowid
        db.commit(); db.close()

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(room_id),
            'period_start': '2032-01-01',
            'period_end': '2032-03-01',
            'fee_types': '1',
            'custom_amount_1': '88.00',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills?period=2032-01~2032-03', urllib.parse.unquote(loc))

        status, list_html = http_get('/bills?period=2032-01~2032-03&keyword=1808', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('RANGEBILL-A座-1808', list_html)
        self.assertIn('2032-01~2032-03', list_html)
        self.assertNotIn('暂无账单', list_html)

    def test_invoice_requests_backend_page_updates_status(self):
        import server.db as db_module
        from server.invoice_requests import InvoiceRequestService
        db = db_module.get_db()
        owner_id = create_owner(db, '后台票据业主', '13800139002')
        room_id = create_room(db, building='INVADMIN', room_number='3902', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, owner_id=owner_id, amount=99.0, status='paid', period='2030-01')
        db.close()
        request = InvoiceRequestService().create_request({'bill_id': bill_id, 'buyer_name': '后台票据抬头'})
        try:
            status, page = http_get('/invoice_requests', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertIn('电子票据请求', page)
            self.assertIn(request['request_no'], page)

            status, _, loc = http_post(f'/invoice_requests/{request["request_no"]}/status', {
                'status': 'issued',
                'external_invoice_id': 'EINV-001',
            }, self.cookie, TEST_PORT)
            self.assertEqual(status, 302)
            self.assertIn('/invoice_requests', loc)

            db = db_module.get_db()
            row = db.execute('SELECT status, external_invoice_id FROM invoice_requests WHERE request_no=?', (request['request_no'],)).fetchone()
            db.close()
            self.assertEqual(row['status'], 'issued')
            self.assertEqual(row['external_invoice_id'], 'EINV-001')
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM invoice_requests WHERE bill_id=?', (bill_id,))
            db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()

    def test_invoice_request_api_create_list_and_detail(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '电子票据业主', '13800139001')
        room_id = create_room(db, building='INVAPI', room_number='3901', owner_id=owner_id)
        bill_id = create_bill(db, room_id=room_id, owner_id=owner_id, amount=88.0, status='paid', period='2029-12')
        payment_id = create_payment(db, bill_id=bill_id, amount=88.0, method='mock', operator='api-test')
        db.close()
        try:
            status, body, _ = http_post('/api/v1/invoice-requests', {
                'bill_id': str(bill_id),
                'buyer_name': '接口测试公司',
                'buyer_tax_id': 'TAX-API-001',
                'idempotency_key': 'api-invoice-request-key',
            }, self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            data = json.loads(body)['data']
            self.assertEqual(data['status'], 'pending')
            self.assertEqual(data['amount'], '88.00')
            self.assertTrue(data['request_no'].startswith('IR'))

            status, body = http_get('/api/v1/invoice-requests?status=pending', self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            items = json.loads(body)['data']['items']
            self.assertTrue(any(item['request_no'] == data['request_no'] for item in items))

            status, body = http_get('/api/v1/invoice-requests/' + data['request_no'], self.cookie, TEST_PORT)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['data']['buyer_name'], '接口测试公司')
        finally:
            db = db_module.get_db()
            db.execute('DELETE FROM invoice_requests WHERE bill_id=?', (bill_id,))
            db.execute('DELETE FROM payments WHERE bill_id=?', (bill_id,))
            db.execute('DELETE FROM bills WHERE id=?', (bill_id,))
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            db.execute('DELETE FROM owners WHERE id=?', (owner_id,))
            db.commit(); db.close()




if __name__ == '__main__':
    unittest.main()
