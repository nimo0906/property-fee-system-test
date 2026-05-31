#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop launcher safety tests."""

import os
import tempfile
import unittest
from pathlib import Path

import desktop_app


class TestDesktopApp(unittest.TestCase):
    def test_prepare_runtime_uses_data_dir_and_creates_required_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir, db_path, backup_dir = desktop_app.prepare_runtime(tmp)
            self.assertEqual(data_dir, Path(tmp))
            self.assertTrue(data_dir.exists())
            self.assertTrue(backup_dir.exists())
            self.assertEqual(db_path, Path(tmp) / 'property.db')
            self.assertEqual(os.environ['PM_DB_PATH'], str(db_path))
            self.assertEqual(os.environ['PM_BACKUP_DIR'], str(backup_dir))

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


if __name__ == '__main__':
    unittest.main()

class TestDesktopDeliveryDiagnostics(unittest.TestCase):
    def test_get_runtime_status_reports_paths_and_missing_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir, db_path, backup_dir = desktop_app.prepare_runtime(tmp)
            status = desktop_app.get_runtime_status(data_dir=data_dir, dependencies=['module_that_does_not_exist_for_desktop_test'])
            self.assertEqual(status['data_dir'], str(data_dir))
            self.assertEqual(status['db_path'], str(db_path))
            self.assertEqual(status['backup_dir'], str(backup_dir))
            self.assertTrue(status['db_exists'])
            self.assertIn('module_that_does_not_exist_for_desktop_test', status['missing_dependencies'])
            self.assertIn('python_version', status)

    def test_format_runtime_status_is_user_readable_for_windows_delivery(self):
        status = {
            'app_title': desktop_app.APP_TITLE,
            'python_version': '3.11.0',
            'executable': r'C:\\Python311\\python.exe',
            'data_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystem',
            'db_path': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystem\\property.db',
            'backup_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystem\\backups',
            'db_exists': True,
            'backup_dir_exists': True,
            'missing_dependencies': ['openpyxl'],
        }
        text = desktop_app.format_runtime_status(status)
        self.assertIn('物业管理收费系统', text)
        self.assertIn('Data directory', text)
        self.assertIn('Missing dependencies: openpyxl', text)
        self.assertIn('install_windows_dependencies.bat', text)


    def test_desktop_default_port_prefers_documented_5001(self):
        port = desktop_app.choose_desktop_port(start=54321)
        self.assertEqual(port, 54321)

    def test_desktop_port_falls_back_when_5001_is_busy(self):
        sock = __import__('socket').socket(__import__('socket').AF_INET, __import__('socket').SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', 54321))
            port = desktop_app.choose_desktop_port(start=54321)
            self.assertNotEqual(port, 54321)
            self.assertGreaterEqual(port, 54322)
        finally:
            sock.close()

    def test_find_free_port_reports_checked_range_when_unavailable(self):
        sockets = []
        try:
            for port in range(53100, 53102):
                sock = __import__('socket').socket(__import__('socket').AF_INET, __import__('socket').SOCK_STREAM)
                sock.bind(('127.0.0.1', port))
                sockets.append(sock)
            with self.assertRaises(RuntimeError) as ctx:
                desktop_app.find_free_port(53100, attempts=2)
            self.assertIn('53100-53101', str(ctx.exception))
        finally:
            for sock in sockets:
                sock.close()


class TestDesktopPackaging(unittest.TestCase):
    def test_resource_dir_defaults_to_source_directory(self):
        resource_dir = desktop_app.get_resource_dir()
        self.assertEqual(resource_dir, Path(desktop_app.__file__).resolve().parent)
        self.assertTrue((resource_dir / 'server').exists())

    def test_resource_dir_uses_pyinstaller_meipass(self):
        old = getattr(__import__('sys'), '_MEIPASS', None)
        had = hasattr(__import__('sys'), '_MEIPASS')
        try:
            setattr(__import__('sys'), '_MEIPASS', '/tmp/property-fee-bundle')
            self.assertEqual(desktop_app.get_resource_dir(), Path('/tmp/property-fee-bundle'))
        finally:
            if had:
                setattr(__import__('sys'), '_MEIPASS', old)
            else:
                delattr(__import__('sys'), '_MEIPASS')

    def test_desktop_launcher_exports_resource_dir_for_server_static_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop_app.prepare_runtime(tmp)
            self.assertEqual(os.environ['PM_RESOURCE_DIR'], str(desktop_app.get_resource_dir()))

    def test_windows_build_files_exist_and_include_required_assets(self):
        spec = Path('property_fee_system.spec')
        script = Path('build_windows_exe.bat')
        self.assertTrue(spec.exists())
        self.assertTrue(script.exists())
        spec_text = spec.read_text(encoding='utf-8')
        self.assertIn('desktop_app.py', spec_text)
        self.assertIn('server', spec_text)
        self.assertIn('templates', spec_text)
        self.assertIn('static', spec_text)
        script_text = script.read_text(encoding='utf-8')
        self.assertIn('pyinstaller', script_text.lower())
        self.assertIn('property_fee_system.spec', script_text)

class TestDesktopDeliveryDocs(unittest.TestCase):
    def test_delivery_docs_exist_and_cover_first_run_checklist(self):
        quick = Path('用户快速开始.md')
        checklist = Path('交付验收清单.md')
        self.assertTrue(quick.exists())
        self.assertTrue(checklist.exists())
        quick_text = quick.read_text(encoding='utf-8')
        for text in ['PropertyFeeSystem.exe', 'admin', 'admin123', '数据导入', '生成账单', '收费登记', '对账报表']:
            self.assertIn(text, quick_text)
        checklist_text = checklist.read_text(encoding='utf-8')
        for text in ['Windows', '首次启动', '登录', '导入模板', '备份', '诊断']:
            self.assertIn(text, checklist_text)

    def test_packaged_distribution_includes_user_facing_docs(self):
        spec_text = Path('property_fee_system.spec').read_text(encoding='utf-8')
        self.assertIn('用户快速开始.md', spec_text)
        self.assertIn('交付验收清单.md', spec_text)
        build_text = Path('build_windows_exe.bat').read_text(encoding='utf-8')
        self.assertIn('用户快速开始.md', build_text)
        self.assertIn('交付验收清单.md', build_text)

class TestDesktopWindowExperience(unittest.TestCase):
    def test_desktop_window_model_exposes_user_support_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = desktop_app.build_window_model(
                url='http://127.0.0.1:5000',
                data_dir=Path(tmp),
                db_path=Path(tmp) / 'property.db',
                backup_dir=Path(tmp) / 'backups',
            )
            labels = [a['label'] for a in model['actions']]
            self.assertIn('打开系统', labels)
            self.assertIn('打开数据目录', labels)
            self.assertIn('查看诊断信息', labels)
            self.assertIn('打开错误日志', labels)
            self.assertIn('退出', labels)
            self.assertIn('数据保存在本机', model['hint'])
            self.assertEqual(model['startup_log'], str(Path(tmp) / 'startup_error.log'))


    def test_window_model_shows_service_url_and_restart_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = desktop_app.build_window_model(
                url='http://127.0.0.1:5001',
                data_dir=Path(tmp),
                db_path=Path(tmp) / 'property.db',
                backup_dir=Path(tmp) / 'backups',
            )
            labels = [a['label'] for a in model['actions']]
            self.assertEqual(model['url'], 'http://127.0.0.1:5001')
            self.assertIn('重新启动服务', labels)
            self.assertIn('当前访问地址', model['service_status'])
            self.assertIn('http://127.0.0.1:5001', model['service_status'])

    def test_write_runtime_status_log_creates_support_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = desktop_app.get_runtime_status(data_dir=tmp, dependencies=[])
            log_path = desktop_app.write_runtime_status_log(status)
            self.assertTrue(log_path.exists())
            text = log_path.read_text(encoding='utf-8')
            self.assertIn('Data directory', text)
            self.assertIn('Database', text)
            self.assertIn('Missing dependencies: none', text)

class TestDesktopRuntimeModule(unittest.TestCase):
    def test_runtime_helpers_are_available_from_desktop_runtime_module(self):
        import desktop_runtime
        for name in [
            'get_resource_dir', 'prepare_runtime', 'get_runtime_status',
            'format_runtime_status', 'write_runtime_status_log',
            'build_window_model', 'choose_desktop_port', 'find_free_port', 'write_startup_error',
        ]:
            self.assertTrue(hasattr(desktop_runtime, name), name)

    def test_desktop_app_reexports_runtime_helpers_for_existing_callers(self):
        import desktop_runtime
        self.assertIs(desktop_app.prepare_runtime, desktop_runtime.prepare_runtime)
        self.assertIs(desktop_app.build_window_model, desktop_runtime.build_window_model)
        self.assertIs(desktop_app.write_runtime_status_log, desktop_runtime.write_runtime_status_log)
        self.assertIs(desktop_app.choose_desktop_port, desktop_runtime.choose_desktop_port)

class TestMacDesktopDeployment(unittest.TestCase):
    def test_macos_build_files_exist_and_include_required_assets(self):
        spec = Path('property_fee_system_macos.spec')
        script = Path('build_macos_app.command')
        self.assertTrue(spec.exists())
        self.assertTrue(script.exists())
        spec_text = spec.read_text(encoding='utf-8')
        self.assertIn('desktop_app.py', spec_text)
        self.assertIn('BUNDLE(', spec_text)
        self.assertIn('物业管理收费系统.app', spec_text)
        for asset in ['server', 'templates', 'static', 'property.db', '用户快速开始.md', '交付验收清单.md', '使用说明.md']:
            self.assertIn(asset, spec_text)
        script_text = script.read_text(encoding='utf-8')
        self.assertIn('property_fee_system_macos.spec', script_text)
        self.assertIn('PyInstaller', script_text)

    def test_delivery_docs_cover_macos_app_build(self):
        usage = Path('使用说明.md').read_text(encoding='utf-8')
        checklist = Path('交付验收清单.md').read_text(encoding='utf-8')
        self.assertIn('build_macos_app.command', usage)
        self.assertIn('物业管理收费系统.app', usage)
        self.assertIn('macOS 启动验收', checklist)
        self.assertIn('物业管理收费系统.app', checklist)
