#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split tests from tests/test_desktop_app.py chunk 01."""

from tests.test_desktop_app_split_base import *


class TestDesktopApp01(DesktopAppTestBase):
    def test_prepare_runtime_uses_data_dir_and_creates_required_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir, db_path, backup_dir = desktop_app.prepare_runtime(tmp)
            self.assertEqual(data_dir, Path(tmp))
            self.assertTrue(data_dir.exists())
            self.assertTrue(backup_dir.exists())
            self.assertTrue((Path(tmp) / 'database').exists())
            self.assertTrue((Path(tmp) / 'imports').exists())
            self.assertTrue((Path(tmp) / 'exports').exists())
            self.assertTrue((Path(tmp) / 'updates').exists())
            self.assertTrue((Path(tmp) / 'logs').exists())
            self.assertEqual(db_path, Path(tmp) / 'database' / 'property.db')
            self.assertEqual(os.environ['PM_DB_PATH'], str(db_path))
            self.assertEqual(os.environ['PM_BACKUP_DIR'], str(backup_dir))
            self.assertEqual(os.environ['PM_IMPORT_CACHE_DIR'], str(Path(tmp) / 'imports'))


    def test_prepare_runtime_copies_legacy_data_then_deletes_legacy_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / 'PropertyFeeSystem'
            legacy_backups = legacy / 'backups'
            legacy_backups.mkdir(parents=True)
            legacy_db = legacy / 'property.db'
            legacy_db.write_bytes(b'legacy-db')
            (legacy_backups / 'backup_legacy.db').write_bytes(b'legacy-backup')

            new_dir = base / 'PropertyFeeSystemData'
            data_dir, db_path, backup_dir = desktop_app.prepare_runtime(new_dir)

            self.assertEqual(data_dir, new_dir)
            self.assertEqual(db_path.read_bytes(), b'legacy-db')
            self.assertEqual((backup_dir / 'backup_legacy.db').read_bytes(), b'legacy-backup')
            self.assertFalse(legacy.exists())
            log_text = (new_dir / 'logs' / 'legacy_migration.log').read_text(encoding='utf-8')
            self.assertIn('deleted legacy directory', log_text)


    def test_prepare_runtime_deletes_legacy_dir_without_overwriting_new_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / 'PropertyFeeSystem'
            legacy.mkdir(parents=True)
            legacy_db = legacy / 'property.db'
            legacy_db.write_bytes(b'changed-legacy-db')
            new_dir = base / 'PropertyFeeSystemData'
            new_db = new_dir / 'database' / 'property.db'
            new_db.parent.mkdir(parents=True)
            new_db.write_bytes(b'new-db')

            desktop_app.prepare_runtime(new_dir)

            self.assertEqual(new_db.read_bytes(), b'new-db')
            self.assertFalse(legacy.exists())


    def test_prepare_runtime_keeps_legacy_dir_when_copy_verification_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / 'PropertyFeeSystem'
            legacy.mkdir(parents=True)
            new_db = base / 'PropertyFeeSystemData' / 'database' / 'property.db'
            new_db.parent.mkdir(parents=True)
            new_db.write_bytes(b'new-db')
            legacy_db = legacy / 'property.db'
            legacy_db.mkdir()

            desktop_app.prepare_runtime(base / 'PropertyFeeSystemData')

            self.assertTrue(legacy.exists())


    def test_write_startup_error_creates_readable_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                raise RuntimeError('desktop startup failed for test')
            except RuntimeError as exc:
                log_path = desktop_app.write_startup_error(exc, Path(tmp))
            self.assertTrue(log_path.exists())
            text = log_path.read_text(encoding='utf-8')
            self.assertIn('desktop startup failed for test', text)
            self.assertIn('Traceback', text)


    def test_create_server_uses_configured_host_for_windows_server_mode(self):
        with mock.patch.dict(os.environ, {'PM_HOST': '0.0.0.0'}, clear=False):
            with mock.patch('desktop_app.http.server.ThreadingHTTPServer') as server_cls:
                with mock.patch('server.db_init'), mock.patch('server.backups.ensure_startup_backups'):
                    desktop_app.create_server(5001)
        self.assertEqual(server_cls.call_args.args[0], ('0.0.0.0', 5001))


