#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for importing basic room and owner data."""

import sqlite3
import unittest

from server.basic_import import import_basic_info, preview_basic_info_import


class TestBasicImport(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE owners(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT)")
        self.db.execute(
            "CREATE TABLE rooms(id INTEGER PRIMARY KEY AUTOINCREMENT, building TEXT, unit TEXT, room_number TEXT, "
            "floor INTEGER, category TEXT, area REAL, owner_id INTEGER, contract_start TEXT, contract_end TEXT, business_type TEXT, tenant_name TEXT, notes TEXT)"
        )
        self.db.execute("CREATE TABLE bills(id INTEGER PRIMARY KEY AUTOINCREMENT)")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_imports_room_owner_contract_and_notes_without_money(self):
        headers = ['类别', '房号', '业主姓名', '面积㎡', '联系电话', '租户姓名', '店铺名称', '业态', '合同缴租期']
        col_map = {
            'category': 0, 'room_number': 1, 'owner_name': 2, 'area': 3,
            'owner_phone': 4, 'tenant_name': 5, 'shop_name': 6,
            'business_type': 7, 'contract_period': 8,
        }
        rows = [['商户', 'B座一楼大厅', '东大置业', '18.9', '18291415177', '程西琴', '烟酒小商店', '便利店', '2024.10.1-2027.9.30']]

        result = import_basic_info(self.db, headers, rows, col_map)
        self.db.commit()

        self.assertEqual(result['imported_rooms'], 1)
        self.assertEqual(result['imported_owners'], 1)
        self.assertEqual(len(result['changed_rooms']), 1)
        self.assertEqual(result['changed_rooms'][0]['action'], '新增')
        self.assertEqual(result['changed_rooms'][0]['building'], 'B座')
        self.assertEqual(result['changed_rooms'][0]['room_number'], '一楼大厅')
        self.assertEqual(result['changed_rooms'][0]['owner_name'], '东大置业')
        self.assertEqual(result['changed_rooms'][0]['contract_start'], '2024-10-01')
        room = self.db.execute("SELECT * FROM rooms WHERE room_number='一楼大厅'").fetchone()
        owner = self.db.execute("SELECT * FROM owners WHERE name='东大置业'").fetchone()
        bills = self.db.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
        self.assertIsNotNone(room)
        self.assertEqual(room['building'], 'B座')
        self.assertEqual(room['contract_start'], '2024-10-01')
        self.assertEqual(room['contract_end'], '2027-09-30')
        self.assertEqual(room['business_type'], '便利店')
        self.assertEqual(room['tenant_name'], '程西琴')
        self.assertNotIn('业态:便利店', room['notes'])
        self.assertEqual(owner['phone'], '18291415177')
        self.assertEqual(bills, 0)

    def test_preview_does_not_write_database(self):
        headers = ['类别', '房号', '业主姓名', '面积㎡', '联系电话', '合同缴租期']
        col_map = {'category': 0, 'room_number': 1, 'owner_name': 2, 'area': 3, 'owner_phone': 4, 'contract_period': 5}
        rows = [['商户', 'B座913', '文化宫', '50', '13900000000', 'bad-date']]

        result = preview_basic_info_import(self.db, headers, rows, col_map)

        self.assertEqual(result['imported_rooms'], 1)
        self.assertEqual(result['imported_owners'], 1)
        self.assertEqual(len(result['invalid_contracts']), 1)
        self.assertEqual(len(result['changed_rooms']), 1)
        self.assertEqual(result['changed_rooms'][0]['action'], '新增')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM owners").fetchone()[0], 0)

    def test_skips_advertising_rows_without_real_room_shape_or_area(self):
        headers = ['类别', '房号', '业主姓名', '面积㎡', '联系电话', '租户姓名', '店铺名称', '业态', '合同缴租期']
        col_map = {
            'category': 0, 'room_number': 1, 'owner_name': 2, 'area': 3,
            'owner_phone': 4, 'tenant_name': 5, 'shop_name': 6,
            'business_type': 7, 'contract_period': 8,
        }
        rows = [
            ['东大置业', 'A座1F-01', '东大置业', '28.8', '18091692999', '杨旭', '每一天便利店', '便利店', '2022.7.1-2027.6.30'],
            ['东大置业', 'B座一楼大厅', '东大置业', '18.9', '18291415177', '程西琴', '烟酒小商店', '便利店', '2024.10.1-2027.9.30'],
            ['', '美容护肤', '', '', '', '', '58*88', '藏式健康管理中心', '2026.4.14-2027.6.13'],
            ['', '美发', '', '', 'B点（右手）', '', '58*88', '拼豆', '2026.1.16-2027.1.15'],
        ]

        result = import_basic_info(self.db, headers, rows, col_map)
        self.db.commit()

        self.assertEqual(result['imported_rooms'], 2)
        self.assertEqual(result['skipped'], 2)
        self.assertTrue(any('非房间资料' in x for x in result['skip_examples']))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 2)
        self.assertIsNone(self.db.execute("SELECT * FROM rooms WHERE room_number='美容护肤'").fetchone())
        self.assertIsNone(self.db.execute("SELECT * FROM rooms WHERE room_number='美发'").fetchone())

    def test_imports_explicit_contract_start_and_end_columns(self):
        headers = ['类别', '房号', '业主姓名', '面积㎡', '合同开始日期', '合同到期日期']
        col_map = {
            'category': 0, 'room_number': 1, 'owner_name': 2, 'area': 3,
            'contract_start': 4, 'contract_end': 5,
        }
        rows = [['商户', 'B座950', '独立日期业主', '60', '2026-01-15', '2026-12-31']]

        result = import_basic_info(self.db, headers, rows, col_map)
        self.db.commit()

        self.assertEqual(result['imported_rooms'], 1)
        self.assertEqual(result['changed_rooms'][0]['contract_start'], '2026-01-15')
        self.assertEqual(result['changed_rooms'][0]['contract_end'], '2026-12-31')
        room = self.db.execute("SELECT * FROM rooms WHERE room_number='950'").fetchone()
        self.assertEqual(room['contract_start'], '2026-01-15')
        self.assertEqual(room['contract_end'], '2026-12-31')

    def test_imports_mall_merchant_commercial_fields_and_flags_missing_rules(self):
        self.db.execute("ALTER TABLE rooms ADD COLUMN custom_rate REAL")
        self.db.execute("ALTER TABLE rooms ADD COLUMN payment_cycle TEXT")
        self.db.execute("ALTER TABLE rooms ADD COLUMN shop_name TEXT")
        self.db.execute("ALTER TABLE rooms ADD COLUMN water_rate_type TEXT")
        headers = ['楼栋', '单元/座', '铺位号', '房屋类别', '面积㎡', '商户名称', '店铺名称', '业态', '物业费单价', '缴费周期', '水费标准']
        col_map = {
            'building': 0, 'unit': 1, 'room_number': 2, 'category': 3, 'area': 4,
            'owner_name': 5, 'shop_name': 6, 'business_type': 7, 'custom_rate': 8,
            'payment_cycle': 9, 'water_rate_type': 10,
        }
        rows = [
            ['金莎国际', '商场', '1F-101', '商户', '88.5', '甲商贸', '甲店', '餐饮', '4.8', '季付', '特行'],
            ['金莎国际', '商场', '1F-102', '居民', '60', '乙商贸', '乙店', '零售', '', '', ''],
        ]

        result = import_basic_info(self.db, headers, rows, col_map)
        self.db.commit()

        self.assertEqual(result['imported_rooms'], 2)
        room = self.db.execute("SELECT * FROM rooms WHERE room_number='1F-101'").fetchone()
        self.assertEqual(room['unit'], '商场')
        self.assertEqual(room['shop_name'], '甲店')
        self.assertEqual(room['custom_rate'], 4.8)
        self.assertEqual(room['payment_cycle'], 'quarterly')
        self.assertEqual(room['water_rate_type'], '特行')
        reasons = '；'.join(r['reason'] for r in result['problem_rows'])
        self.assertIn('商场商户误填为居民', reasons)
        self.assertIn('缺少物业费单价', reasons)
        self.assertIn('缺少缴费周期', reasons)


if __name__ == '__main__':
    unittest.main()
