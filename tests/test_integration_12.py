#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 12."""

from tests.integration_base import *


class TestIntegration12(IntegrationTestBase):
    def test_b_phase_review_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'b_phase_review_manager_scope', 'manager123', 'manager', 'B阶段审查管理员'
        )
        cashier_cookie = self._create_user_and_login(
            'b_phase_review_cashier_scope', 'cashier123', 'cashier', 'B阶段审查收费员'
        )

        status, _, loc = http_get_with_location('/delivery_center/b_phase_review', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/b_phase_review', cashier_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_c_phase_review_page_documents_abc_completion(self):
        status, body = http_get('/delivery_center/c_phase_review', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('C 阶段完成审查', body)
        for text in ['首页经营驾驶舱已增强', '报表分析看板已增强', 'A/B/C 阶段验收链路', '底层安全运行验证']:
            self.assertIn(text, body)
        for text in ['431 passed, 4 skipped', '2.0 当前业务范围已完成，进入桌面稳定版收口优化', '稳定版收口建议']:
            self.assertIn(text, body)
        self.assertNotIn('继续推进云端部署演练', body)
        self.assertNotIn('按 A→B→C 顺序推进', body)
        for href in ['/', '/reports', '/delivery_center/a_phase_review', '/delivery_center/b_phase_review', '/system_health']:
            self.assertIn(href, body)


    def test_c_phase_review_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'c_phase_review_manager_scope', 'manager123', 'manager', 'C阶段审查管理员'
        )
        cashier_cookie = self._create_user_and_login(
            'c_phase_review_cashier_scope', 'cashier123', 'cashier', 'C阶段审查收费员'
        )

        status, _, loc = http_get_with_location('/delivery_center/c_phase_review', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/c_phase_review', cashier_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_v2_delivery_center_guides_roles_and_acceptance_flow(self):
        status, body = http_get('/delivery_center', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('2.0 交付中心', body)
        self.assertIn('岗位权限说明', body)
        for text in ['系统管理员', '财务', '收费员', '客服业务编辑', '管理层只读']:
            self.assertIn(text, body)
        for text in ['空间合同档案', '商业收费主入口', '导入核对与修正', '云端技术备查', '桌面稳定版收口']:
            self.assertIn(text, body)
        self.assertNotIn('商户合同闭环', body)
        self.assertNotIn('合同出账预览', body)
        self.assertIn('2.0 当前业务范围已完成', body)
        self.assertNotIn('按 A→B→C 顺序推进', body)
        for href in ['/users', '/merchant_contracts', '/import', '/cloud_schema', '/system_health']:
            self.assertIn(href, body)


    def test_sidebar_groups_daily_workbench_and_shared_functions_in_requested_order(self):
        status, body = http_get('/rooms', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for text in ['工作台', '公共功能', '财务核对', '系统维护']:
            self.assertIn(text, body)
        self.assertNotIn('<span>空间合同档案</span>', body)
        self.assertIn('<span>合同档案</span>', body)
        self.assertNotIn('<div class="nav-section-title">物业业务</div>', body)
        self.assertNotIn('<div class="nav-section-title">商业业务</div>', body)
        nav = body.split('<nav class="sidebar-nav">', 1)[1].split('</nav>', 1)[0]
        workbench_section = nav.split('工作台', 1)[1].split('公共功能', 1)[0]
        shared_section = nav.split('公共功能', 1)[1].split('财务核对', 1)[0]
        financial_section = nav.split('财务核对', 1)[1].split('系统维护', 1)[0]
        workbench_labels = ['收费工作台', '智能预警', '催缴管理', '数据导入', '合同档案']
        shared_labels = ['业主管理', '收费对象管理', '收费项目', '抄表管理', '批量更新', '自动出账', '公摊分摊']
        previous = -1
        for label in workbench_labels:
            pos = workbench_section.index(f'<span>{label}</span>')
            self.assertGreater(pos, previous)
            previous = pos
        previous = -1
        for label in shared_labels:
            pos = shared_section.index(f'<span>{label}</span>')
            self.assertGreater(pos, previous)
            previous = pos
        self.assertIn('<span>账单管理</span>', financial_section)

        status, page = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('空间合同档案', page)
        self.assertIn('新增合同档案', page)
        self.assertNotIn('新增空间档案', page)
        self.assertNotIn('/commercial_spaces/create', page)
        self.assertNotIn('空间/铺位档案', page)
        self.assertIn('/merchant_contracts/create', page)
        self.assertIn('不局限于商场', page)


    def test_merchant_contract_list_delete_button_removes_only_without_contract_bills(self):
        from server.contract_billing import create_merchant_contract
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, '可删除合同业主', '13900004401')
        deletable = create_merchant_contract({
            'owner_id': owner_id, 'contract_no': 'DEL-CONTRACT-001', 'merchant_name': '可删除商户',
            'shop_name': '可删除品牌', 'rent_amount': 100, 'rent_cycle': 'monthly', 'property_rate': 1,
            'property_cycle': 'monthly', 'deposit_amount': 10, 'start_date': '2036-01-01', 'end_date': '2036-12-31',
        })
        protected = create_merchant_contract({
            'owner_id': owner_id, 'contract_no': 'DEL-CONTRACT-002', 'merchant_name': '有账单商户',
            'shop_name': '有账单品牌', 'rent_amount': 100, 'rent_cycle': 'monthly', 'property_rate': 1,
            'property_cycle': 'monthly', 'deposit_amount': 10, 'start_date': '2036-01-01', 'end_date': '2036-12-31',
        })
        fee_id = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)' LIMIT 1").fetchone()['id']
        db.execute("""INSERT INTO bills(owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number, source, source_ref)
                  VALUES(?,?,?,?,?,?,?,?,?)""", (owner_id, fee_id, '2036-01', 88, '2036-01-31', 'unpaid', 'DEL-PROTECT-001', 'merchant_contract', str(protected)))
        db.commit(); db.close()

        status, page = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'/merchant_contracts/{deletable}/delete', page)
        self.assertIn('删除', page)
        self.assertIn('确认删除该合同档案？', page)

        status, _, loc = http_post(f'/merchant_contracts/{protected}/delete', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('已有合同账单，不能删除', urllib.parse.unquote(loc))
        db = db_module.get_db()
        self.assertIsNotNone(db.execute('SELECT id FROM merchant_contracts WHERE id=?', (protected,)).fetchone())
        db.close()

        status, _, loc = http_post(f'/merchant_contracts/{deletable}/delete', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('合同档案已删除', urllib.parse.unquote(loc))
        db = db_module.get_db()
        self.assertIsNone(db.execute('SELECT id FROM merchant_contracts WHERE id=?', (deletable,)).fetchone())
        self.assertIsNotNone(db.execute('SELECT id FROM merchant_contracts WHERE id=?', (protected,)).fetchone())
        db.close()

