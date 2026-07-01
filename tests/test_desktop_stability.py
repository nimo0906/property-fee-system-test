#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop launcher stability tests."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_app
from desktop_runtime import build_window_model
from desktop_service_guard import (
    build_health_url,
    find_existing_service,
    read_service_state,
    write_service_state,
)


class TestDesktopStability(unittest.TestCase):
    def test_window_model_warns_not_to_close_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = build_window_model(
                'http://127.0.0.1:5001',
                Path(tmp),
                Path(tmp) / 'database' / 'property.db',
                Path(tmp) / 'backups',
            )
        self.assertIn('不要关闭', model['hint'])
        self.assertIn('重新打开系统', [x['label'] for x in model['actions']])


    def test_launcher_window_is_tall_enough_for_windows_scaling(self):
        self.assertEqual(desktop_app.WINDOW_GEOMETRY, '620x460')
        source = Path('desktop_app.py').read_text(encoding='utf-8')
        self.assertIn('root.minsize(620, 440)', source)
        self.assertIn('root.resizable(True, True)', source)

    def test_service_state_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = write_service_state(Path(tmp), 5001, 'http://127.0.0.1:5001')
            self.assertTrue(state_path.exists())
            state = read_service_state(Path(tmp))
        self.assertEqual(state['port'], 5001)
        self.assertEqual(state['url'], 'http://127.0.0.1:5001')
        self.assertEqual(state['pid'], os.getpid())

    def test_existing_service_is_reused_only_when_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_service_state(Path(tmp), 5001, 'http://127.0.0.1:5001')
            with mock.patch('desktop_service_guard.is_service_healthy', return_value=True):
                healthy = find_existing_service(Path(tmp))
            with mock.patch('desktop_service_guard.is_service_healthy', return_value=False):
                stale = find_existing_service(Path(tmp))
        self.assertEqual(healthy['url'], 'http://127.0.0.1:5001')
        self.assertIsNone(stale)

    def test_build_health_url_preserves_host_and_port(self):
        self.assertEqual(build_health_url('http://127.0.0.1:5001/rooms'), 'http://127.0.0.1:5001/health')
        self.assertEqual(build_health_url('http://127.0.0.1:5001'), 'http://127.0.0.1:5001/health')

    def test_health_route_is_before_login_gate(self):
        with mock.patch.object(desktop_app, 'prepare_runtime', return_value=(Path('/tmp/app'), Path('/tmp/app/database/property.db'), Path('/tmp/app/backups'))):
            # Static source check protects the no-login health endpoint from route-order regressions.
            source = Path('server/router_get.py').read_text(encoding='utf-8')
        self.assertLess(source.index("if p == '/health'"), source.index("if p not in ('/login'"))


if __name__ == '__main__':
    unittest.main()
