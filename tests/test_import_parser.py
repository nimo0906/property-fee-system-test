#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for real spreadsheet parsing used by data import."""

import os
import unittest

from server.import_data import ImportMixin
from server.import_parser import (
    build_column_map,
    detect_data_type,
    detect_header_row,
    enrich_column_map_from_subheader,
    parse_rows,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA = os.path.join(ROOT, '真实数据')


class TestImportParser(unittest.TestCase):

    def test_parse_legacy_xls_payment_ledger(self):
        path = os.path.join(REAL_DATA, '收款明细表2026.5.27.XLS')
        with open(path, 'rb') as f:
            rows = parse_rows(path, f.read())
        header_idx = detect_header_row(rows, ImportMixin.COLUMN_MAP)
        headers = rows[header_idx]
        col_map = build_column_map(headers, ImportMixin.COLUMN_MAP)

        self.assertEqual(header_idx, 0)
        self.assertGreater(len(rows), 10000)
        self.assertIn('room_number', col_map)
        self.assertIn('payment_date', col_map)
        self.assertEqual(detect_data_type(col_map, headers), 'payment_ledger')

    def test_parse_wps_xlsx_even_when_styles_are_invalid(self):
        path = os.path.join(REAL_DATA, '金莎B座7-26层业态表-2026年5月(1).xlsx')
        with open(path, 'rb') as f:
            rows = parse_rows(path, f.read())
        header_idx = detect_header_row(rows, ImportMixin.COLUMN_MAP)
        headers = rows[header_idx]
        col_map = build_column_map(headers, ImportMixin.COLUMN_MAP)

        self.assertGreater(len(rows), 10)
        self.assertIn('room_number', col_map)
        self.assertIn('area', col_map)

    def test_enriches_contract_period_from_subheader(self):
        path = os.path.join(REAL_DATA, '金莎B座7-26层业态表-2026年5月(1).xlsx')
        with open(path, 'rb') as f:
            rows = parse_rows(path, f.read())
        header_idx = detect_header_row(rows, ImportMixin.COLUMN_MAP)
        headers = rows[header_idx]
        col_map = build_column_map(headers, ImportMixin.COLUMN_MAP)
        col_map = enrich_column_map_from_subheader(col_map, headers, rows, ImportMixin.COLUMN_MAP, header_idx)

        self.assertIn('contract_period', col_map)


if __name__ == '__main__':
    unittest.main()
