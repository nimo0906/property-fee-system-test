#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests chunk 42: special turnover rent contracts."""

from tests.integration_base import *


class TestIntegration42(IntegrationTestBase):
    def test_contract_form_exposes_special_rent_fields(self):
        status, page = http_get('/merchant_contracts/create', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('特殊计租方式', page)
        self.assertIn('固定租金+销售额分成', page)
        self.assertIn('销售额分成比例', page)

    def test_import_special_turnover_rent_rule_and_generate_bill(self):
        import server.db as db_module
        from server.merchant_contract_import_store import _rows_from_form, _upsert_row
        from server.special_rent import special_rule_for

        rows = _rows_from_form({
            'row_count': ['1'], 'include_0': ['1'], 'row_no_0': ['6'],
            'space_no_0': ['(-1F)-07'], 'contract_no_0': ['D3'],
            'merchant_name_0': ['西安麦当劳'], 'shop_name_0': ['麦当劳'],
            'floor_0': ['-1'], 'start_date_0': ['2014-01-01'],
            'end_date_0': ['2033-12-31'], 'lease_term_0': ['20'],
            'contract_area_0': ['255.5'], 'building_area_0': ['263'],
            'rent_rate_0': ['100'], 'rent_mode_0': ['higher_of_fixed_or_turnover'],
            'turnover_rate_0': ['0.1'], 'property_rate_0': ['5'],
            'deposit_amount_0': ['0'], 'rent_cycle_0': ['monthly'],
            'notes_0': ['营业额分成+保底租金'],
        })
        self.assertEqual(rows[0]['errors'], [])
        db = db_module.get_db()
        _upsert_row(db, rows[0])
        db.commit()
        contract = db.execute("SELECT * FROM merchant_contracts WHERE contract_no='D3'").fetchone()
        rule = special_rule_for(db, contract['id'])
        db.close()
        self.assertIsNotNone(rule)
        self.assertEqual(rule['rent_mode'], 'higher_of_fixed_or_turnover')
        self.assertAlmostEqual(float(rule['turnover_rate']), 0.1)
        self.assertAlmostEqual(float(rule['fixed_amount']), 25550.0)

        status, page = http_get(f"/merchant_contracts/{contract['id']}", self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('特殊计租', page)
        self.assertIn('销售额出账', page)

        status, form = http_get(f"/merchant_contracts/{contract['id']}/turnover_rent", self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('本期销售额', form)
        status, _, loc = http_post(f"/merchant_contracts/{contract['id']}/turnover_rent", {
            'billing_period': '2026-06',
            'turnover_amount': '500000',
            'notes': '6月销售额分成',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        bill = db.execute("""SELECT amount,billing_period,source,source_ref,notes FROM bills
            WHERE source='merchant_contract' AND source_ref=? ORDER BY id DESC LIMIT 1""", (str(contract['id']),)).fetchone()
        record = db.execute("SELECT * FROM contract_turnover_records WHERE contract_id=? AND billing_period='2026-06'", (contract['id'],)).fetchone()
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['amount'], 50000.0)
        self.assertEqual(bill['billing_period'], '2026-06')
        self.assertIn('特殊计租销售额出账', bill['notes'])
        self.assertIsNotNone(record)
        self.assertEqual(record['rent_amount'], 50000.0)

    def test_special_rent_contract_skips_regular_rent_receivable(self):
        import server.db as db_module
        from server.merchant_contract_import_store import _rows_from_form, _upsert_row

        row = _rows_from_form({
            'row_count': ['1'], 'include_0': ['1'], 'space_no_0': ['SP-SPECIAL-2'],
            'contract_no_0': ['HT-SPECIAL-2'], 'merchant_name_0': ['特殊计租商户'],
            'shop_name_0': ['特殊计租店'], 'floor_0': ['1'], 'start_date_0': ['2026-01-01'],
            'end_date_0': ['2026-12-31'], 'lease_term_0': ['1'], 'contract_area_0': ['100'],
            'building_area_0': ['100'], 'rent_rate_0': ['100'], 'rent_mode_0': ['fixed_plus_turnover'],
            'turnover_rate_0': ['0.05'], 'property_rate_0': ['5'], 'rent_cycle_0': ['monthly'],
        })[0]
        db = db_module.get_db()
        _upsert_row(db, row)
        db.commit(); db.close()

        status, page = http_get('/commercial_receivables?today=2026-01-01&advance_days=30&keyword=HT-SPECIAL-2', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('合同租金', page)
        self.assertIn('合同物业费', page)

    def test_legacy_special_rent_preview_confirm_creates_contract(self):
        import server.db as db_module
        from server.merchant_contract_import_store import _rows_from_form, _upsert_row
        from server.special_rent import special_rule_for

        rows = _rows_from_form({
            'row_count': ['1'], 'include_0': ['1'], 'row_no_0': ['6'],
            'space_no_0': ['（-1F）-07'], 'contract_no_0': ['D3-LEGACY'],
            'merchant_name_0': ['西安麦当劳'], 'shop_name_0': ['麦当劳'],
            'floor_0': ['-1'], 'start_date_0': ['2014-01-01'],
            'end_date_0': ['2033-12-31'], 'lease_term_0': ['20'],
            'contract_area_0': ['255.5'], 'building_area_0': ['263'],
            'rent_rate_0': [''], 'property_rate_0': ['5'],
            'deposit_amount_0': ['0'], 'rent_cycle_0': ['monthly'],
            'notes_0': ['当月营业额10%，保底租金取其高'],
        })
        self.assertEqual(rows[0]['rent_mode'], 'higher_of_fixed_or_turnover')
        self.assertEqual(rows[0]['errors'], [])
        db = db_module.get_db()
        result = _upsert_row(db, rows[0])
        db.commit()
        contract = db.execute("SELECT * FROM merchant_contracts WHERE contract_no='D3-LEGACY'").fetchone()
        rule = special_rule_for(db, contract['id']) if contract else None
        db.close()
        self.assertEqual(result, 'created')
        self.assertIsNotNone(contract)
        self.assertIsNotNone(rule)
        self.assertEqual(rule['rent_mode'], 'higher_of_fixed_or_turnover')
        self.assertAlmostEqual(float(rule['turnover_rate']), 0.1)

    def test_contract_import_skipped_rows_return_editable_second_review(self):
        import server.db as db_module

        status, html, _ = http_post('/import/upload', {
            'mode': 'confirm_commercial_contracts',
            'data_type': 'commercial_contracts',
            'filename': 'contracts.xlsx',
            'row_count': '2',
            'include_0': '1', 'row_no_0': '6',
            'space_no_0': 'OK-SPACE-42', 'contract_no_0': 'HT-OK-42',
            'merchant_name_0': '正常合同商户', 'shop_name_0': '正常品牌',
            'floor_0': '1', 'start_date_0': '2026-01-01',
            'end_date_0': '2026-12-31', 'lease_term_0': '1',
            'contract_area_0': '100', 'building_area_0': '100',
            'rent_rate_0': '80', 'property_rate_0': '5',
            'rent_cycle_0': 'monthly',
            'include_1': '1', 'row_no_1': '7',
            'space_no_1': '', 'contract_no_1': 'HT-BAD-42',
            'merchant_name_1': '问题合同商户', 'shop_name_1': '问题品牌',
            'floor_1': '1', 'start_date_1': '',
            'end_date_1': '', 'lease_term_1': '',
            'contract_area_1': '0', 'building_area_1': '0',
            'rent_rate_1': '0', 'property_rate_1': '0',
            'rent_cycle_1': 'monthly',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('合同问题行二次校对', html)
        self.assertIn('已导入：新增 1 条，更新 0 条', html)
        self.assertIn('问题合同商户', html)
        self.assertIn('name="row_count" value="1"', html)
        self.assertIn('商铺号为空', html)

        db = db_module.get_db()
        ok = db.execute("SELECT id FROM merchant_contracts WHERE contract_no='HT-OK-42'").fetchone()
        bad = db.execute("SELECT id FROM merchant_contracts WHERE contract_no='HT-BAD-42'").fetchone()
        db.close()
        self.assertIsNotNone(ok)
        self.assertIsNone(bad)

    def test_import_keeps_same_contract_no_for_different_spaces(self):
        import server.db as db_module
        from server.merchant_contract_import_store import _rows_from_form, _upsert_row
        from server.special_rent import special_rule_for

        rows = _rows_from_form({
            'row_count': ['2'],
            'include_0': ['1'], 'row_no_0': ['6'],
            'space_no_0': ['（-1F）-07'], 'contract_no_0': ['D3-SAME'],
            'merchant_name_0': ['西安麦当劳'], 'shop_name_0': ['麦当劳负一层'],
            'floor_0': ['-1'], 'start_date_0': ['2014-01-01'],
            'end_date_0': ['2033-12-31'], 'lease_term_0': ['20'],
            'contract_area_0': ['255.5'], 'building_area_0': ['263'],
            'rent_rate_0': ['212'], 'rent_mode_0': ['fixed_plus_turnover'],
            'turnover_rate_0': ['10'], 'property_rate_0': ['0'],
            'rent_cycle_0': ['monthly'], 'notes_0': ['固定+销售额10%'],
            'include_1': ['1'], 'row_no_1': ['15'],
            'space_no_1': ['1F-06'], 'contract_no_1': ['D3-SAME'],
            'merchant_name_1': ['西安麦当劳'], 'shop_name_1': ['麦当劳一层'],
            'floor_1': ['1'], 'start_date_1': ['2014-01-01'],
            'end_date_1': ['2033-12-31'], 'lease_term_1': ['20'],
            'contract_area_1': ['170.8'], 'building_area_1': ['183'],
            'rent_rate_1': ['0'], 'rent_mode_1': ['turnover_only'],
            'turnover_rate_1': ['0.09'], 'property_rate_1': ['3000'],
            'rent_cycle_1': ['monthly'], 'notes_1': ['销售额9%'],
        })
        db = db_module.get_db()
        for row in rows:
            self.assertEqual(row['errors'], [])
            _upsert_row(db, row)
        db.commit()
        contracts = db.execute("""SELECT c.*,s.space_no FROM merchant_contracts c
            JOIN commercial_spaces s ON c.commercial_space_id=s.id
            WHERE c.contract_no LIKE 'D3-SAME%' ORDER BY s.space_no""").fetchall()
        rules = [special_rule_for(db, c['id']) for c in contracts]
        db.close()
        self.assertEqual(len(contracts), 2)
        self.assertEqual({c['space_no'] for c in contracts}, {'（-1F）-07', '1F-06'})
        self.assertEqual(len({c['contract_no'] for c in contracts}), 2)
        first_rule = next(r for c, r in zip(contracts, rules) if c['space_no'] == '（-1F）-07')
        self.assertEqual(first_rule['rent_mode'], 'fixed_plus_turnover')
        self.assertAlmostEqual(float(first_rule['turnover_rate']), 0.10)
