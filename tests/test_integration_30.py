#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split integration tests chunk 30."""

from tests.integration_base import *


class TestIntegration30(IntegrationTestBase):
    def test_closing_close_confirm_writes_record_after_precheck(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('确认结账业主', '13300000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSECONFIRM', 'A座', '1401', 14, '居民', 50, ?)
        """, (owner_id,)).lastrowid
        db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-04', 95, '2030-04-28', 'paid', 'CCF-PAID')
        """, (room_id, owner_id))
        db.commit()
        db.close()

        status, body, loc = http_post('/closing/close', {'period': '2030-04', 'notes': '确认结账', 'confirm': '1'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('2030-04', loc)
        db = db_module.get_db()
        row = db.execute("SELECT status, paid_count, total_amount FROM closing_records WHERE period='2030-04'").fetchone()
        db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['status'], 'closed')
        self.assertEqual(row['paid_count'], 1)
        self.assertEqual(row['total_amount'], 95)


    def test_closed_period_blocks_batch_pay_batch_edit_and_undo_generated(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('批量锁定业主', '13500000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSEDBATCH', 'A座', '1201', 12, '居民', 80, ?)
        """, (owner_id,)).lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-02', 152, '2030-02-28', 'unpaid', 'CB-001')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO closing_records(period, close_date, status) VALUES('2030-02', datetime('now','localtime'), 'closed')")
        db.commit()
        db.close()

        status, body, loc = http_post('/bills/batch_pay', {
            'confirm': '1', 'bill_ids': str(bill_id), 'payment_method': 'cash', 'operator': 'tester'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-02', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post('/bills/batch_edit/apply', {
            'bill_ids': str(bill_id), 'due_date': '2030-02-20', 'notes': 'closed batch edit'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-02', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post('/bills/undo_generated', {
            'period': '2030-02', 'bill_ids': str(bill_id)
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-02', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        db = db_module.get_db()
        row = db.execute("SELECT amount,due_date,status,(SELECT COUNT(*) FROM payments WHERE bill_id=?) pay_count FROM bills WHERE id=?", (bill_id, bill_id)).fetchone()
        db.close()
        self.assertEqual(row['amount'], 152)
        self.assertEqual(row['due_date'], '2030-02-28')
        self.assertEqual(row['status'], 'unpaid')
        self.assertEqual(row['pay_count'], 0)


    def test_closed_period_blocks_bill_edit_delete_and_payment(self):
        import server.db as db_module
        db = db_module.get_db()
        owner_id = db.execute("INSERT INTO owners(name, phone) VALUES('结账锁定业主', '13600000000')").lastrowid
        room_id = db.execute("""
            INSERT INTO rooms(building, unit, room_number, floor, category, area, owner_id)
            VALUES('CLOSEDLOCK', 'A座', '1101', 11, '居民', 77, ?)
        """, (owner_id,)).lastrowid
        bill_id = db.execute("""
            INSERT INTO bills(room_id, owner_id, fee_type_id, billing_period, amount, due_date, status, bill_number)
            VALUES(?, ?, 1, '2030-01', 146.3, '2030-01-28', 'unpaid', 'CL-001')
        """, (room_id, owner_id)).lastrowid
        db.execute("INSERT INTO closing_records(period, close_date, status) VALUES('2030-01', datetime('now','localtime'), 'closed')")
        db.commit()
        db.close()

        status, body, loc = http_post(f'/bills/{bill_id}/edit', {
            'new_amount': '99', 'due_date': '2030-01-28', 'notes': 'closed edit', 'approved_by': 'tester'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-01', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post(f'/bills/{bill_id}/pay', {
            'amount_paid': '10', 'payment_method': 'cash', 'operator': 'tester'
        }, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-01', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        status, body, loc = http_post(f'/bills/{bill_id}/delete', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)
        self.assertIn('2030-01', loc)
        self.assertIn('%E5%B7%B2%E7%BB%93%E8%B4%A6', loc)

        db = db_module.get_db()
        row = db.execute("SELECT amount, status, (SELECT COUNT(*) FROM payments WHERE bill_id=?) AS pay_count FROM bills WHERE id=?", (bill_id, bill_id)).fetchone()
        db.close()
        self.assertEqual(row['amount'], 146.3)
        self.assertEqual(row['status'], 'unpaid')
        self.assertEqual(row['pay_count'], 0)


    def test_backup_cleanup_preview_keeps_manual_backups_and_requires_confirm(self):
        import server.db as db_module
        os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
        prefix = 'auto_before_payment_'
        for old in os.listdir(db_module.BACKUP_DIR):
            if old.startswith(prefix):
                os.remove(os.path.join(db_module.BACKUP_DIR, old))
        auto_names = []
        for i in range(12):
            name = f'{prefix}_{i:02d}.db'
            fp = os.path.join(db_module.BACKUP_DIR, name)
            with open(fp, 'wb') as f:
                f.write(b'x' * (i + 1))
            os.utime(fp, (1700000000 + i, 1700000000 + i))
            auto_names.append(name)
        manual_name = 'backup_cleanup_preview_manual.db'
        with open(os.path.join(db_module.BACKUP_DIR, manual_name), 'wb') as f:
            f.write(b'manual')

        status, html = http_get('/backups/cleanup?keep=10&type=payment', self.cookie, TEST_PORT)

        self.assertEqual(status, 200)
        self.assertIn('自动备份清理预览', html)
        self.assertIn('默认只清理自动备份', html)
        self.assertIn(auto_names[0], html)
        self.assertIn(auto_names[1], html)
        self.assertNotIn(manual_name, html)
        self.assertIn('确认清理', html)
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[0])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, manual_name)))


    def test_backup_cleanup_post_deletes_only_old_auto_backups(self):
        import server.db as db_module
        os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
        prefix = 'auto_before_import_'
        for old in os.listdir(db_module.BACKUP_DIR):
            if old.startswith(prefix):
                os.remove(os.path.join(db_module.BACKUP_DIR, old))
        auto_names = []
        for i in range(12):
            name = f'{prefix}_{i:02d}.db'
            fp = os.path.join(db_module.BACKUP_DIR, name)
            with open(fp, 'wb') as f:
                f.write(b'x')
            os.utime(fp, (1710000000 + i, 1710000000 + i))
            auto_names.append(name)
        manual_name = 'backup_cleanup_post_manual.db'
        with open(os.path.join(db_module.BACKUP_DIR, manual_name), 'wb') as f:
            f.write(b'manual')

        status, body, loc = http_post('/backups/cleanup', {'keep': '10', 'type': 'import'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertIn('%E5%B7%B2%E6%B8%85%E7%90%86%E8%87%AA%E5%8A%A8%E5%A4%87%E4%BB%BD%202%20%E4%B8%AA', loc)
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[0])))
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[1])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, auto_names[-1])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, manual_name)))


    def test_backup_cleanup_post_deletes_old_startup_and_daily_auto_backups(self):
        import server.db as db_module
        os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
        for prefix in ('auto_startup_', 'auto_daily_'):
            for old in os.listdir(db_module.BACKUP_DIR):
                if old.startswith(prefix):
                    os.remove(os.path.join(db_module.BACKUP_DIR, old))
        startup_names = []
        for i in range(12):
            name = f'auto_startup_{i:02d}.db'
            fp = os.path.join(db_module.BACKUP_DIR, name)
            with open(fp, 'wb') as f:
                f.write(b'x')
            os.utime(fp, (1720000000 + i, 1720000000 + i))
            startup_names.append(name)

        status, body, loc = http_post('/backups/cleanup', {'keep': '10', 'type': 'startup'}, self.cookie, TEST_PORT)

        self.assertEqual(status, 302)
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, startup_names[0])))
        self.assertFalse(os.path.exists(os.path.join(db_module.BACKUP_DIR, startup_names[1])))
        self.assertTrue(os.path.exists(os.path.join(db_module.BACKUP_DIR, startup_names[-1])))


    def test_backup_delete_confirm_page_explains_deleted_backup(self):
        status, body, loc = http_post('/backups/create', {}, self.cookie, TEST_PORT)
        self.assertEqual(status, 302)

        import server.db as db_module
        m = re.search(r'backup_\d{8}_\d{6}_\d+\.db', urllib.parse.unquote(loc))
        self.assertIsNotNone(m)
        name = m.group(0)

        status, html = http_get(f'/backups/{name}/delete', self.cookie, TEST_PORT)
        self.assertEqual(status, 200)
        self.assertIn('删除备份确认', html)
        self.assertIn(name, html)
        self.assertIn('删除后无法从系统内恢复', html)
        self.assertIn(f'action="/backups/{name}/delete"', html)
        self.assertIn('确认删除', html)


