#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests chunk 41: commercial receivables and contract amendments."""

from tests.integration_base import *


class TestIntegration41(IntegrationTestBase):
    def _contract(self, no='HT-AR-001', rent=3000, prop=5, start='2026-01-01', end='2026-12-31'):
        from server.contract_billing import create_merchant_contract
        import server.db as db_module
        db = db_module.get_db()
        owner_id = create_owner(db, no + '商户', '13900004101')
        space_id = db.execute("""
            INSERT INTO commercial_spaces(project_id,space_no,floor,area,shop_name,merchant_name,business_type,status)
            VALUES(1,?,1,100,?,?, '零售','active')
        """, (no + '-铺', no + '店', no + '商户')).lastrowid
        db.commit(); db.close()
        cid = create_merchant_contract({
            'commercial_space_id': space_id, 'owner_id': owner_id, 'contract_no': no,
            'merchant_name': no + '商户', 'shop_name': no + '店', 'rent_amount': rent,
            'rent_cycle': 'monthly', 'property_rate': prop, 'property_cycle': 'monthly',
            'deposit_amount': 0, 'contract_area': 100, 'building_area': 100,
            'start_date': start, 'end_date': end,
        })
        return cid, owner_id, space_id

    def test_commercial_receivables_preview_and_confirm_generates_contract_bills_once(self):
        import server.db as db_module
        cid, owner_id, space_id = self._contract('HT-AR-100')
        status, page = http_get('/commercial_receivables?today=2026-01-01&advance_days=30', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商业合同应收', page)
        self.assertIn('HT-AR-100', page)
        self.assertIn('合同租金', page)
        self.assertIn('合同物业费', page)
        self.assertIn('可生成', page)

        status, _, loc = http_post('/commercial_receivables/confirm', {
            'today': '2026-01-01', 'advance_days': '30',
            'item_keys': [f'{cid}:rent:2026-01-01:2026-01-31', f'{cid}:property:2026-01-01:2026-01-31'],
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        rows = db.execute("SELECT fee_type_id,amount,service_start,service_end,source,source_ref,commercial_space_id FROM bills WHERE source='merchant_contract' AND source_ref=? ORDER BY amount DESC", (str(cid),)).fetchall()
        db.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['amount'] for r in rows], [3000.0, 500.0])
        self.assertEqual(rows[0]['service_start'], '2026-01-01')
        self.assertEqual(rows[0]['service_end'], '2026-01-31')
        self.assertEqual(rows[0]['commercial_space_id'], space_id)

        status, page2 = http_get('/commercial_receivables?today=2026-01-01&advance_days=30&status=existing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('已存在', page2)
        self.assertNotIn('可生成</span>', page2)

    def test_commercial_receivables_confirm_uses_edited_dates_and_amount(self):
        import server.db as db_module
        cid, owner_id, space_id = self._contract('HT-AR-EDIT')
        key = f'{cid}:rent:2026-01-01:2026-01-31'
        status, page = http_get('/commercial_receivables?today=2026-01-01&advance_days=30', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'name="amount__{key}"', page)
        self.assertIn(f'name="service_start__{key}"', page)

        status, _, loc = http_post('/commercial_receivables/confirm', {
            'today': '2026-01-01', 'advance_days': '30', 'item_keys': key, 'confirm': '1',
            f'service_start__{key}': '2026-01-10',
            f'service_end__{key}': '2026-01-20',
            f'due_date__{key}': '2026-01-25',
            f'amount__{key}': '1234.6',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        row = db.execute("""SELECT amount,service_start,service_end,due_date,billing_period,notes
            FROM bills WHERE source='merchant_contract' AND source_ref=?""", (str(cid),)).fetchone()
        db.close()
        self.assertEqual(row['amount'], 1234.6)
        self.assertEqual(row['service_start'], '2026-01-10')
        self.assertEqual(row['service_end'], '2026-01-20')
        self.assertEqual(row['due_date'], '2026-01-25')
        self.assertEqual(row['billing_period'], '2026-01')
        self.assertIn('人工核对', row['notes'])

    def test_commercial_receivables_lists_optional_commercial_fees_and_respects_checked_items(self):
        import server.db as db_module
        cid, _, _ = self._contract('HT-AR-FEES2')
        status, page = http_get('/commercial_receivables?today=2026-01-01&advance_days=30&keyword=HT-AR-FEES2', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for fee_name in ['物业费(商业)', '泄水费', '装修管理费', '装修押金', '空调能源费']:
            self.assertIn(fee_name, page)
        self.assertIn('本页已勾选', page)
        self.assertIn('生成前核对', page)
        self.assertIn('可生成项目', page)
        self.assertIn('未自动勾选', page)
        self.assertIn('data-default-checked="0"', page)

        db = db_module.get_db()
        fee_rows = {r['name']: r['id'] for r in db.execute(
            "SELECT id,name FROM fee_types WHERE name IN ('物业费(商业)','泄水费','装修管理费','装修押金','空调能源费')"
        ).fetchall()}
        db.close()
        selected_two = [
            f'{cid}:commercial:{fee_rows["物业费(商业)"]}:2026-01-01:2026-01-31',
            f'{cid}:commercial:{fee_rows["泄水费"]}:2026-01-01:2026-01-31',
        ]
        status, _, loc = http_post('/commercial_receivables/confirm', {
            'today': '2026-01-01',
            'advance_days': '30',
            'item_keys': selected_two,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills?', loc)
        self.assertIn('keyword=HT-AR-FEES2', loc)
        db = db_module.get_db()
        names = [r['name'] for r in db.execute("""SELECT f.name FROM bills b
            JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.source='merchant_contract' AND b.source_ref=? ORDER BY f.name""", (str(cid),)).fetchall()]
        db.close()
        self.assertEqual(set(names), {'物业费(商业)', '泄水费'})

        cid5, _, _ = self._contract('HT-AR-FEES5')
        selected_five = [
            f'{cid5}:commercial:{fee_rows[name]}:2026-01-01:2026-01-31'
            for name in ['物业费(商业)', '泄水费', '装修管理费', '装修押金', '空调能源费']
        ]
        status, _, loc = http_post('/commercial_receivables/confirm', {
            'today': '2026-01-01',
            'advance_days': '30',
            'item_keys': selected_five,
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        generated = db.execute("SELECT COUNT(*) FROM bills WHERE source='merchant_contract' AND source_ref=?", (str(cid5),)).fetchone()[0]
        db.close()
        self.assertEqual(generated, 5)

    def test_commercial_receivables_page_matches_current_workflow(self):
        import server.db as db_module
        expired_id, _, _ = self._contract('HT-AR-EXPIRED', start='2022-01-01', end='2022-12-31')
        current_id, _, _ = self._contract('HT-AR-CURRENT', start='2022-01-01', end='2026-12-31')

        status, page = http_get('/commercial_receivables?today=2026-06-15&advance_days=30', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('href="/auto_billing"', page)
        self.assertIn('金额确认', page)
        self.assertIn('应收金额', page)
        self.assertIn('请逐项核对金额', page)
        self.assertNotIn('HT-AR-EXPIRED', page)
        self.assertNotIn('2022-01-01', page)
        self.assertIn(f'{current_id}:rent:2026-06-15:2026-07-14', page)
        self.assertIn(f'{current_id}:property:2026-06-15:2026-07-14', page)

        status, _, loc = http_post('/commercial_receivables/confirm', {
            'today': '2026-06-15',
            'advance_days': '30',
            'item_keys': f'{current_id}:rent:2026-06-15:2026-07-14',
            f'service_start__{current_id}:rent:2026-06-15:2026-07-14': '2026-06-15',
            f'service_end__{current_id}:rent:2026-06-15:2026-07-14': '2026-07-14',
            f'due_date__{current_id}:rent:2026-06-15:2026-07-14': '2026-06-30',
            f'amount__{current_id}:rent:2026-06-15:2026-07-14': '4321.00',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        current_count = db.execute("SELECT COUNT(*) FROM bills WHERE source='merchant_contract' AND source_ref=?", (str(current_id),)).fetchone()[0]
        expired_count = db.execute("SELECT COUNT(*) FROM bills WHERE source='merchant_contract' AND source_ref=?", (str(expired_id),)).fetchone()[0]
        row = db.execute("SELECT amount,service_start,due_date FROM bills WHERE source='merchant_contract' AND source_ref=?", (str(current_id),)).fetchone()
        db.close()
        self.assertEqual(current_count, 1)
        self.assertEqual(expired_count, 0)
        self.assertEqual(row['amount'], 4321.0)
        self.assertEqual(row['service_start'], '2026-06-15')
        self.assertEqual(row['due_date'], '2026-06-30')

    def test_supplement_attachment_recognition_draft_and_confirm_affects_split_billing(self):
        import server.db as db_module
        cid, owner_id, space_id = self._contract('HT-AM-100', rent=3000, prop=5)
        payload = b"%PDF-1.4\nSupplement agreement effective date 2026-01-16 rent unit price 20 property rate 6 rent cycle monthly\n%%EOF"
        status, _, loc = http_post_multipart(f'/merchant_contracts/{cid}/attachments', {
            'attachment_type': '补充协议',
        }, {'file': ('amend.pdf', 'application/pdf', payload)}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        aid = db.execute("SELECT id FROM contract_attachments WHERE contract_id=? AND attachment_type='补充协议'", (cid,)).fetchone()['id']
        db.close()

        status, _, loc = http_post(f'/merchant_contracts/{cid}/attachments/{aid}/recognize', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        draft = db.execute("SELECT * FROM contract_amendment_drafts WHERE contract_id=? AND attachment_id=?", (cid, aid)).fetchone()
        self.assertIsNotNone(draft)
        self.assertEqual(draft['effective_date'], '2026-01-16')
        self.assertAlmostEqual(float(draft['rent_unit_price'] or 0), 20.0)
        self.assertAlmostEqual(float(draft['property_rate'] or 0), 6.0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM contract_amendments WHERE contract_id=?", (cid,)).fetchone()[0], 0)
        db.close()

        status, _, loc = http_post(f'/merchant_contracts/{cid}/amendments/{draft["id"]}/confirm', {
            'effective_date': '2026-01-16', 'rent_unit_price': '20', 'property_rate': '6', 'rent_cycle': 'monthly', 'property_cycle': 'monthly', 'notes': '测试补充协议',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM contract_amendments WHERE contract_id=?", (cid,)).fetchone()[0], 1)
        db.close()

        status, _, loc = http_post('/commercial_receivables/confirm', {
            'today': '2026-01-01', 'advance_days': '30',
            'item_keys': [f'{cid}:rent:2026-01-01:2026-01-31', f'{cid}:property:2026-01-01:2026-01-31'],
            'confirm': '1',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = db_module.get_db()
        rows = db.execute("SELECT amount FROM bills WHERE source='merchant_contract' AND source_ref=? ORDER BY amount DESC", (str(cid),)).fetchall()
        db.close()
        self.assertEqual([r['amount'] for r in rows], [2483.9, 551.6])
