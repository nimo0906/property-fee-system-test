#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 15."""

from tests.integration_base import *


class TestIntegration15(IntegrationTestBase):
    def test_a_phase_review_page_documents_ready_for_cloud_phase(self):
        status, body = http_get('/delivery_center/a_phase_review', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('A 阶段完成审查', body)
        for text in ['合同闭环已验收', '导入闭环已验收', '岗位权限已验收', '员工操作说明已补齐', '云端技术备查入口已保留', '备份恢复入口已准备', '系统健康检查入口已准备']:
            self.assertIn(text, body)
        for text in ['进入稳定版收口前必须保持全量测试通过', '431 passed, 4 skipped', '可以进入 2.0 桌面稳定版收口']:
            self.assertIn(text, body)
        for href in ['/delivery_center/contracts', '/delivery_center/import', '/delivery_center/checklist', '/delivery_center/staff_guide', '/cloud_schema', '/backups', '/system_health']:
            self.assertIn(href, body)


    def test_a_phase_review_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'a_phase_review_manager_scope', 'manager123', 'manager', 'A阶段审查管理员'
        )
        cashier_cookie = self._create_user_and_login(
            'a_phase_review_cashier_scope', 'cashier123', 'cashier', 'A阶段审查收费员'
        )

        status, _, loc = http_get_with_location('/delivery_center/a_phase_review', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/a_phase_review', cashier_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_delivery_center_is_admin_only_for_release_scope(self):
        manager_cookie = self._create_user_and_login(
            'delivery_manager_scope', 'manager123', 'manager', '交付管理员'
        )
        finance_cookie = self._create_user_and_login(
            'delivery_finance_scope', 'finance123', 'finance', '交付财务'
        )

        status, body = http_get('/delivery_center', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('2.0 交付中心', body)

        status, _, loc = http_get_with_location('/delivery_center', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center', finance_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


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


    def test_secondary_pages_show_global_back_button(self):
        for path in ['/fee_types/11/edit', '/rooms/create', '/bills/generate']:
            with self.subTest(path=path):
                status, body = http_get(path, self.cookie, TEST_PORT)
                self.assertEqual(status, 200)
                self.assertIn('data-back-button="1"', body)
                self.assertIn('返回', body)
                self.assertIn('topbar-actions d-flex', body)
                self.assertIn('href="', body)
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
            '/backups': '备份记录', '/import': '数据导入', '/reports': '对账报表',
            '/users': '操作员管理', '/late_fee_config': '滞纳金设置',
            '/elevator_tiers': '电梯费阶梯设置', '/bills/generate': '生成账单',
        }
        for path, title in pages.items():
            with self.subTest(path=path):
                status, body = http_get(path, self.cookie, TEST_PORT)
                self.assertEqual(status, 200, msg=f'{path} returned {status}')
                self.assertIn(title, body, msg=f'{path} missing title [{title}]')


    def test_late_fee_config_returns_to_previous_page(self):
        status, body = http_get('/late_fee_config', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('返回上一级', body)
        self.assertIn('history.back()', body)
        self.assertIn("location.href='/bills'", body)
        self.assertNotIn('返回账单</a>', body)


    def test_home_no_longer_shows_persistent_first_run_guide(self):
        status, body = http_get('/', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertNotIn('首次使用建议流程', body)
        self.assertIn('生成账单', body)
        self.assertIn('收费登记', body)
        self.assertIn('对账报表', body)
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
        self.assertIn('/import/template/basic.xlsx', body)
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
        self.assertIn('/import/template/basic.xlsx', body)
        self.assertIn('/import', body)
        self.assertIn('/rooms/create', body)


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
