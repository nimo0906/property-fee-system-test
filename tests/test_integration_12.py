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
        shared_labels = ['业主管理', '房间管理', '收费项目', '抄表管理', '批量更新', '自动出账', '公摊分摊']
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


    def test_bills_page_uses_scope_label_and_room_labels_for_commercial_and_property_rows(self):
        import server.db as db_module
        db = db_module.get_db()
        prop_owner = create_owner(db, '账单页物业业主', '13900005551')
        prop_room = create_room(db, building='BILLSCOPE', unit='B座', room_number='901', floor=9, category='居民', area=10, owner_id=prop_owner)
        mall_owner = create_owner(db, '账单页商户业主', '13900005552')
        mall_space = db.execute("INSERT INTO commercial_spaces(space_no,floor,area,shop_name,merchant_name,business_type,status) VALUES(?,?,?,?,?,?,?)", ('BILLS-SPACE-01', 1, 20, '账单页商铺', '账单页商户', '零售', 'active')).lastrowid
        fee_id = db.execute("SELECT id FROM fee_types WHERE is_active=1 ORDER BY sort_order LIMIT 1").fetchone()['id']
        db.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)", (prop_room, prop_owner, fee_id, '2037-06', 19, '2037-06-30', 'unpaid', 'BILLSCOPE-PROP'))
        db.execute("INSERT INTO bills(commercial_space_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) VALUES(?,?,?,?,?,?,?,?)", (mall_space, mall_owner, fee_id, '2037-06', 38, '2037-06-30', 'unpaid', 'BILLSCOPE-MALL'))
        db.commit(); db.close()

        status, body = http_get('/bills?period=2037-06', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('Formal proposal · Bills', body)
        self.assertNotIn('账单管理正式提案版', body)
        self.assertNotIn('本页目标：先看规模', body)
        self.assertIn('data-testid="bill-scope-summary"', body)
        self.assertIn('ledger-scope-area', body)
        self.assertIn('收费公司分区', body)
        self.assertIn('ledger-scope-chip property', body)
        self.assertIn('ledger-scope-chip commercial', body)
        self.assertIn('收费公司', body)
        self.assertIn('物业公司收费', body)
        self.assertIn('商业公司收费', body)
        self.assertIn('欠费¥19.0', body)
        self.assertIn('欠费¥38.0', body)
        self.assertIn('账单页物业业主', body)
        self.assertIn('BILLSCOPE-B座-901', body)
        self.assertIn('商场-BILLS-SPACE-01', body)
        self.assertIn('href="/bills?period_start=2037-06-01&amp;period_end=2037-06-30&amp;company_scope=property"', body)
        self.assertIn('href="/bills?period_start=2037-06-01&amp;period_end=2037-06-30&amp;company_scope=commercial"', body)
        self.assertIn('bill-object-chip">BILLSCOPE-B座-901</span>', body)
        self.assertIn('bill-object-chip">商场-BILLS-SPACE-01</span>', body)

        status, property_body = http_get('/bills?period=2037-06&company_scope=property', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('ledger-scope-chip property active', property_body)
        self.assertIn('BILLSCOPE-PROP', property_body)
        self.assertNotIn('BILLSCOPE-MALL', property_body)
        self.assertIn('物业公司收费 <strong>1笔</strong>', property_body)
        self.assertIn('商业公司收费 <strong>1笔</strong>', property_body)

        status, commercial_body = http_get('/bills?period=2037-06&company_scope=commercial', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('ledger-scope-chip commercial active', commercial_body)
        self.assertIn('BILLSCOPE-MALL', commercial_body)
        self.assertNotIn('BILLSCOPE-PROP', commercial_body)
        self.assertIn('bill-inline-code">BILLS-SPACE-01</span>', commercial_body)

    def test_merchant_contract_list_shows_formal_group_nav_and_summary_cards(self):
        status, body = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('Formal proposal · Contracts', body)
        self.assertNotIn('合同档案正式提案版', body)
        self.assertNotIn('page-proposal-hero', body)
        self.assertIn('合同档案总览', body)
        self.assertNotIn('本页目标：先看档案总量和分组', body)
        self.assertIn('data-testid="contract-scope-tabs"', body)
        self.assertIn('contract-scope-tab all active', body)
        self.assertIn('contract-scope-tab property', body)
        self.assertIn('contract-scope-tab commercial', body)
        self.assertIn('物业合同', body)
        self.assertIn('商业合同', body)
        self.assertIn('id="property-contracts"', body)
        self.assertIn('id="commercial-contracts"', body)
        self.assertIn('/merchant_contracts?contract_scope=property', body)
        self.assertIn('/merchant_contracts?contract_scope=commercial', body)
        self.assertNotIn('href="#property-contracts"', body)
        self.assertNotIn('href="#commercial-contracts"', body)
