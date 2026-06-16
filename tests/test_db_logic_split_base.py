#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for database-dependent business logic.

These tests use a real SQLite database (in-memory or temp file).
"""

import unittest, os, tempfile, time

# Ensure project root is on path
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Redirect DB before importing server modules
_db_path = os.path.join(tempfile.gettempdir(), f'test_property_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups')

from server.db import (
    get_db, db_init, get_period,
    calc_elevator_fee, calc_bill_late_fee,
    is_period_closed, get_fee_type_rate,
    update_overdue_bills, BACKUP_DIR,
)


class DBLogicTestBase(unittest.TestCase):
    """Tests that require a populated test database."""

    @classmethod
    def setUpClass(cls):
        db_init()
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        if os.path.exists(_db_path):
            os.remove(_db_path)
        # clean WAL/SHM files
        for ext in ('-wal', '-shm'):
            p = _db_path + ext
            if os.path.exists(p):
                os.remove(p)

    def setUp(self):
        # Start each test with a clean slate by deleting test data
        self.db.execute("DELETE FROM payments")
        self.db.execute("DELETE FROM invoices")
        self.db.execute("DELETE FROM invoice_requests")
        self.db.execute("DELETE FROM bills")
        self.db.execute("DELETE FROM auto_billing_runs")
        self.db.execute("DELETE FROM rooms")
        self.db.execute("DELETE FROM owners")
        self.db.execute("DELETE FROM meter_readings")
        self.db.execute("DELETE FROM closing_records")
        self.db.commit()
