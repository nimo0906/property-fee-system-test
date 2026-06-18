#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 13."""

from tests.integration_base import *


class TestIntegration13(IntegrationTestBase):
    def test_merchant_contract_archive_imports_rented_contract_sheet_only(self):
        import io
        import openpyxl
        from server.db import get_db

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '在租合同'
        ws.append(['房产出租合同情况明细表'])
        ws.append(['填报单位：陕西金莎国际商业管理有限公司'])
        ws.append(['楼层', '序号', '合同编号', '商铺号', '起租期（日）', '承租人', '进场日', '免租装修期（日）', '合同面积（㎡）', '实际建筑面积（㎡）', '租赁期限（年）', '经营品牌', '联系电话', '交租方式', '租金保证金', '经营管理费/㎡元', '租金/㎡元', '物业费/㎡', '垃圾费/㎡', '水费/吨', '电费/度', '递增', '备注'])
        ws.append(['合计', '', '', '', '', '', '', '', 1000, 980, '', '', '', '', '', '', '', '', '', '', '', '', ''])
        ws.append(['负一层', 1, 'HT-REAL-001', 'D11-01 （-1F）-02A', '2026-01-15', '真实承租公司', '2025-12-01', '45天', 231, 240, 5, '真实品牌', '13900009999', '季付', 20790, '', 90, 5, 0.9, 5.8, 0.85, '第3年递增', '真实备注'])
        ws.append(['负一层', 2, 'HT-PERCENT-001', 'B1-07', '2026-03-01', '销售额租金商户', '2026-02-01', '30天', 100, 100, 5, '销售额品牌', '13900008888', '月付', 50000, '', '当月销售额10%', 0, 0, 5.8, 0.85, '', '保底提成取其高'])
        other = wb.create_sheet('退租合同')
        other.append(['合同编号', '商铺号', '承租人'])
        other.append(['HT-OLD-001', 'OLD-SPACE', '已退租商户'])
        out = io.BytesIO()
        wb.save(out)

        status, page = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('/merchant_contracts/import', page)
        self.assertNotIn('导入合同档案', page)

        status, import_page = http_get('/import', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('value="commercial_contracts"', import_page)
        self.assertIn('value="b_tower_contracts"', import_page)

        status, preview, _ = http_post_multipart('/import/upload', {'mode': 'preview', 'data_type': 'commercial_contracts'}, {
            'file': ('real-contracts.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', out.getvalue())
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('在租合同导入预览', preview)
        self.assertIn('只读取 Excel 的“在租合同”sheet', preview)
        self.assertIn('真实承租公司', preview)
        self.assertIn('D11-01 （-1F）-02A', preview)
        self.assertIn('HT-REAL-001', preview)
        self.assertIn('name="space_no_0"', preview)
        self.assertIn('name="contract_no_0"', preview)
        self.assertIn('name="merchant_name_0"', preview)
        self.assertIn('name="contract_area_0"', preview)
        self.assertIn('可编辑核对表', preview)
        self.assertIn('2026-01-15 至 2031-01-14', preview)
        self.assertIn('合同面积 231.00㎡', preview)
        self.assertIn('建筑面积 240.00㎡', preview)
        self.assertIn('销售额租金商户', preview)
        self.assertIn('百分比/销售额租金需人工核对', preview)
        self.assertIn('合同问题行', preview)
        self.assertIn('/import/problem_rows/', preview)
        self.assertNotIn('已退租商户', preview)

        token_match = re.search(r'name="upload_token" value="([^"]+)"', preview)
        self.assertIsNotNone(token_match)
        status, _, loc = http_post('/import/upload', {
            'mode': 'confirm_commercial_contracts',
            'data_type': 'commercial_contracts',
            'row_count': '1',
            'include_0': '1',
            'row_no_0': '5',
            'space_no_0': 'EDIT-SPACE-01',
            'contract_no_0': 'HT-EDIT-001',
            'merchant_name_0': '编辑后承租人',
            'shop_name_0': '编辑后品牌',
            'floor_0': '-1',
            'start_date_0': '2026-02-01',
            'end_date_0': '2031-01-31',
            'lease_term_0': '5',
            'contract_area_0': '300',
            'building_area_0': '320',
            'rent_rate_0': '100',
            'property_rate_0': '6',
            'deposit_amount_0': '30000',
            'rent_cycle_0': 'quarterly',
            'water_rate_0': '5.8',
            'electricity_rate_0': '0.85',
            'notes_0': '编辑后备注',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('合同档案导入完成', urllib.parse.unquote(loc))

        db = get_db()
        space = db.execute("SELECT * FROM commercial_spaces WHERE space_no=?", ('EDIT-SPACE-01',)).fetchone()
        contract = db.execute("SELECT * FROM merchant_contracts WHERE contract_no=?", ('HT-EDIT-001',)).fetchone()
        db.close()
        self.assertIsNotNone(space)
        self.assertEqual(space['space_no'], 'EDIT-SPACE-01')
        self.assertEqual(space['merchant_name'], '编辑后承租人')
        self.assertEqual(space['shop_name'], '编辑后品牌')
        self.assertAlmostEqual(float(space['area']), 300.0)
        self.assertIsNotNone(contract)
        self.assertEqual(contract['merchant_name'], '编辑后承租人')
        self.assertEqual(contract['shop_name'], '编辑后品牌')
        self.assertAlmostEqual(float(contract['contract_area']), 300.0)
        self.assertAlmostEqual(float(contract['building_area']), 320.0)
        self.assertEqual(contract['start_date'], '2026-02-01')
        self.assertEqual(contract['end_date'], '2031-01-31')
        self.assertAlmostEqual(float(contract['rent_amount']), 300 * 100)
        self.assertAlmostEqual(float(contract['property_rate']), 6.0)
        self.assertAlmostEqual(float(contract['deposit_amount']), 30000.0)
        self.assertIn('水费/吨：5.8', contract['notes'])
        self.assertIn('电费/度：0.85', contract['notes'])
        self.assertIn('原备注：编辑后备注', contract['notes'])


    def test_merchant_contract_archive_groups_b_tower_and_commercial_contracts(self):
        from server.contract_billing import create_merchant_contract
        from server.db import get_db

        db = get_db()
        b_owner = create_owner(db, 'B座合同租户', '13900001111')
        b_room = create_room(db, building='B座', unit='B座', room_number='B-1801', category='出租', area=88, owner_id=b_owner)
        mall_owner = create_owner(db, '商业合同商户', '13900002222')
        mall_room = create_room(db, building='商场', unit='商场', room_number='M-001', category='商户', area=120, owner_id=mall_owner)
        db.commit(); db.close()

        create_merchant_contract({
            'room_id': b_room, 'owner_id': b_owner, 'contract_no': 'HT-B-GROUP-001',
            'merchant_name': 'B座合同租户', 'shop_name': 'B座合同租户', 'rent_amount': 3000,
            'rent_cycle': 'monthly', 'property_rate': 3, 'property_cycle': 'monthly',
            'deposit_amount': 3000, 'contract_area': 88, 'building_area': 88,
            'start_date': '2038-01-01', 'end_date': '2038-12-31',
        })
        create_merchant_contract({
            'room_id': mall_room, 'owner_id': mall_owner, 'contract_no': 'HT-M-GROUP-001',
            'merchant_name': '商业合同商户', 'shop_name': '商业合同商户', 'rent_amount': 12000,
            'rent_cycle': 'monthly', 'property_rate': 5, 'property_cycle': 'monthly',
            'deposit_amount': 12000, 'contract_area': 120, 'building_area': 120,
            'start_date': '2038-01-01', 'end_date': '2038-12-31',
        })

        status, page = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<details class="contract-group" open>', page)
        self.assertIn('收费对象合同', page)
        self.assertIn('商业合同', page)
        self.assertIn('HT-B-GROUP-001', page)
        self.assertIn('HT-M-GROUP-001', page)
        self.assertIn('B-1801', page)
        self.assertIn('M-001', page)


    def test_merchant_contract_archive_searches_and_sorts_by_floor_ascending(self):
        from server.contract_billing import create_merchant_contract
        from server.db import get_db

        db = get_db()
        owner_low = create_owner(db, '低楼层合同商户', '13900004441')
        owner_high = create_owner(db, '高楼层合同商户', '13900004442')
        low_room = create_room(db, building='商场', unit='商场', room_number='F1-SEARCH', floor=1, category='商户', area=60, owner_id=owner_low)
        high_room = create_room(db, building='商场', unit='商场', room_number='F8-SEARCH', floor=8, category='商户', area=80, owner_id=owner_high)
        db.commit(); db.close()
        create_merchant_contract({
            'room_id': high_room, 'owner_id': owner_high, 'contract_no': 'HT-SEARCH-HIGH',
            'merchant_name': '高楼层合同商户', 'shop_name': '八楼搜索店', 'rent_amount': 8000,
            'rent_cycle': 'monthly', 'property_rate': 5, 'property_cycle': 'monthly',
            'deposit_amount': 8000, 'contract_area': 80, 'building_area': 80,
            'start_date': '2039-01-01', 'end_date': '2039-12-31',
        })
        create_merchant_contract({
            'room_id': low_room, 'owner_id': owner_low, 'contract_no': 'HT-SEARCH-LOW',
            'merchant_name': '低楼层合同商户', 'shop_name': '一楼搜索店', 'rent_amount': 6000,
            'rent_cycle': 'monthly', 'property_rate': 5, 'property_cycle': 'monthly',
            'deposit_amount': 6000, 'contract_area': 60, 'building_area': 60,
            'start_date': '2039-01-01', 'end_date': '2039-12-31',
        })

        status, page = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('搜索合同档案', page)
        self.assertIn('默认按楼层从低到高排序', page)
        self.assertLess(page.index('HT-SEARCH-LOW'), page.index('HT-SEARCH-HIGH'))

        status, search_page = http_get('/merchant_contracts?keyword=%E5%85%AB%E6%A5%BC%E6%90%9C%E7%B4%A2', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('八楼搜索店', search_page)
        self.assertIn('搜索结果', search_page)
        self.assertNotIn('一楼搜索店', search_page)


    def test_merchant_contract_import_redirects_to_unified_import_workbench(self):
        status, _, loc = http_get_with_location('/merchant_contracts/import', self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/import?data_type=commercial_contracts', loc)

