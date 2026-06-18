#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 11."""

from tests.integration_base import *


class TestIntegration11(IntegrationTestBase):
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
        self.assertIn('已收', body)
        self.assertIn('未收', body)
        self.assertIn('待收费账单', body)
        self.assertIn('生成账单', body)
        self.assertIn('收费登记', body)
        self.assertIn('打印收据', body)
        self.assertIn('经营看板', body)
        self.assertIn('对账报表', body)
        self.assertIn('发票管理', body)
        self.assertNotIn('维修', body)


    def test_home_shows_actionable_todo_and_exception_cards(self):
        from server.db import get_db, get_period
        db = get_db()
        period = get_period()
        owner_id = create_owner(db, '首页待办业主', '13900008888')
        room_id = create_room(db, building='HOME', unit='B座', room_number='TODO-1', area=88, owner_id=owner_id)
        unpaid_id = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=1, period=period, amount=100, status='overdue')
        paid_id = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=2, period=period, amount=200, status='paid')
        zero_id = create_bill(db, room_id=room_id, owner_id=owner_id, fee_type_id=3, period=period, amount=0, status='unpaid')
        db.execute("UPDATE bills SET due_date=date('now','localtime','-1 day') WHERE id=?", (unpaid_id,))
        create_payment(db, bill_id=paid_id, amount=200, method='cash', operator='首页测试')
        db.commit(); db.close()

        status, body = http_get('/', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('优先处理', body)
        self.assertIn('待收费账单', body)
        self.assertIn('/bills?status=unpaid', body)
        self.assertIn('待开票', body)
        self.assertIn('/invoices', body)
        self.assertIn('待抄表', body)
        self.assertIn('/meter_readings', body)


    def test_home_shows_enterprise_analysis_dashboard_sections(self):
        from server.db import get_db, get_period
        db = get_db()
        period = get_period()
        owner_id = create_owner(db, '首页经营商户', '13900006666')
        mall_room = create_room(db, building='商场', unit='商场', room_number='DASH-M1', category='商户', area=100, owner_id=owner_id)
        b_room = create_room(db, building='B座', unit='B座', room_number='DASH-B1', category='居民', area=80, owner_id=owner_id)
        db.execute("UPDATE rooms SET shop_name='首页贡献店' WHERE id=?", (mall_room,))
        mall_bill = create_bill(db, room_id=mall_room, owner_id=owner_id, fee_type_id=1, period=period, amount=800, status='unpaid')
        b_bill = create_bill(db, room_id=b_room, owner_id=owner_id, fee_type_id=2, period=period, amount=200, status='paid')
        create_payment(db, bill_id=b_bill, amount=200, method='cash', operator='首页经营测试')
        db.commit(); db.close()

        status, body = http_get('/', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        for text in ['经营看板', '区域 / 业态', '收入结构', '业务动态']:
            self.assertIn(text, body)
        self.assertIn('收缴率', body)


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


    def test_stable_closeout_mobile_desktop_css_keeps_core_pages_usable(self):
        css = open(os.path.join(PROJECT_ROOT, 'static', 'app.css'), encoding='utf-8').read()

        self.assertIn('@media (max-width: 575.98px)', css)
        for selector in ['.cashier-layout', '.auto-filter-panel', '.report-export-panel', '.table-responsive']:
            self.assertIn(selector, css)
        self.assertIn('-webkit-overflow-scrolling: touch', css)
        self.assertIn('grid-template-columns: 1fr', css)

        for path, expected in [
            ('/billing', ['cashier-layout', 'table-responsive']),
            ('/commercial_billing', ['商业收费', 'table-responsive']),
            ('/meter_readings', ['抄表管理', 'table-responsive']),
            ('/auto_billing?advance_days=30', ['auto-filter-panel', 'table-responsive']),
            ('/reports', ['report-export-panel', 'table-responsive']),
        ]:
            status, body = http_get(path, self.cookie, TEST_PORT)
            self.assertEqual(status, 200, path)
            for text in expected:
                self.assertIn(text, body, path)


    def test_core_desktop_pages_include_refined_ui_sections(self):
        checks = [
            ('/', ['dashboard-focus-shell', 'workbench-primary-actions', '优先处理']),
            ('/bills', ['ledger-toolbar', 'ledger-summary-strip', '按租户和房间折叠展示']),
            ('/billing', ['cashier-layout', 'cashier-object-card', 'cashier-fee-card']),
            ('/auto_billing?advance_days=30', ['auto-billing-console', 'auto-filter-panel', 'auto-run-history']),
            ('/users', ['operator-console', 'role-guide-grid', '超级管理员：admin 保留']),
            ('/delivery_center', ['2.0 交付中心', '岗位权限说明', '当前阶段建议：桌面稳定版收口']),
        ]
        for path, expected in checks:
            status, body = http_get(path, self.cookie, TEST_PORT)
            self.assertEqual(status, 200, path)
            for text in expected:
                self.assertIn(text, body, path)


    def test_cloud_schema_page_shows_migration_reconciliation_checklist(self):
        status, body = http_get('/cloud_schema', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('迁移后一致性核对清单', body)
        self.assertIn('技术人员备查', body)
        self.assertIn('不作为当前开发主线', body)
        for text in ['业主数量一致', '房间数量一致', '账单数量一致', '收款数量一致', '账单金额一致', '收款金额一致', '欠费金额一致']:
            self.assertIn(text, body)
        for text in ['SQLite 当前值', 'PostgreSQL 导入后应一致', '待导入后核对']:
            self.assertIn(text, body)
        self.assertIn('/cloud_migration.sql', body)


    def test_cloud_security_page_documents_deployment_safety_baseline(self):
        status, body = http_get('/delivery_center/cloud_security', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('云端技术备查安全检查', body)
        for text in ['HTTPS 部署说明', '登录会话过期', '安全日志', '自动备份/恢复', '敏感信息不进日志']:
            self.assertIn(text, body)
        for text in ['HttpOnly', 'SameSite=Lax', 'Max-Age=86400', 'cleanup_old_sessions', 'audit_logs']:
            self.assertIn(text, body)
        for text in ['未来迁移前必须检查', '不开放业主端公网支付闭环', '431 passed, 4 skipped']:
            self.assertIn(text, body)
        for href in ['/cloud_schema', '/audit_logs', '/backups', '/system_health']:
            self.assertIn(href, body)


    def test_cloud_security_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'cloud_security_manager_scope', 'manager123', 'manager', '云端安全管理员'
        )
        cashier_cookie = self._create_user_and_login(
            'cloud_security_cashier_scope', 'cashier123', 'cashier', '云端安全收费员'
        )

        status, _, loc = http_get_with_location('/delivery_center/cloud_security', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/cloud_security', cashier_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_cloud_go_live_checklist_page_documents_deployment_runbook(self):
        status, body = http_get('/delivery_center/cloud_go_live', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('云端技术备查检查清单', body)
        for text in ['PostgreSQL 数据底座', 'HTTPS 与域名', '登录会话', '安全日志', '自动备份', '恢复演练', '公网访问边界']:
            self.assertIn(text, body)
        for text in ['SQLite → PostgreSQL 迁移校验', '禁止明文公网登录', '员工后台公网访问', '不开放业主端公网支付闭环']:
            self.assertIn(text, body)
        for text in ['未来迁移前总门槛', '431 passed, 4 skipped', '云端相关内容仅作技术备查' ]:
            self.assertIn(text, body)
        for href in ['/cloud_schema', '/delivery_center/cloud_security', '/backups', '/audit_logs', '/system_health']:
            self.assertIn(href, body)


    def test_cloud_deployment_drill_page_documents_run_steps(self):
        status, body = http_get('/delivery_center/cloud_drill', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('云端技术备查执行单', body)
        for text in ['PostgreSQL 真实导入演练', '备份恢复演练', 'HTTPS / 域名检查', '演练证据留存', '回退方案']:
            self.assertIn(text, body)
        for text in ['psql 导入 seed SQL', '金额一致性截图', '恢复前备份', 'HTTP 自动跳转 HTTPS', '不开放业主端公网支付闭环']:
            self.assertIn(text, body)
        for href in ['/cloud_migration.sql', '/cloud_schema', '/backups', '/audit_logs', '/system_health', '/delivery_center/cloud_go_live']:
            self.assertIn(href, body)


    def test_cloud_deployment_drill_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'cloud_drill_manager_scope', 'manager123', 'manager', '云端演练管理员'
        )
        finance_cookie = self._create_user_and_login(
            'cloud_drill_finance_scope', 'finance123', 'finance', '云端演练财务'
        )

        status, _, loc = http_get_with_location('/delivery_center/cloud_drill', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/cloud_drill', finance_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_cloud_go_live_checklist_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'cloud_go_live_manager_scope', 'manager123', 'manager', '云端上线管理员'
        )
        finance_cookie = self._create_user_and_login(
            'cloud_go_live_finance_scope', 'finance123', 'finance', '云端上线财务'
        )

        status, _, loc = http_get_with_location('/delivery_center/cloud_go_live', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/cloud_go_live', finance_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_b_phase_review_page_documents_ready_for_dashboard_phase(self):
        status, body = http_get('/delivery_center/b_phase_review', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('技术备查完成审查', body)
        for text in ['PostgreSQL 迁移校验已增强', '云端技术备查安全已补齐', '云端技术备查清单已补齐', '备份恢复入口已确认', '安全日志入口已确认']:
            self.assertIn(text, body)
        for text in ['进入稳定版收口前必须保持全量测试通过', '431 passed, 4 skipped', '继续桌面稳定版收口：金额、词汇、流程、窄屏体验']:
            self.assertIn(text, body)
        for href in ['/cloud_schema', '/delivery_center/cloud_security', '/delivery_center/cloud_go_live', '/backups', '/audit_logs', '/reports']:
            self.assertIn(href, body)


