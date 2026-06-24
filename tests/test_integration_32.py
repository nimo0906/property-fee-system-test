#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 32."""

from tests.integration_base import *


class TestIntegration32(IntegrationTestBase):
    def test_import_preview_manual_mapping_regenerates_review_without_writing(self):
        
        from server.db import get_db
        db = get_db(); before_rooms = db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]; db.close()
        boundary = '----PropertyImportRemapReviewBoundary'
        csv_data = '房号,姓名,备注列,电话\nB座955,自动识别业主,手动映射业主,13900009555\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="remap-review.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
            'X-CSRF-Token': csrf_header_for_cookie(self.cookie),
        })
        resp = conn.getresponse(); html = resp.read().decode('utf-8'); conn.close()
        token = re.search(r'name="upload_token" value="([^"]+)"', html).group(1)

        status, remap_html, _ = http_post('/import/upload', {
            'mode': 'preview',
            'data_type': 'rooms',
            'filename': 'remap-review.csv',
            'upload_token': token,
            'col_room_number': '0',
            'col_owner_name': '2',
            'col_owner_phone': '3',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('手动映射业主', remap_html)
        self.assertIn('来自：备注列', remap_html)
        self.assertNotIn('value="自动识别业主"', remap_html)
        db = get_db(); after_rooms = db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]; db.close()
        self.assertEqual(after_rooms, before_rooms)


    def test_import_preview_confirm_writes_edited_review_values(self):
        boundary = '----PropertyImportEditedConfirmBoundary'
        csv_data = '铺位号,客户名称,联系电话,建筑面积\nE-101,原商户,13900001010,50\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="edited-confirm.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
            'X-CSRF-Token': csrf_header_for_cookie(self.cookie),
        })
        resp = conn.getresponse(); html = resp.read().decode('utf-8'); conn.close()
        self.assertEqual(resp.status, 200)

        status, result_html, _ = http_post('/import/upload', {
            'mode': 'confirm_preview_rows',
            'data_type': 'rooms',
            'filename': 'edited-confirm.csv',
            'preview_row_count': '1',
            'row_0_building': '商场',
            'row_0_unit': '商场',
            'row_0_room_number': 'E-201',
            'row_0_floor': '2',
            'row_0_category': '商业',
            'row_0_area': '66.6',
            'row_0_owner_name': '编辑后商户',
            'row_0_owner_phone': '13900002020',
            'row_0_contract_start': '2026-02-01',
            'row_0_contract_end': '2027-01-31',
            'row_0_custom_rate': '5.5',
            'row_0_payment_cycle': 'monthly',
            'row_0_business_type': '零售',
            'row_0_notes': '预览页修改后确认',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('导入结果', result_html)
        from server.db import get_db
        db = get_db()
        room = db.execute("SELECT r.*,o.name owner_name,o.phone owner_phone FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id WHERE r.room_number='E-201'").fetchone()
        db.close()
        self.assertIsNotNone(room)
        self.assertEqual(room['owner_name'], '编辑后商户')
        self.assertEqual(round(float(room['area']), 1), 66.6)
        self.assertEqual(room['contract_start'], '2026-02-01')
        self.assertEqual(room['unit'], '商场')
        self.assertEqual(room['category'], '商业')
        self.assertEqual(room['business_type'], '零售')


    def test_payment_ledger_preview_confirms_fee_mapping_without_importing_amounts(self):
        boundary = '----PropertyFeeMappingBoundary'
        csv_data = '房间号,用户名称,物业费,电费,广告费\nB座903,收费项目业主,100,20,5\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\npayment_ledger\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="fee-map.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
            'X-CSRF-Token': csrf_header_for_cookie(self.cookie),
        })
        resp = conn.getresponse()
        preview_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('收费标准匹配确认', preview_html)
        self.assertIn('name="fee_map_物业费"', preview_html)
        self.assertIn('物业费(居民)', preview_html)
        token = re.search(r'name="upload_token" value="([^"]+)"', preview_html).group(1)

        status, result_html, _ = http_post('/import/upload', {
            'mode': 'confirm_fee_mapping',
            'data_type': 'payment_ledger',
            'filename': 'fee-map.csv',
            'upload_token': token,
            'fee_map_物业费': 'fee:物业费(居民)',
            'fee_map_电费': 'fee:电费(商业)',
            'fee_map_广告费': 'ignore',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('收费项目匹配确认结果', result_html)
        self.assertIn('物业费(居民)', result_html)
        self.assertIn('电费(商业)', result_html)
        self.assertIn('忽略', result_html)
        self.assertIn('未导入历史金额', result_html)
        self.assertIn('打印核对清单', result_html)
        match = re.search(r'href="(/import/fee_mapping/[^"]+\.csv)"', result_html)
        self.assertIsNotNone(match)
        status, csv_body = http_get(match.group(1), self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('Excel原始列名,系统识别结果,用户确认匹配,正数行数,负数行数,金额合计,说明,金额入账状态', csv_body)
        self.assertIn('物业费,matched_fee,物业费(居民)', csv_body)
        self.assertIn('广告费,unmatched_fee,忽略', csv_body)
        self.assertIn('未导入历史金额', csv_body)


    def test_import_preview_allows_manual_column_mapping(self):
        boundary = '----PropertyImportPreviewBoundary'
        csv_data = '房号,姓名,电话,备注列\nB座902,自动识别业主,13900008888,手动映射业主\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="manual-map.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
            'X-CSRF-Token': csrf_header_for_cookie(self.cookie),
        })
        resp = conn.getresponse()
        preview_html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('数据核对与修正', preview_html)
        self.assertIn('name="col_owner_name"', preview_html)
        token = re.search(r'name="upload_token" value="([^"]+)"', preview_html).group(1)

        status, result_html, _ = http_post('/import/upload', {
            'mode': 'import',
            'data_type': 'rooms',
            'filename': 'manual-map.csv',
            'upload_token': token,
            'col_room_number': '0',
            'col_owner_name': '3',
            'col_owner_phone': '2',
            'col_area': '',
            'col_contract_period': '',
        }, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('导入结果', result_html)
        self.assertNotIn('数据核对与修正', result_html)
        from server.db import get_db
        db = get_db()
        row = db.execute("""
            SELECT r.building, r.room_number, o.name owner_name, o.phone owner_phone
            FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
            WHERE r.building='B座' AND r.room_number='902' LIMIT 1
        """).fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['building'], 'B座')
        self.assertEqual(row['owner_name'], '手动映射业主')
        self.assertEqual(row['owner_phone'], '13900008888')


