#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 05."""

from tests.integration_base import *


class TestIntegration05(IntegrationTestBase):
    def test_merchant_contract_edit_updates_existing_space_master_data(self):
        from server.commercial_spaces import create_commercial_space
        from server.contract_billing import create_merchant_contract
        from server.db import get_db

        space_id = create_commercial_space({
            'space_no': 'EDIT-SP-001',
            'shop_name': '原始店铺',
            'merchant_name': '原始商户',
            'business_type': '餐饮',
            'floor': '2',
            'area': '88',
            'water_rate_type': '非居民',
            'status': 'active',
        })
        db = get_db()
        owner_id = create_owner(db, '合同编辑空间业主', '13900006666')
        db.close()
        create_merchant_contract({
            'commercial_space_id': space_id,
            'owner_id': owner_id,
            'contract_no': 'HT-EDIT-SP-001',
            'merchant_name': '原始商户',
            'shop_name': '原始店铺',
            'rent_amount': 5000,
            'rent_cycle': 'monthly',
            'property_rate': 5,
            'property_cycle': 'monthly',
            'deposit_amount': 10000,
            'contract_area': 88,
            'building_area': 88,
            'start_date': '2040-01-01',
            'end_date': '2040-12-31',
        })
        db = get_db()
        contract_id = db.execute("SELECT id FROM merchant_contracts WHERE contract_no='HT-EDIT-SP-001'").fetchone()['id']
        db.close()

        status, _, _ = http_post(f'/merchant_contracts/{contract_id}/edit', {
            'commercial_space_id': str(space_id),
            'owner_id': str(owner_id),
            'space_no': 'EDIT-SP-001',
            'shop_name': '更新后店铺',
            'merchant_name': '更新后商户',
            'business_type': '零售',
            'floor': '3',
            'area': '99.5',
            'building_area': '100.0',
            'water_rate_type': '特行',
            'space_notes': '空间备注更新',
            'contract_no': 'HT-EDIT-SP-001',
            'rent_amount': '6000',
            'rent_cycle': 'quarterly',
            'property_rate': '6',
            'property_cycle': 'monthly',
            'deposit_amount': '12000',
            'start_date': '2040-01-01',
            'end_date': '2040-12-31',
            'status': 'active',
            'notes': '合同备注更新',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        db = get_db()
        space = db.execute("SELECT * FROM commercial_spaces WHERE id=?", (space_id,)).fetchone()
        contract = db.execute("SELECT * FROM merchant_contracts WHERE id=?", (contract_id,)).fetchone()
        db.close()
        self.assertEqual(space['space_no'], 'EDIT-SP-001')
        self.assertEqual(space['shop_name'], '更新后店铺')
        self.assertEqual(space['merchant_name'], '更新后商户')
        self.assertEqual(space['business_type'], '零售')
        self.assertEqual(int(space['floor']), 3)
        self.assertAlmostEqual(float(space['area']), 99.5)
        self.assertEqual(space['water_rate_type'], '特行')
        self.assertIn('空间备注更新', space['notes'])
        self.assertEqual(contract['merchant_name'], '更新后商户')
        self.assertEqual(contract['shop_name'], '更新后店铺')
        self.assertAlmostEqual(float(contract['contract_area']), 99.5)
        self.assertAlmostEqual(float(contract['building_area']), 100.0)
        self.assertAlmostEqual(float(contract['rent_amount']), 6000.0 * 99.5)
        self.assertEqual(contract['rent_cycle'], 'quarterly')
        self.assertAlmostEqual(float(contract['property_rate']), 6.0)
        self.assertAlmostEqual(float(contract['deposit_amount']), 12000.0 * 99.5)
        self.assertIn('合同备注更新', contract['notes'])

    def test_commercial_space_contract_bills_visible_in_finance_pages(self):
        status, _, _ = http_post('/commercial_spaces/create', {
            'space_no': 'INT-SP-001',
            'shop_name': '集成商铺店',
            'merchant_name': '集成商铺商户',
            'business_type': '餐饮',
            'floor': '1',
            'area': '100',
            'water_rate_type': '非居民',
            'status': 'active',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        from server.db import get_db
        db = get_db()
        space_id = db.execute("SELECT id FROM commercial_spaces WHERE space_no='INT-SP-001'").fetchone()['id']
        db.close()

        status, _, _ = http_post('/merchant_contracts/create', {
            'commercial_space_id': str(space_id),
            'contract_no': 'HT-INT-SP-001',
            'merchant_name': '集成商铺商户',
            'rent_amount': '6000',
            'rent_cycle': 'monthly',
            'property_rate': '6',
            'property_cycle': 'monthly',
            'deposit_amount': '0',
            'start_date': '2041-01-01',
            'end_date': '2041-12-31',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = get_db()
        contract_id = db.execute("SELECT id FROM merchant_contracts WHERE contract_no='HT-INT-SP-001'").fetchone()['id']
        db.close()
        status, _, _ = http_post(f'/merchant_contracts/{contract_id}/billing/confirm', {'service_start': '2041-01-01'}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        status, bills = http_get('/bills?period=2041-01&keyword=INT-SP-001', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商场-INT-SP-001', bills)
        self.assertIn('集成商铺商户', bills)

        db = get_db()
        bill_id = db.execute("SELECT id FROM bills WHERE commercial_space_id=? AND source='merchant_contract' ORDER BY amount DESC LIMIT 1", (space_id,)).fetchone()['id']
        db.close()
        status, detail = http_get(f'/bills/{bill_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商场-INT-SP-001', detail)
        self.assertIn('集成商铺商户', detail)

        status, pay_page = http_get(f'/bills/{bill_id}/pay', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商场-INT-SP-001', pay_page)
        status, result_html, _ = http_post(f'/bills/{bill_id}/pay', {
            'amount_paid': '6000',
            'payment_method': 'transfer',
            'operator': '财务',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款成功', result_html)
        self.assertIn('打印收据', result_html)

        status, payments = http_get('/payments?keyword=INT-SP-001', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商场-INT-SP-001', payments)
        self.assertIn('集成商铺商户', payments)

        db = get_db()
        payment_id = db.execute("SELECT id FROM payments WHERE bill_id=? ORDER BY id DESC LIMIT 1", (bill_id,)).fetchone()['id']
        db.close()
        status, receipt_html, _ = http_post('/payments/receipts', {
            'payment_ids': str(payment_id),
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('收款收据', receipt_html)
        self.assertIn('商场-INT-SP-001', receipt_html)
        self.assertIn('集成商铺商户', receipt_html)
        self.assertIn('6000.00', receipt_html)

        status, reports = http_get('/reports?period=2041-01&building=%E5%95%86%E5%9C%BA', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('商场', reports)
        self.assertIn('集成商铺商户', reports)

        status, csv_data = http_get('/bills/export?period=2041-01&building=%E5%95%86%E5%9C%BA', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('INT-SP-001', csv_data)
        self.assertIn('集成商铺商户', csv_data)


    def test_merchant_contract_edit_renew_deactivate_and_bill_view_flow(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '合同生命周期商户', '13900007777')
        room_id = create_room(db, building='商场', unit='商场', room_number='MC-201', category='商户', area=80, owner_id=owner_id)
        db.execute("UPDATE rooms SET shop_name=?, custom_rate=? WHERE id=?", ('合同生命周期商户', 8, room_id))
        db.commit(); db.close()

        status, _, _ = http_post('/merchant_contracts/create', {
            'room_id': str(room_id),
            'owner_id': str(owner_id),
            'contract_no': 'HT-LIFE-001',
            'merchant_name': '合同生命周期商户',
            'rent_amount': '8000',
            'rent_cycle': 'monthly',
            'property_rate': '8',
            'property_cycle': 'monthly',
            'deposit_amount': '16000',
            'start_date': '2037-01-01',
            'end_date': '2037-12-31',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        db = get_db()
        contract_id = db.execute("SELECT id FROM merchant_contracts WHERE contract_no='HT-LIFE-001'").fetchone()['id']
        db.close()

        http_post(f'/merchant_contracts/{contract_id}/billing/confirm', {'service_start': '2037-01-01'}, self.cookie, TEST_PORT)

        status, contracts = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn(f'/merchant_contracts/{contract_id}">详情</a>', contracts)
        self.assertIn(f'/merchant_contracts/{contract_id}/edit', contracts)
        self.assertNotIn(f'/merchant_contracts/{contract_id}/renew', contracts)
        self.assertNotIn(f'/merchant_contracts/{contract_id}/bills', contracts)
        self.assertNotIn(f'/merchant_contracts/{contract_id}/deactivate', contracts)

        status, detail_actions = http_get(f'/merchant_contracts/{contract_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        for href in [
            f'/merchant_contracts/{contract_id}/renew',
            f'/merchant_contracts/{contract_id}/bills',
            f'/merchant_contracts/{contract_id}/deactivate',
        ]:
            self.assertIn(href, detail_actions)

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('GET', f'/merchant_contracts/{contract_id}/edit', headers={
            'Cookie': self.cookie,
            'Referer': f'http://127.0.0.1:{TEST_PORT}/merchant_contracts?keyword=contract',
        })
        resp = conn.getresponse()
        edit_page = resp.read().decode('utf-8')
        conn.close()
        status = resp.status
        self.assertEqual(status, 200)
        self.assertIn('已有账单', edit_page)
        self.assertIn('name="rent_cycle"', edit_page)
        self.assertIn('商户编号 *', edit_page)
        self.assertIn('href="/merchant_contracts?keyword=contract"', edit_page)
        self.assertIn('返回', edit_page)
        self.assertNotIn('空间编号 *', edit_page)

        status, _, loc = http_post(f'/merchant_contracts/{contract_id}/edit', {
            'room_id': str(room_id),
            'owner_id': str(owner_id),
            'contract_no': 'HT-LIFE-001',
            'merchant_name': '合同编辑后商户',
            'rent_amount': '9000',
            'rent_cycle': 'quarterly',
            'property_rate': '8.5',
            'property_cycle': 'monthly',
            'deposit_amount': '16000',
            'start_date': '2037-01-01',
            'end_date': '2037-12-31',
            'status': 'active',
            'notes': '编辑测试',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/merchant_contracts', loc)

        status, bill_page = http_get(f'/merchant_contracts/{contract_id}/bills', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('合同已生成账单', bill_page)
        self.assertIn('合同租金', bill_page)
        self.assertIn('2037-01-01 至 2037-01-31', bill_page)

        status, renew_page = http_get(f'/merchant_contracts/{contract_id}/renew', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('合同续签', renew_page)
        status, _, _ = http_post_multipart(f'/merchant_contracts/{contract_id}/renew', {
            'contract_no': 'HT-LIFE-001-R1',
            'start_date': '2038-01-01',
            'end_date': '2038-12-31',
        }, {'file': ('renew-contract.pdf', 'application/pdf', b'%PDF-1.4 renew')}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        status, _, loc = http_post_multipart(
            f'/merchant_contracts/{contract_id}/deactivate',
            {'reason': '退租'},
            {'file': ('checkout.pdf', 'application/pdf', b'%PDF-1.4 checkout')},
            self.cookie,
            TEST_PORT,
        )
        self.assertEqual(status, 302)
        self.assertIn('/merchant_contracts', loc)

        db = get_db()
        status, contracts_after_deactivate = http_get('/merchant_contracts', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('停用', contracts_after_deactivate)
        self.assertNotIn('>inactive<', contracts_after_deactivate)

        old_contract = db.execute("SELECT merchant_name,rent_amount,status FROM merchant_contracts WHERE id=?", (contract_id,)).fetchone()
        renewed = db.execute("SELECT id,start_date,end_date,status FROM merchant_contracts WHERE contract_no='HT-LIFE-001-R1'").fetchone()
        bill_count = db.execute("SELECT COUNT(*) FROM bills WHERE source='merchant_contract' AND source_ref=?", (str(contract_id),)).fetchone()[0]
        old_attachments = db.execute("SELECT attachment_type,original_name FROM contract_attachments WHERE contract_id=?", (contract_id,)).fetchall()
        renewed_attachments = db.execute("SELECT attachment_type,original_name FROM contract_attachments WHERE contract_id=?", (renewed['id'],)).fetchall()
        db.close()
        self.assertEqual(old_contract['merchant_name'], '合同编辑后商户')
        self.assertEqual(float(old_contract['rent_amount']), 9000.0)
        self.assertEqual(old_contract['status'], 'inactive')
        self.assertIsNotNone(renewed)
        self.assertEqual(renewed['start_date'], '2038-01-01')
        self.assertEqual(renewed['status'], 'active')
        self.assertEqual(bill_count, 3)
        self.assertIn(('退租协议', 'checkout.pdf'), [(r['attachment_type'], r['original_name']) for r in old_attachments])
        self.assertIn(('续签合同', 'renew-contract.pdf'), [(r['attachment_type'], r['original_name']) for r in renewed_attachments])

        status, _, loc = http_get_with_location(f'/merchant_contracts/{contract_id}/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/merchant_contracts', loc)

        status, detail = http_get(f'/merchant_contracts/{contract_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('合同详情', detail)
        self.assertIn('合同变更记录', detail)
        self.assertIn('已生成账单', detail)
        self.assertIn('编辑商户合同', detail)
        self.assertIn('停用商户合同', detail)
        self.assertIn('合同续签', detail)
        self.assertIn('租金单价', detail)
        self.assertIn('8000', detail)
        self.assertIn('9000', detail)
