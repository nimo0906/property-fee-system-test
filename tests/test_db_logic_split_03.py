#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split tests from tests/test_db_logic.py chunk 03."""

from tests.test_db_logic_split_base import *


class TestDBLogic03(DBLogicTestBase):
    def test_auto_billing_fee_selection_controls_preview_items(self):
        from server.auto_billing import build_auto_billing_preview
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('自动项目业主')").lastrowid
        room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOSEL', 'B座', '1801', 18, '居民', 100, owner_id, '项目租户', '2026-06-27', '2027-06-26', 'quarterly')
        ).lastrowid
        property_fee = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(居民)'").fetchone()['id']
        elevator_fee = self.db.execute("SELECT id FROM fee_types WHERE name='电梯费'").fetchone()['id']
        self.db.commit()

        default_items = build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30)
        default_for_room = [x['fee_type_id'] for x in default_items if x['room_id'] == room_id]
        self.assertEqual(default_for_room, [property_fee])

        selected_items = build_auto_billing_preview(self.db, today='2026-05-28', advance_days=30, fee_ids=[property_fee, elevator_fee])
        selected_for_room = [x['fee_type_id'] for x in selected_items if x['room_id'] == room_id]
        self.assertEqual(selected_for_room, [property_fee, elevator_fee])


    def test_auto_billing_business_fee_applies_to_generic_commercial_scope(self):
        from server.auto_billing import build_auto_billing_preview
        owner_id = self.db.execute("INSERT INTO owners(name) VALUES('商业费范围业主')").lastrowid
        b_room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOFEE', 'B座', 'B1401', 14, '商户', 100, owner_id, 'B座商户', '2026-06-27', '2027-06-26', 'monthly')
        ).lastrowid
        mall_room_id = self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,contract_start,contract_end,payment_cycle) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ('AUTOFEE', '商场', 'M101', 1, '商户', 100, owner_id, '商场商户', '2026-06-27', '2027-06-26', 'monthly')
        ).lastrowid
        merchant_fee = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        row = self.db.execute("SELECT id FROM fee_types WHERE name='物业费(商业)'").fetchone()
        business_fee = row['id'] if row else self.db.execute(
            "INSERT INTO fee_types(name,calc_method,unit_price,billing_cycle,is_active,sort_order,notes) VALUES(?,?,?,?,?,?,?)",
            ('物业费(商业)', 'area', 30, 'monthly', 1, 31, '测试商业物业费')
        ).lastrowid
        self.db.commit()

        items = build_auto_billing_preview(
            self.db, today='2026-05-28', advance_days=30, fee_ids=[merchant_fee, business_fee], target_scope='all'
        )
        b_fee_ids = [x['fee_type_id'] for x in items if x['room_id'] == b_room_id]
        mall_fee_ids = [x['fee_type_id'] for x in items if x['room_id'] == mall_room_id]

        self.assertEqual(b_fee_ids, [merchant_fee, business_fee])
        self.assertEqual(mall_fee_ids, [merchant_fee, business_fee])


    def test_contract_archive_fees_do_not_show_in_daily_billing_scopes(self):
        from server.billing_rules import fee_in_scope
        archive_fees = [
            {'name': '合同租金', 'sort_order': 10},
            {'name': '合同物业费', 'sort_order': 11},
            {'name': '合同押金', 'sort_order': 12},
        ]

        for fee in archive_fees:
            self.assertFalse(fee_in_scope(fee, 'property'))
            self.assertFalse(fee_in_scope(fee, 'commercial'))
            self.assertFalse(fee_in_scope(fee, 'other'))


