#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for payment ledger rule analysis."""

import os
import unittest

from server.import_parser import parse_rows
from server.payment_ledger import analyze_basic_info, analyze_payment_ledger, room_ref_keys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_XLS = os.path.join(ROOT, '真实数据', '收款明细表2026.5.27.XLS')


def require_real_file(path):
    if not os.path.exists(path):
        raise unittest.SkipTest('真实数据文件不存在: ' + path)
    return path


class TestPaymentLedger(unittest.TestCase):

    def test_room_ref_matching_handles_commercial_prefix(self):
        rooms = [{'building': 'B座', 'room_number': '913'}, {'building': 'B座', 'room_number': '1810'}]
        headers = ['房间号', '本期金额', '本期收款(合计)', '电费']
        rows = [['商用-B座913', '210', '210', '210'], ['商用-B座B1810', '100', '100', '100']]
        result = analyze_payment_ledger(headers, rows, rooms)
        self.assertEqual(result['matched_rooms'], 2)

    def test_room_ref_keys_normalize_repeated_building_and_ranges(self):
        keys = room_ref_keys('商用-B座B2002-2003')
        self.assertIn('2002', keys)
        self.assertIn('2003', keys)
        self.assertIn('B2002', keys)
        self.assertIn('B2003', keys)
        self.assertIn('2512', room_ref_keys('商用-B座2511-2513'))

    def test_room_ref_matching_handles_real_unmatched_variants(self):
        rooms = [
            {'building': 'B座', 'room_number': '2511'},
            {'building': 'B座', 'room_number': '2513'},
            {'building': 'B座', 'room_number': '1810'},
            {'building': 'B座', 'room_number': '2002'},
            {'building': 'B座', 'room_number': '2003'},
            {'building': 'B座', 'room_number': '1524'},
        ]
        headers = ['房间号', '本期金额', '本期收款(合计)', '电费']
        rows = [
            ['商用-B座2511-2513', '1', '1', '1'],
            ['商用-B座B1810', '1', '1', '1'],
            ['商用-B座B2002-2003', '1', '1', '1'],
            ['住宅-B座B1524', '1', '1', '1'],
        ]
        result = analyze_payment_ledger(headers, rows, rooms)
        self.assertEqual(result['matched_rooms'], 4)
        self.assertEqual(result['unmatched_rooms'], 0)

    def test_analyze_real_payment_ledger_marks_ambiguous_columns(self):
        with open(require_real_file(REAL_XLS), 'rb') as f:
            rows = parse_rows(REAL_XLS, f.read())
        headers = rows[0]
        result = analyze_payment_ledger(headers, rows[1:], [
            {'building': 'B座', 'room_number': '913'},
            {'building': 'B座', 'room_number': '1810'},
        ])

        self.assertGreater(result['total_rows'], 10000)
        self.assertGreater(result['rows_with_payment'], 10000)
        names = {x['name']: x for x in result['fee_stats']}
        self.assertEqual(names['其它费用']['action'], 'amount_confirm')
        self.assertEqual(names['装修押金']['action'], 'deposit_hint')
        self.assertEqual(names['电费']['action'], 'matched_fee')

    def test_basic_info_analysis_counts_owner_room_and_contract_fields(self):
        headers = ['类别', '房号', '业主姓名', '面积㎡', '联系电话', '租户姓名', '店铺名称', '业态', '合同缴租期']
        rows = [
            ['商户', 'B座一楼大厅', '东大置业', '18.9', '18291415177', '程西琴', '烟酒小商店', '便利店', '2024.10.1-2027.9.30'],
            ['商户', 'A座1F-01', '东大置业', '28.8', '/', '杨旭', '每一天便利店', '便利店', '2022.7.1-2027.6.30'],
        ]
        result = analyze_basic_info(headers, rows)
        self.assertEqual(result['field_counts']['room_number'], 2)
        self.assertEqual(result['field_counts']['owner_name'], 2)
        self.assertEqual(result['field_counts']['tenant_name'], 2)
        self.assertEqual(result['field_counts']['contract_period'], 2)


if __name__ == '__main__':
    unittest.main()
