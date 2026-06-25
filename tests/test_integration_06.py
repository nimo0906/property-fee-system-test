#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 06."""

from tests.integration_base import *


class TestIntegration06(IntegrationTestBase):
    def test_alert_center_links_contract_risks_to_lifecycle_actions(self):
        from server.contract_billing import create_merchant_contract
        from server.db import get_db
        today = date.today()
        expiring_end = (today + timedelta(days=10)).isoformat()
        expired_end = (today - timedelta(days=1)).isoformat()
        db = get_db()
        owner_id = create_owner(db, '预警处理商户', '13900006666')
        expiring_room = create_room(db, building='商场', unit='商场', room_number='AL-101', category='商户', area=60, owner_id=owner_id)
        expired_room = create_room(db, building='商场', unit='商场', room_number='AL-102', category='商户', area=70, owner_id=owner_id)
        db.close()
        expiring_id = create_merchant_contract({
            'room_id': expiring_room, 'owner_id': owner_id, 'contract_no': 'ALERT-LINK-001',
            'merchant_name': '预警处理商户', 'rent_amount': 6000, 'property_rate': 7,
            'deposit_amount': 12000, 'start_date': today.isoformat(), 'end_date': expiring_end,
        })
        expired_id = create_merchant_contract({
            'room_id': expired_room, 'owner_id': owner_id, 'contract_no': 'ALERT-LINK-002',
            'merchant_name': '过期处理商户', 'rent_amount': 7000, 'property_rate': 8,
            'deposit_amount': 14000, 'start_date': (today - timedelta(days=30)).isoformat(), 'end_date': expired_end,
        })

        status, page = http_get('/alert_center', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn(f'/merchant_contracts/{expiring_id}/renew', page)
        self.assertIn(f'href="/merchant_contracts/{expiring_id}"', page)
        self.assertIn('>查看</a>', page)
        self.assertIn(f'/merchant_contracts/{expiring_id}/edit', page)
        self.assertIn(f'href="/merchant_contracts/{expired_id}"', page)
        self.assertIn(f'/merchant_contracts/{expired_id}/renew', page)
        self.assertIn(f'/merchant_contracts/{expired_id}/deactivate', page)


    def test_merchant_contract_attachment_upload_view_and_download(self):
        from server.contract_billing import create_merchant_contract
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '附件归档商户', '13900003333')
        room_id = create_room(db, building='商场', unit='商场', room_number='AT-101', category='商户', area=50, owner_id=owner_id)
        db.close()
        contract_id = create_merchant_contract({
            'room_id': room_id, 'owner_id': owner_id, 'contract_no': 'ATTACH-001',
            'merchant_name': '附件归档商户', 'rent_amount': 5000, 'property_rate': 6,
            'deposit_amount': 10000, 'start_date': '2039-01-01', 'end_date': '2039-12-31',
        })

        status, _, loc = http_post_multipart(
            f'/merchant_contracts/{contract_id}/attachments',
            {'attachment_type': '合同扫描件'},
            {'file': ('contract scan.pdf', 'application/pdf', b'%PDF-1.4 test contract')},
            self.cookie,
            TEST_PORT,
        )
        self.assertEqual(status, 302)
        self.assertIn(f'/merchant_contracts/{contract_id}', loc)

        db = get_db()
        row = db.execute("SELECT id,original_name,stored_name,file_ext FROM contract_attachments WHERE contract_id=?", (contract_id,)).fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['original_name'], 'contract scan.pdf')
        self.assertEqual(row['file_ext'], '.pdf')

        status, detail = http_get(f'/merchant_contracts/{contract_id}', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('合同附件', detail)
        self.assertIn('单个文件最大 30MB', detail)
        self.assertIn('contract scan.pdf', detail)
        self.assertIn(f'/merchant_contracts/{contract_id}/attachments/{row["id"]}/download', detail)

        status, content = http_get(f'/merchant_contracts/{contract_id}/attachments/{row["id"]}/download', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('%PDF-1.4 test contract', content)

        status, _, loc = http_post_multipart(
            f'/merchant_contracts/{contract_id}/attachments',
            {'attachment_type': '合同扫描件'},
            {'file': ('中文合同扫描件.pdf', 'application/pdf', b'%PDF-1.4 cn contract')},
            self.cookie,
            TEST_PORT,
        )
        self.assertEqual(status, 302)
        db = get_db()
        cn_row = db.execute("SELECT id FROM contract_attachments WHERE contract_id=? AND original_name=?", (contract_id, '中文合同扫描件.pdf')).fetchone()
        db.close()
        self.assertIsNotNone(cn_row)
        status, cn_content = http_get(f'/merchant_contracts/{contract_id}/attachments/{cn_row["id"]}/download', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('%PDF-1.4 cn contract', cn_content)

        large_payload = b'%PDF-1.4 large contract\n' + (b'0' * (11 * 1024 * 1024))
        status, _, loc = http_post_multipart(
            f'/merchant_contracts/{contract_id}/attachments',
            {'attachment_type': '大合同扫描件'},
            {'file': ('large-contract.pdf', 'application/pdf', large_payload)},
            self.cookie,
            TEST_PORT,
        )
        self.assertEqual(status, 302)
        db = get_db()
        large_row = db.execute("SELECT file_size FROM contract_attachments WHERE contract_id=? AND original_name=?", (contract_id, 'large-contract.pdf')).fetchone()
        db.close()
        self.assertIsNotNone(large_row)
        self.assertGreater(large_row['file_size'], 10 * 1024 * 1024)

        status, _, loc = http_post_multipart(
            f'/merchant_contracts/{contract_id}/attachments',
            {'attachment_type': '非法文件'},
            {'file': ('bad.exe', 'application/octet-stream', b'MZ')},
            self.cookie,
            TEST_PORT,
        )
        self.assertEqual(status, 302)
        self.assertIn('文件格式', urllib.parse.unquote(loc))


    def test_merchant_contract_attachment_upload_works_without_stdlib_cgi_module(self):
        from server.contract_billing import create_merchant_contract
        from server.db import get_db

        db = get_db()
        owner_id = create_owner(db, '无CGI附件商户', '13900000613')
        room_id = create_room(db, building='商场', unit='商场', room_number='NCGI-101', category='商户', area=45, owner_id=owner_id)
        db.close()
        contract_id = create_merchant_contract({
            'room_id': room_id, 'owner_id': owner_id, 'contract_no': 'NO-CGI-ATTACH-001',
            'merchant_name': '无CGI附件商户', 'rent_amount': 4500, 'property_rate': 5,
            'deposit_amount': 9000, 'start_date': '2039-01-01', 'end_date': '2039-12-31',
        })

        cgi_module = sys.modules.pop('cgi', None)
        block_cgi = mock.patch.dict('sys.modules', {'cgi': None})
        try:
            with block_cgi:
                status, _, loc = http_post_multipart(
                    f'/merchant_contracts/{contract_id}/attachments',
                    {'attachment_type': '合同扫描件'},
                    {'file': ('no-cgi-contract.pdf', 'application/pdf', b'%PDF-1.4 no cgi contract')},
                    self.cookie,
                    TEST_PORT,
                )
        finally:
            if cgi_module is not None:
                sys.modules['cgi'] = cgi_module

        self.assertEqual(status, 302)
        self.assertIn(f'/merchant_contracts/{contract_id}', loc)
        db = get_db()
        row = db.execute(
            "SELECT original_name,mime_type,file_size FROM contract_attachments WHERE contract_id=? AND original_name=?",
            (contract_id, 'no-cgi-contract.pdf'),
        ).fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['mime_type'], 'application/pdf')
        self.assertGreater(row['file_size'], 0)


    def test_nonresident_and_special_water_fees_apply_by_room_water_rate_not_room_category(self):
        from server.billing_engine import fee_applies_to_room
        room_nonresident = {'category': '居民', 'unit': 'B座', 'water_rate_type': '非居民'}
        room_special = {'category': '居民', 'unit': 'B座', 'water_rate_type': '特行'}
        room_commercial = {'category': '商业', 'unit': '商场', 'water_rate_type': '非居民'}
        self.assertTrue(fee_applies_to_room('水费(非居民)', room_nonresident))
        self.assertFalse(fee_applies_to_room('水费(特行)', room_nonresident))
        self.assertTrue(fee_applies_to_room('水费(特行)', room_special))
        self.assertFalse(fee_applies_to_room('水费(非居民)', room_special))
        self.assertTrue(fee_applies_to_room('水费(非居民)', room_commercial))
        self.assertFalse(fee_applies_to_room('空调费(商业)', {'category': '居民', 'unit': 'B座'}))
        self.assertTrue(fee_applies_to_room('空调费(商业)', {'category': '商业', 'unit': '商场'}))


    def test_commercial_billing_only_lists_mall_unit_rooms(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商业过滤业主', '13900000001')
        create_room(db, building='金莎国际', unit='B座', room_number='1901', category='居民', owner_id=owner_id)
        create_room(db, building='金莎国际', unit='B座', room_number='B-SHOP', category='商户', owner_id=owner_id)
        create_room(db, building='金莎国际', unit='商场', room_number='C101', category='商户', owner_id=owner_id)
        db.close()

        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('<optgroup label="兼容房间 · 商场">', body)
        self.assertIn('金莎国际-商场-C101', body)
        self.assertNotIn('金莎国际-B座-1901', body)
        self.assertNotIn('金莎国际-B座-B-SHOP', body)
        self.assertNotIn('商场商业收费已迁移', body)
        self.assertNotIn('商户合同出账', body)

        status, property_body = http_get('/billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('金莎国际-B座-1901', property_body)
        self.assertIn('金莎国际-B座-B-SHOP', property_body)
        self.assertNotIn('金莎国际-商场-C101', property_body)

    def test_commercial_billing_uses_mall_room_rate_cycle_and_excludes_non_mall_units(self):
        from server.db import get_db
        db = get_db()
        owner_id = create_owner(db, '商场规则业主', '13900008888')
        mall_id = create_room(db, building='金莎国际', unit='商场', room_number='1F-101', category='商户', area=88.5, owner_id=owner_id)
        db.execute("UPDATE rooms SET custom_rate=4.8, payment_cycle='quarterly', shop_name='甲店' WHERE id=?", (mall_id,))
        a_id = create_room(db, building='金莎国际', unit='A座', room_number='A101', category='商户', area=100, owner_id=owner_id)
        b_id = create_room(db, building='金莎国际', unit='B座', room_number='B201', category='居民', area=100, owner_id=owner_id)
        commercial_fee = db.execute("SELECT id FROM fee_types WHERE name='物业费(商户)'").fetchone()['id']
        db.commit(); db.close()

        status, body = http_get('/commercial_billing', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('金莎国际-商场-1F-101 / 甲店', body)
        self.assertNotIn('金莎国际-A座-A101', body)
        self.assertNotIn('金莎国际-B座-B201', body)
        self.assertNotIn('商场商业收费已迁移', body)

        status, body, loc = http_post('/billing/calc', {
            'room_id': str(mall_id),
            'fee_types': str(commercial_fee),
            'period_start': '2033-01-01',
            'period_end': '2033-01-31',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('/bills', loc)
        db = get_db()
        bill = db.execute("SELECT amount,billing_period,due_date FROM bills WHERE room_id=?", (mall_id,)).fetchone()
        a_count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=?", (a_id,)).fetchone()[0]
        b_count = db.execute("SELECT COUNT(*) FROM bills WHERE room_id=?", (b_id,)).fetchone()[0]
        db.close()
        self.assertIsNotNone(bill)
        self.assertEqual(bill['billing_period'], '2033-01')
        self.assertEqual(bill['due_date'], '2033-01-31')
        self.assertAlmostEqual(float(bill['amount']), 424.80)
        self.assertEqual(a_count, 0)
        self.assertEqual(b_count, 0)
