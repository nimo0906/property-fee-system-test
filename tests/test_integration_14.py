#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 14."""

from tests.integration_base import *


class TestIntegration14(IntegrationTestBase):
    def test_unified_import_b_tower_contract_updates_existing_and_optionally_creates_rooms(self):
        import io
        import openpyxl
        from server.db import get_db

        db = get_db()
        owner_id = create_owner(db, 'B座原业主', '13811110000')
        create_room(db, building='B座', unit='B座', room_number='1801', category='出租', area=80, owner_id=owner_id)
        db.commit(); db.close()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'B座出租合同'
        ws.append(['楼栋', '单元', '房号', '租户姓名', '租户电话', '面积', '物业费单价', '缴费周期', '合同开始日期', '合同结束日期', '水费标准', '备注'])
        ws.append(['B座', 'B座', '1801', 'B座新租户', '13918010000', 88, 4.5, '季付', '2026-01-01', '2026-12-31', '非居民', '更新已有'])
        ws.append(['B座', 'B座', '1802', 'B座新增租户', '13918020000', 90, 4.8, '月付', '2026-02-01', '2027-01-31', '特行', '默认不新建'])
        out = io.BytesIO(); wb.save(out)

        status, preview, _ = http_post_multipart('/import/upload', {'mode': 'preview', 'data_type': 'b_tower_contracts'}, {
            'file': ('b-tower-contracts.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', out.getvalue())
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('出租合同导入预览', preview)
        self.assertIn('允许自动新建系统中不存在的收费对象', preview)
        self.assertIn('B座新租户', preview)
        self.assertIn('B座新增租户', preview)

        status, result, _ = http_post('/import/upload', {
            'mode': 'confirm_b_tower_contracts',
            'data_type': 'b_tower_contracts',
            'row_count': '2',
            'include_0': '1', 'row_no_0': '2', 'building_0': 'B座', 'unit_0': 'B座', 'room_number_0': '1801',
            'tenant_name_0': 'B座新租户', 'tenant_phone_0': '13918010000', 'area_0': '88', 'custom_rate_0': '4.5',
            'payment_cycle_0': 'quarterly', 'contract_start_0': '2026-01-01', 'contract_end_0': '2026-12-31',
            'water_rate_type_0': '非居民', 'notes_0': '更新已有',
            'include_1': '1', 'row_no_1': '3', 'building_1': 'B座', 'unit_1': 'B座', 'room_number_1': '1802',
            'tenant_name_1': 'B座新增租户', 'tenant_phone_1': '13918020000', 'area_1': '90', 'custom_rate_1': '4.8',
            'payment_cycle_1': 'monthly', 'contract_start_1': '2026-02-01', 'contract_end_1': '2027-01-31',
            'water_rate_type_1': '特行', 'notes_1': '默认不新建',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('系统中不存在该收费对象', result)
        db = get_db()
        existing = db.execute("SELECT tenant_name,custom_rate,payment_cycle,contract_start,contract_end FROM rooms WHERE building='B座' AND room_number='1801'").fetchone()
        missing = db.execute("SELECT id FROM rooms WHERE building='B座' AND room_number='1802'").fetchone()
        db.close()
        self.assertEqual(existing['tenant_name'], 'B座新租户')
        self.assertAlmostEqual(float(existing['custom_rate']), 4.5)
        self.assertEqual(existing['payment_cycle'], 'quarterly')
        self.assertEqual(existing['contract_start'], '2026-01-01')
        self.assertEqual(existing['contract_end'], '2026-12-31')
        self.assertIsNone(missing)

        status, result, _ = http_post('/import/upload', {
            'mode': 'confirm_b_tower_contracts', 'data_type': 'b_tower_contracts', 'allow_create_rooms': '1', 'row_count': '1',
            'include_0': '1', 'row_no_0': '3', 'building_0': 'B座', 'unit_0': 'B座', 'room_number_0': '1802',
            'tenant_name_0': 'B座新增租户', 'tenant_phone_0': '13918020000', 'area_0': '90', 'custom_rate_0': '4.8',
            'payment_cycle_0': 'monthly', 'contract_start_0': '2026-02-01', 'contract_end_0': '2027-01-31',
            'water_rate_type_0': '特行', 'notes_0': '允许新建',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        db = get_db()
        created = db.execute("SELECT tenant_name,custom_rate,payment_cycle,contract_start,contract_end,water_rate_type FROM rooms WHERE building='B座' AND room_number='1802'").fetchone()
        db.close()
        self.assertIsNotNone(created)
        self.assertEqual(created['tenant_name'], 'B座新增租户')
        self.assertAlmostEqual(float(created['custom_rate']), 4.8)
        self.assertEqual(created['payment_cycle'], 'monthly')
        self.assertEqual(created['water_rate_type'], '特行')


    def test_merchant_contract_create_combines_space_and_contract_fields(self):
        status, form = http_get('/merchant_contracts/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for field in ['name="space_no"', 'name="business_type"', 'name="area"', 'name="water_rate_type"', 'name="contract_no"', 'name="rent_amount"']:
            self.assertIn(field, form)
        self.assertNotIn('合同关联铺位/房间', form)

        status, _, loc = http_post('/merchant_contracts/create', {
            'space_no': 'ONE-SPACE-001',
            'shop_name': '一体档案店铺',
            'merchant_name': '一体档案商户',
            'business_type': '零售',
            'floor': '-2',
            'area': '88.5',
            'water_rate_type': '特行',
            'contract_no': 'ONE-CONTRACT-001',
            'rent_amount': '120',
            'rent_cycle': 'monthly',
            'property_rate': '12',
            'property_cycle': 'monthly',
            'deposit_amount': '200',
            'start_date': '2038-01-01',
            'end_date': '2038-12-31',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/merchant_contracts', loc)

        from server.db import get_db
        db = get_db()
        row = db.execute("""SELECT c.contract_no,c.commercial_space_id,c.rent_amount,c.deposit_amount,s.space_no,s.area,s.business_type,s.water_rate_type
                          FROM merchant_contracts c JOIN commercial_spaces s ON c.commercial_space_id=s.id
                          WHERE c.contract_no='ONE-CONTRACT-001'""").fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['space_no'], 'ONE-SPACE-001')
        self.assertEqual(float(row['area']), 88.5)
        self.assertEqual(row['business_type'], '零售')
        self.assertEqual(row['water_rate_type'], '特行')
        self.assertEqual(float(row['rent_amount']), 10620.0)
        self.assertEqual(float(row['deposit_amount']), 17700.0)

        # Use the actual contract id for billing preview; commercial_space_id may differ in seeded databases.
        db = get_db()
        contract_id = db.execute("SELECT id FROM merchant_contracts WHERE contract_no='ONE-CONTRACT-001'").fetchone()['id']
        db.close()
        status, preview = http_get(f'/merchant_contracts/{contract_id}/billing?service_start=2038-01-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('¥10620.00', preview)
        self.assertIn('¥17700.00', preview)

        status, page = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for text in ['ONE-SPACE-001', 'ONE-CONTRACT-001', '一体档案店铺', '一体档案商户', '零售', '88.50', '特行', '120.00 元/m²', '200.00 元/m²']:
            self.assertIn(text, page)


    def test_merchant_contract_create_can_bind_b_tower_room_and_bill_from_contract(self):
        from server.db import get_db

        db = get_db()
        owner_id = create_owner(db, 'B座合同档案业主', '13900001414')
        room_id = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name) VALUES(?,?,?,?,?,?,?,?)",
            ('金莎国际', 'B座', 'BCT-1401', 14, '商户', 72.5, owner_id, 'B座合同档案商户'),
        ).lastrowid
        db.commit()
        db.close()

        status, form = http_get('/merchant_contracts/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收费对象合同', form)
        self.assertIn('name="target_kind"', form)
        self.assertIn('name="room_id"', form)
        self.assertIn('BCT-1401', form)

        status, _, loc = http_post('/merchant_contracts/create', {
            'target_kind': 'room',
            'room_id': str(room_id),
            'owner_id': str(owner_id),
            'shop_name': 'B座合同档案店铺',
            'merchant_name': 'B座合同档案商户',
            'business_type': '办公商户',
            'area': '72.5',
            'building_area': '72.5',
            'contract_no': 'BROOM-CONTRACT-001',
            'rent_amount': '80',
            'rent_cycle': 'monthly',
            'property_rate': '6',
            'property_cycle': 'monthly',
            'deposit_amount': '100',
            'start_date': '2039-01-01',
            'end_date': '2039-12-31',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/merchant_contracts', loc)

        db = get_db()
        contract = db.execute(
            "SELECT id,room_id,commercial_space_id,rent_amount,deposit_amount FROM merchant_contracts WHERE contract_no='BROOM-CONTRACT-001'"
        ).fetchone()
        db.close()
        self.assertIsNotNone(contract)
        self.assertEqual(contract['room_id'], room_id)
        self.assertIsNone(contract['commercial_space_id'])
        self.assertEqual(float(contract['rent_amount']), 5800.0)
        self.assertEqual(float(contract['deposit_amount']), 7250.0)

        status, preview = http_get(f'/merchant_contracts/{contract["id"]}/billing?service_start=2039-01-01', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('BROOM-CONTRACT-001', preview)
        self.assertIn('¥5800.00', preview)

        status, _, _ = http_post(f'/merchant_contracts/{contract["id"]}/billing/confirm', {
            'service_start': '2039-01-01',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = get_db()
        bills = db.execute(
            "SELECT room_id,commercial_space_id,amount FROM bills WHERE source='merchant_contract' AND source_ref=? ORDER BY amount DESC",
            (str(contract['id']),),
        ).fetchall()
        db.close()
        self.assertTrue(bills)
        self.assertTrue(all(row['room_id'] == room_id and row['commercial_space_id'] is None for row in bills))


    def test_contract_acceptance_page_documents_full_contract_flow(self):
        status, body = http_get('/delivery_center/contracts', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('空间合同档案验收', body)
        for text in ['新增档案', '资料备查', '去商业收费', '收费登记', '合同档案预警', '续签合同', '退租协议', '历史账单']:
            self.assertIn(text, body)
        for text in ['档案不自动收费', '押金单价口径', '列表操作降噪']:
            self.assertIn(text, body)
        self.assertNotIn('商场收费以商户合同为核心', body)
        for href in ['/merchant_contracts', '/alert_center', '/bills', '/payments']:
            self.assertIn(href, body)


    def test_contract_acceptance_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'contract_accept_manager_scope', 'manager123', 'manager', '合同验收管理员'
        )
        cashier_cookie = self._create_user_and_login(
            'contract_accept_cashier_scope', 'cashier123', 'cashier', '合同验收收费员'
        )

        status, _, loc = http_get_with_location('/delivery_center/contracts', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/contracts', cashier_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_import_acceptance_page_documents_preview_and_confirm_flow(self):
        status, body = http_get('/delivery_center/import', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('导入核对与修正验收', body)
        for text in ['字段识别', '调整字段映射', '数据核对与修正', '问题行/重复数据提示']:
            self.assertIn(text, body)
        for text in ['预览阶段不写入数据库', '确认导入后才写入', '历史金额不会自动入账']:
            self.assertIn(text, body)
        for href in ['/import', '/import/template/basic.xlsx', '/rooms']:
            self.assertIn(href, body)


    def test_import_acceptance_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'import_accept_manager_scope', 'manager123', 'manager', '导入验收管理员'
        )
        cashier_cookie = self._create_user_and_login(
            'import_accept_cashier_scope', 'cashier123', 'cashier', '导入验收收费员'
        )

        status, _, loc = http_get_with_location('/delivery_center/import', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/import', cashier_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_delivery_checklist_page_documents_a_phase_release_gates(self):
        status, body = http_get('/delivery_center/checklist', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('2.0 交付验收清单', body)
        for text in ['合同闭环', '导入闭环', '权限闭环', '云端技术备查', '备份恢复', '系统健康', '全量测试']:
            self.assertIn(text, body)
        for text in ['431 passed', 'PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 -m pytest', '进入 2.0 桌面稳定版收口']:
            self.assertIn(text, body)
        for href in ['/delivery_center/contracts', '/delivery_center/import', '/users', '/cloud_schema', '/backups', '/system_health']:
            self.assertIn(href, body)


    def test_delivery_checklist_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'delivery_checklist_manager_scope', 'manager123', 'manager', '总验收管理员'
        )
        finance_cookie = self._create_user_and_login(
            'delivery_checklist_finance_scope', 'finance123', 'finance', '总验收财务'
        )

        status, _, loc = http_get_with_location('/delivery_center/checklist', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/checklist', finance_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))


    def test_staff_guide_page_documents_daily_employee_workflows(self):
        status, body = http_get('/delivery_center/staff_guide', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('员工操作说明', body)
        for text in ['财务每天怎么操作', '收费员怎么收费', '客服业务编辑怎么维护资料和催缴', '管理层怎么看报表']:
            self.assertIn(text, body)
        for text in ['导入/录入资料', '抄表', '物业收费/商业收费', '账单核对', '收费登记', '收据/发票', '报表 → 期末结账', '打印收据', '催缴管理', '对账报表', '智能预警']:
            self.assertIn(text, body)
        self.assertNotIn('合同出账预览', body)
        for href in ['/import', '/meter_readings', '/commercial_billing', '/merchant_contracts', '/billing', '/bills', '/payments', '/reminders', '/reports', '/alert_center']:
            self.assertIn(href, body)


    def test_staff_guide_page_access_matches_delivery_center_scope(self):
        manager_cookie = self._create_user_and_login(
            'staff_guide_manager_scope', 'manager123', 'manager', '员工说明管理员'
        )
        frontdesk_cookie = self._create_user_and_login(
            'staff_guide_frontdesk_scope', 'frontdesk123', 'frontdesk', '员工说明前台'
        )

        status, _, loc = http_get_with_location('/delivery_center/staff_guide', manager_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))

        status, _, loc = http_get_with_location('/delivery_center/staff_guide', frontdesk_cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('无权限', urllib.parse.unquote(loc))
