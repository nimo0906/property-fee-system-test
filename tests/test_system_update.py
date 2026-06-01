#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the semi-automatic desktop update workflow."""

import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


class TestSystemUpdateCore(unittest.TestCase):
    def test_check_update_selects_platform_asset_and_compares_versions(self):
        from server.system_update import SystemUpdateService

        manifest = {
            'version': '2.0.3',
            'notes': '修复收费和导入问题',
            'assets': {
                'mac': {'url': 'https://example.test/mac.zip', 'sha256': 'm'},
                'windows': {'url': 'https://example.test/win.zip', 'sha256': 'w'},
            },
        }
        result = SystemUpdateService(current_version='2.0.1', platform_key='windows').check_manifest(manifest)

        self.assertTrue(result['update_available'])
        self.assertEqual(result['latest_version'], '2.0.3')
        self.assertEqual(result['asset_url'], 'https://example.test/win.zip')
        self.assertEqual(result['asset_sha256'], 'w')
        self.assertIn('修复收费', result['notes'])

    def test_prepare_downloaded_update_verifies_hash_extracts_payload_and_writes_helper(self):
        from server.system_update import SystemUpdateService

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_payload = root / 'payload' / 'PropertyFeeSystem'
            source_payload.mkdir(parents=True)
            (source_payload / 'PropertyFeeSystem.exe').write_text('exe', encoding='utf-8')
            package = root / 'update.zip'
            with zipfile.ZipFile(package, 'w') as zf:
                zf.write(source_payload / 'PropertyFeeSystem.exe', 'PropertyFeeSystem/PropertyFeeSystem.exe')
            digest = hashlib.sha256(package.read_bytes()).hexdigest()

            app_root = root / 'installed' / 'PropertyFeeSystem'
            app_root.mkdir(parents=True)
            (app_root / 'old.txt').write_text('old', encoding='utf-8')
            service = SystemUpdateService(
                current_version='2.0.1', platform_key='windows', data_dir=root / 'data',
                app_root=app_root, process_id=12345,
            )
            result = service.prepare_package(package, '2.0.3', digest)

            self.assertEqual(result['version'], '2.0.3')
            self.assertTrue(Path(result['payload_path']).joinpath('PropertyFeeSystem.exe').exists())
            helper = Path(result['helper_path'])
            self.assertTrue(helper.exists())
            helper_text = helper.read_text(encoding='utf-8')
            self.assertIn('PropertyFeeSystem.exe', helper_text)
            self.assertIn('12345', helper_text)
            self.assertIn(str(app_root), helper_text)

    def test_prepare_package_rejects_zip_path_traversal(self):
        from server.system_update import SystemUpdateService, UpdateError

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = root / 'bad.zip'
            with zipfile.ZipFile(package, 'w') as zf:
                zf.writestr('../evil.txt', 'bad')
            digest = hashlib.sha256(package.read_bytes()).hexdigest()
            service = SystemUpdateService(
                current_version='2.0.1', platform_key='mac', data_dir=root / 'data', app_root=root / 'App.app'
            )

            with self.assertRaisesRegex(UpdateError, '不安全'):
                service.prepare_package(package, '2.0.3', digest)


if __name__ == '__main__':
    unittest.main()
