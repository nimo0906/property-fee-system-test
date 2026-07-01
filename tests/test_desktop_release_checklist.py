#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for desktop release acceptance checklist assets."""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDesktopReleaseChecklist(unittest.TestCase):
    def test_desktop_release_checklist_document_exists_for_macos_and_windows(self):
        path = os.path.join(ROOT, 'docs', 'desktop-release-checklist.md')
        self.assertTrue(os.path.exists(path))
        text = open(path, encoding='utf-8').read()
        self.assertIn('macOS', text)
        self.assertIn('Windows', text)
        self.assertIn('build_macos_app.command', text)
        self.assertIn('build_windows_exe.bat', text)

    def test_desktop_release_check_script_reports_required_assets(self):
        script = os.path.join(ROOT, 'scripts', 'desktop_release_check.py')
        result = subprocess.run([sys.executable, script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('macOS build script', result.stdout)
        self.assertIn('Windows build script', result.stdout)
        self.assertIn('PASS', result.stdout)


    def test_windows_server_background_assets_are_packaged(self):
        required_files = [
            'PACK_WINDOWS_RELEASE.bat',
            'CHECK_WINDOWS_ENV.bat',
            'package_windows_release.bat',
            'check_windows_packaging_ready.bat',
            'USER_GUIDE_WINDOWS.txt',
            'start_windows.bat',
            'start_windows_server.bat',
            'diagnose_windows.bat',
            'install_windows_background_task.bat',
            'status_windows_background_task.bat',
            'uninstall_windows_background_task.bat',
            'RESET_TRIAL_DATA.bat',
        ]
        for rel in required_files:
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)

        for rel in required_files:
            data = open(os.path.join(ROOT, rel), 'rb').read()
            self.assertFalse(data.startswith(b'\xef\xbb\xbf'), rel)
            self.assertTrue(all(byte < 128 for byte in data), rel)
            self.assertIn(b'\r\n', data, rel)

        package_script = open(os.path.join(ROOT, 'PACK_WINDOWS_RELEASE.bat'), encoding='ascii').read()
        self.assertIn('PropertyFeeSystem-windows-server', package_script)
        self.assertIn('start_windows_server.bat', package_script)
        self.assertIn('diagnose_windows.bat', package_script)
        self.assertIn('USER_GUIDE_WINDOWS.txt', package_script)
        self.assertIn('install_windows_background_task.bat', package_script)
        self.assertIn('status_windows_background_task.bat', package_script)
        self.assertIn('uninstall_windows_background_task.bat', package_script)
        self.assertIn(r'PropertyFeeSystemData', package_script)
        self.assertIn('non-ascii names:', package_script)

        guide = open(os.path.join(ROOT, 'USER_GUIDE_WINDOWS.txt'), encoding='ascii').read()
        self.assertIn('release\\windows\\PropertyFeeSystem-windows-server.zip', guide)
        self.assertIn(r'D:\PropertyFeeSystemData', guide)
        self.assertIn('http://SERVER_IP:5001', guide)

    def test_windows_source_package_inputs_are_ascii_safe(self):
        checked_files = [
            'PACK_WINDOWS_RELEASE.bat',
            'CHECK_WINDOWS_ENV.bat',
            'package_windows_release.bat',
            'check_windows_packaging_ready.bat',
            'USER_GUIDE_WINDOWS.txt',
            'build_windows_exe.bat',
            'property_fee_system.spec',
        ]
        for rel in checked_files:
            data = open(os.path.join(ROOT, rel), 'rb').read()
            self.assertTrue(all(byte < 128 for byte in data), rel)

        spec = open(os.path.join(ROOT, 'property_fee_system.spec'), encoding='ascii').read()
        self.assertIn("clean_tree('server', 'server')", spec)
        self.assertIn("clean_tree('templates', 'templates')", spec)
        self.assertIn("clean_tree('static', 'static')", spec)
        self.assertNotIn('.md', spec)
        self.assertNotIn('.bat', spec)


    def test_windows_source_packager_uses_ascii_safe_manifest(self):
        script = open(os.path.join(ROOT, 'scripts', 'package_windows_source.py'), encoding='utf-8').read()
        self.assertIn("PACKAGE_PREFIX = 'PropertyFeeSystem-windows-source'", script)
        self.assertIn("'PACK_WINDOWS_RELEASE.bat'", script)
        self.assertIn("'CHECK_WINDOWS_ENV.bat'", script)
        self.assertIn("'USER_GUIDE_WINDOWS.txt'", script)
        self.assertIn("'server'", script)
        self.assertIn("'templates'", script)
        self.assertIn("'static'", script)
        self.assertIn('NON_ASCII_COUNT=0', script)
        self.assertIn('FORBIDDEN_COUNT=0', script)

    def test_runtime_pages_use_local_static_assets(self):
        checked = [
            'templates/base.html',
            'server/auth.py',
            'server/index.py',
            'server/invoices.py',
            'server/reminders.py',
            'server/reports.py',
        ]
        for rel in checked:
            text = open(os.path.join(ROOT, rel), encoding='utf-8').read()
            self.assertNotIn('cdn.jsdelivr.net', text, rel)
            self.assertNotIn('https://cdn', text, rel)

        required_assets = [
            'static/vendor/bootstrap/bootstrap.min.css',
            'static/vendor/bootstrap/bootstrap.bundle.min.js',
            'static/vendor/bootstrap-icons/bootstrap-icons.min.css',
            'static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2',
            'static/vendor/chart/chart.umd.min.js',
        ]
        for rel in required_assets:
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)


if __name__ == '__main__':
    unittest.main()
