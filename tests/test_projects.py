#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for multi-project readiness boundary."""

import os
import tempfile
import time
import unittest

_db_path = os.path.join(tempfile.gettempdir(), f'test_projects_{int(time.time())}_{os.getpid()}.db')
os.environ['PM_DB_PATH'] = _db_path

import server.db as db_module
db_module.DB_PATH = _db_path
db_module.BACKUP_DIR = os.path.join(os.path.dirname(_db_path), 'backups')

from server.db import db_init, get_db


class TestProjectReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_init()

    @classmethod
    def tearDownClass(cls):
        for suffix in ('', '-wal', '-shm'):
            path = _db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def setUp(self):
        self.db = get_db()

    def tearDown(self):
        self.db.close()

    def test_db_init_creates_default_project_and_project_columns(self):
        tables = {r['name'] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertIn('projects', tables)
        default_project = self.db.execute("SELECT code,name,is_active FROM projects WHERE code='default'").fetchone()
        self.assertEqual(default_project['name'], '默认项目')
        self.assertEqual(default_project['is_active'], 1)
        for table in ('owners', 'rooms', 'fee_types', 'bills', 'payments', 'invoices', 'invoice_requests', 'notification_events'):
            cols = {r['name'] for r in self.db.execute(f'PRAGMA table_info({table})').fetchall()}
            self.assertIn('project_id', cols, table)

    def test_project_service_lists_default_project(self):
        from server.projects import ProjectService

        result = ProjectService().list_projects()
        default_project = ProjectService().default_project()

        self.assertEqual(result['items'][0]['code'], 'default')
        self.assertEqual(default_project['name'], '默认项目')
        self.assertEqual(default_project['is_active'], 1)


if __name__ == '__main__':
    unittest.main()
