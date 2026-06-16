#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 39: import preview batching."""

import re

from tests.integration_base import *


class TestIntegration39(IntegrationTestBase):
    def _upload_large_room_file(self, rows=205):
        boundary = '----PropertyLargeImportBoundary'
        lines = ['楼栋,单元/座,铺位号/房号,房间类型,面积㎡,租户姓名,缴费周期']
        for i in range(1, rows + 1):
            lines.append(f'金莎国际,B座,批量{i:03d},商户,50,批量租户{i:03d},季付')
        csv_data = '\n'.join(lines) + '\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="large-rooms.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')
        conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
        conn.request('POST', '/import/upload', body, {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
            'Cookie': self.cookie,
        })
        resp = conn.getresponse()
        html = resp.read().decode('utf-8', errors='ignore')
        conn.close()
        return resp.status, html

    def test_large_import_preview_batches_first_200_and_can_continue_same_file(self):
        status, html = self._upload_large_room_file(205)
        self.assertEqual(status, 200)
        self.assertIn('批量001', html)
        self.assertIn('批量200', html)
        self.assertNotIn('批量201', html)
        self.assertIn('name="preview_row_count" value="200"', html)
        self.assertIn('当前批次：第 1 - 200 条', html)
        m = re.search(r'name="upload_token" value="([A-Za-z0-9_-]+)"', html)
        self.assertIsNotNone(m)
        token = m.group(1)

        status, next_html, _ = http_post('/import/upload', {
            'mode': 'preview',
            'data_type': 'rooms',
            'filename': 'large-rooms.csv',
            'upload_token': token,
            'import_offset': '200',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('当前批次：第 201 - 205 条', next_html)
        self.assertIn('批量201', next_html)
        self.assertIn('批量205', next_html)
        self.assertNotIn('批量001', next_html)
        self.assertIn('name="preview_row_count" value="5"', next_html)

    def test_import_result_offers_continue_button_for_remaining_rows(self):
        status, html = self._upload_large_room_file(205)
        self.assertEqual(status, 200)
        token = re.search(r'name="upload_token" value="([A-Za-z0-9_-]+)"', html).group(1)
        form = {
            'mode': 'confirm_preview_rows',
            'data_type': 'rooms',
            'filename': 'large-rooms.csv',
            'upload_token': token,
            'import_offset': '0',
            'next_import_offset': '200',
            'preview_total_rows': '205',
            'preview_row_count': '1',
            'row_0_action': '新增',
            'row_0_building': '金莎国际',
            'row_0_unit': 'B座',
            'row_0_room_number': '批量结果001',
            'row_0_floor': '1',
            'row_0_category': '商户',
            'row_0_area': '50',
            'row_0_owner_name': '',
            'row_0_owner_phone': '',
            'row_0_contract_start': '',
            'row_0_contract_end': '',
            'row_0_custom_rate': '',
            'row_0_payment_cycle': '季付',
            'row_0_business_type': '',
            'row_0_shop_name': '',
            'row_0_tenant_name': '批量结果租户001',
            'row_0_notes': '',
        }
        status, result_html, _ = http_post('/import/upload', form, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('继续导入后续数据', result_html)
        self.assertIn('name="import_offset" value="200"', result_html)
        self.assertIn('name="upload_token" value="' + token + '"', result_html)

    def test_import_result_uses_continue_for_other_file_when_current_file_done(self):
        form = {
            'mode': 'confirm_preview_rows',
            'data_type': 'rooms',
            'filename': 'small-rooms.csv',
            'upload_token': 'finished_token',
            'import_offset': '0',
            'next_import_offset': '1',
            'preview_total_rows': '1',
            'preview_row_count': '1',
            'row_0_action': '新增',
            'row_0_building': '金莎国际',
            'row_0_unit': 'B座',
            'row_0_room_number': '批量完成001',
            'row_0_floor': '1',
            'row_0_category': '商户',
            'row_0_area': '50',
            'row_0_owner_name': '',
            'row_0_owner_phone': '',
            'row_0_contract_start': '',
            'row_0_contract_end': '',
            'row_0_custom_rate': '',
            'row_0_payment_cycle': '季付',
            'row_0_business_type': '',
            'row_0_shop_name': '',
            'row_0_tenant_name': '批量完成租户001',
            'row_0_notes': '',
        }
        status, result_html, _ = http_post('/import/upload', form, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertNotIn('继续导入后续数据', result_html)
        self.assertIn('导入其他文件', result_html)
