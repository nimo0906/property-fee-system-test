#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 31."""

from tests.integration_base import *


class TestIntegration31(IntegrationTestBase):
    def test_backup_routes_reject_path_traversal_names(self):
        import server.db as db_module
        outside = os.path.join(os.path.dirname(db_module.BACKUP_DIR), 'outside_backup_escape.db')
        with open(outside, 'wb') as f:
            f.write(b'not a valid backup')
        try:
            traversal_names = [
                '../outside_backup_escape.db',
                '..%2Foutside_backup_escape.db',
            ]
            for traversal_name in traversal_names:
                for action in ['preview', 'restore', 'delete']:
                    status, body = http_get(f'/backups/{traversal_name}/{action}', self.cookie, TEST_PORT)
                    self.assertNotEqual(status, 200, f'{traversal_name} {action}')
                    self.assertNotIn('outside_backup_escape.db', body)

            for traversal_name in traversal_names:
                status, body, loc = http_post(f'/backups/{traversal_name}/delete', {}, self.cookie, TEST_PORT)
                self.assertTrue(os.path.exists(outside))
                self.assertNotEqual(status, 200)

                status, body, loc = http_post(f'/backups/{traversal_name}/restore', {}, self.cookie, TEST_PORT)
                self.assertTrue(os.path.exists(outside))
                self.assertNotEqual(status, 200)
        finally:
            if os.path.exists(outside):
                os.remove(outside)


    def test_backup_restore_confirm_page_shows_backup_data_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('备份摘要业主', '13900000000')").lastrowid
        room_id = None
        for idx in range(1, 9):
            cur = db.execute("""
                INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
                VALUES('BACKUPSUMMARY', 'A座', ?, 9, '居民', 88, ?)
            """, (f'90{idx}', owner_id))
            room_id = room_id or cur.lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2029-01', 168.8, '2029-01-28', 'paid', 'BS-001')
        """, (room_id, owner_id)).lastrowid
        db.execute("""
            INSERT INTO payments(bill_id, amount_paid, payment_method, operator)
            VALUES(?, 168.8, 'cash', '备份摘要测试员')
        """, (bill_id,))
        db.commit()
        db.close()
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, html = http_get(f'/backups/{name}/restore', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('备份数据摘要', html)
        self.assertIn('房间数', html)
        self.assertIn('业主数', html)
        self.assertIn('账单数', html)
        self.assertIn('缴费记录数', html)
        self.assertIn('账单金额合计', html)
        self.assertIn('缴费金额合计', html)
        self.assertIn('BACKUPSUMMARY', html)
        self.assertIn('2029-01', html)
        self.assertRegex(html, r'账单金额合计</td><td>\d+\.80')
        self.assertRegex(html, r'缴费金额合计</td><td>\d+\.80')


    def test_backup_restore_confirm_page_explains_risk_and_auto_backup(self):
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        import server.db as db_module
        names = sorted([n for n in os.listdir(db_module.BACKUP_DIR) if n.startswith('backup_')], reverse=True)
        self.assertTrue(names)
        name = names[0]

        status, html = http_get(f'/backups/{name}/restore', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('恢复备份确认', html)
        self.assertIn(name, html)
        self.assertIn('当前数据会先自动备份', html)
        self.assertIn(f'action="/backups/{name}/restore"', html)
        self.assertIn('输入“恢复”', html)
        self.assertIn('name="confirm_text"', html)
        self.assertIn('确认恢复', html)


    def test_backup_restore_post_shows_result_page_with_current_summary(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('恢复结果业主', '13700000000')").lastrowid
        room_id = None
        for idx in range(1, 9):
            cur = db.execute("""
                INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
                VALUES('RESTORERESULT', 'A座', ?, 10, '居民', 66, ?)
            """, (f'10{idx:02d}', owner_id))
            room_id = room_id or cur.lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2029-02', 125.4, '2029-02-28', 'unpaid', 'BR-001')
        """, (room_id, owner_id))
        db.commit()
        db.close()
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, html, loc = http_post(f'/backups/{name}/restore', {'confirm_text': '恢复'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('恢复完成', html)
        self.assertIn(name, html)
        self.assertIn('恢复前自动备份', html)
        self.assertIn('auto_before_restore_', html)
        self.assertIn('当前数据库摘要', html)
        self.assertIn('RESTORERESULT', html)
        self.assertIn('2029-02', html)
        self.assertIn('去首页', html)
        self.assertIn('查看房间', html)
        self.assertIn('查看账单', html)
        self.assertIn('返回备份', html)


    def test_backup_flow(self):
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        _, bbody = http_get('/backups', self.cookie, TEST_PORT)
        self.assertIn('backup_', bbody)
        self.assertIn('最近一次备份', bbody)
        self.assertIn('备份目录', bbody)


    def test_import_upload_works_without_stdlib_cgi_module(self):
        cgi_module = sys.modules.pop('cgi', None)
        block_cgi = mock.patch.dict('sys.modules', {'cgi': None})
        boundary = '----PropertyNoCgiBoundary'
        csv_data = '房号,姓名,电话\nB座940,NoCgi业主,13900009940\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="no-cgi.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
            f'{csv_data}\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        try:
            with block_cgi:
                conn = http.client.HTTPConnection(BASE_URL, TEST_PORT)
                conn.request('POST', '/import/upload', body, {
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                    'Content-Length': str(len(body)),
                    'Cookie': self.cookie,
                })
                resp = conn.getresponse()
                preview_html = resp.read().decode('utf-8')
                conn.close()
        finally:
            if cgi_module is not None:
                sys.modules['cgi'] = cgi_module

        self.assertEqual(resp.status, 200)
        self.assertIn('数据核对与修正', preview_html)
        self.assertIn('NoCgi业主', preview_html)


    def test_import_preview_prioritizes_mapped_review_table_without_writing(self):
        
        from server.db import get_db
        db = get_db(); before_rooms = db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]; db.close()
        boundary = '----PropertyImportMappedReviewBoundary'
        csv_data = '楼栋,单元/座,房屋类别,铺位号,客户名称,联系电话,建筑面积,合同开始日期,合同结束日期,物业费单价,缴费周期,业态\n商场,1F,商业,A-101,映射核对商户,13910000001,88.5,2026-01-01,2026-12-31,4.8,季付,餐饮\n'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="data_type"\r\n\r\nrooms\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="mode"\r\n\r\npreview\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="mapped-review.csv"\r\n'
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
        html = resp.read().decode('utf-8')
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn('数据核对与修正', html)
        self.assertIn('来自：单元/座', html)
        self.assertIn('来自：房屋类别', html)
        self.assertIn('来自：铺位号', html)
        self.assertIn('来自：客户名称', html)
        self.assertIn('来自：建筑面积', html)
        self.assertIn('value="1F"', html)
        self.assertIn('value="商业"', html)
        self.assertIn('value="餐饮"', html)
        self.assertIn('映射核对商户', html)
        self.assertIn('确认导入并生成结果', html)
        self.assertIn('高级识别信息', html)
        self.assertLess(html.find('数据核对与修正'), html.find('高级识别信息'))
        db = get_db(); after_rooms = db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]; db.close()
        self.assertEqual(after_rooms, before_rooms)
