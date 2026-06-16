#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 38: import preview Chinese labels."""

from tests.integration_base import *


class TestIntegration38(IntegrationTestBase):
    def _post_csv_preview(self, csv_data):
        boundary = '----PropertyImportChineseCycleBoundary'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="cycle-preview.csv"\r\n'
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

    def test_import_preview_payment_cycle_uses_chinese_label(self):
        csv_data = (
            '楼栋,单元/座,铺位号/房号,房间类型,面积㎡,租户姓名,缴费周期\n'
            '金莎国际,B座,中文周期3801,商户,66.5,中文周期租户,quarterly\n'
        )
        status, html = self._post_csv_preview(csv_data)
        self.assertEqual(status, 200)
        self.assertIn('数据核对与修正', html)
        self.assertIn('name="row_0_payment_cycle"', html)
        self.assertIn('selected>季付</option>', html)
        self.assertNotIn('value="quarterly" class="form-control', html)

    def test_import_preview_confirm_normalizes_chinese_payment_cycle(self):
        status, _, loc = http_post('/import/upload', {
            'mode': 'confirm_preview_rows',
            'data_type': 'rooms',
            'filename': 'manual-cycle.csv',
            'preview_row_count': '1',
            'row_0_action': '新增',
            'row_0_building': '金莎国际',
            'row_0_unit': 'B座',
            'row_0_room_number': '中文周期3802',
            'row_0_floor': '38',
            'row_0_category': '商户',
            'row_0_area': '66.5',
            'row_0_owner_name': '',
            'row_0_owner_phone': '',
            'row_0_contract_start': '2026-01-01',
            'row_0_contract_end': '2026-12-31',
            'row_0_custom_rate': '5',
            'row_0_payment_cycle': '季付',
            'row_0_business_type': '',
            'row_0_shop_name': '',
            'row_0_tenant_name': '中文周期租户2',
            'row_0_notes': '',
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertEqual(loc, '')
        import server.db as db_module
        db = db_module.get_db()
        row = db.execute("SELECT payment_cycle FROM rooms WHERE room_number='中文周期3802'").fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['payment_cycle'], 'quarterly')
