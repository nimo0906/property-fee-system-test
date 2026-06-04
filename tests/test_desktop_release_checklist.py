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
