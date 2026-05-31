#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, tempfile, time, unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_db_path = os.path.join(tempfile.gettempdir(), f'test_v1_internal_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path
os.environ['PM_SKIP_STARTUP_BACKUP'] = '1'

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups_v1_internal')

from server.db import db_init, get_db, room_active_in_period, log_audit
from server.shared_expenses import allocate_shared_amount


class TestV1InternalFeatures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db_init()
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        for suffix in ['', '-wal', '-shm']:
            path = _db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def setUp(self):
        for table in ['audit_logs','shared_expense_runs','bill_adjustments','payments','meter_readings','bills','rooms','owners']:
            self.db.execute(f'DELETE FROM {table}')
        self.db.commit()

    def _room(self, room_number, area, start='', end=''):
        return self.db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,contract_start,contract_end) VALUES('T','A',?,1,'居民',?,?,?)",
            (room_number, area, start, end)
        ).lastrowid

    def test_shared_area_allocation_sums_to_total(self):
        self._room('101', 30)
        self._room('102', 70)
        rows = self.db.execute('SELECT * FROM rooms ORDER BY room_number').fetchall()
        allocations = allocate_shared_amount(100, rows, 'area')
        self.assertEqual([a['amount'] for a in allocations], [30.0, 70.0])
        self.assertAlmostEqual(sum(a['amount'] for a in allocations), 100.0)

    def test_shared_household_allocation_rounding_keeps_total(self):
        for i in range(3):
            self._room(f'10{i}', 1)
        rows = self.db.execute('SELECT * FROM rooms ORDER BY room_number').fetchall()
        allocations = allocate_shared_amount(100, rows, 'household')
        self.assertAlmostEqual(sum(a['amount'] for a in allocations), 100.0)
        self.assertEqual(allocations[-1]['amount'], 33.34)

    def test_room_contract_overlap_filter(self):
        active_id = self._room('201', 50, '2026-01-01', '2026-12-31')
        expired_id = self._room('202', 50, '2025-01-01', '2025-12-31')
        future_id = self._room('203', 50, '2026-07-01', '2026-12-31')
        rows = {r['room_number']: r for r in self.db.execute('SELECT * FROM rooms').fetchall()}
        self.assertTrue(room_active_in_period(rows['201'], '2026-05'))
        self.assertFalse(room_active_in_period(rows['202'], '2026-05'))
        self.assertFalse(room_active_in_period(rows['203'], '2026-05'))

    def test_audit_log_records_json_values(self):
        log_audit('bill_amount_update', 'bill', 1, 'admin', 'admin', '127.0.0.1', {'amount': 10}, {'amount': 12}, '测试')
        row = self.db.execute('SELECT * FROM audit_logs WHERE action=?', ('bill_amount_update',)).fetchone()
        self.assertIsNotNone(row)
        self.assertIn('10', row['old_value'])
        self.assertIn('12', row['new_value'])
        self.assertEqual(row['reason'], '测试')


if __name__ == '__main__':
    unittest.main()
