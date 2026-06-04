#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop launcher safety tests."""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_app


class TestDesktopApp(unittest.TestCase):
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
            self.assertEqual(status['import_dir'], str(Path(tmp) / 'imports'))
            self.assertEqual(status['export_dir'], str(Path(tmp) / 'exports'))
            self.assertEqual(status['update_dir'], str(Path(tmp) / 'updates'))
            self.assertEqual(status['log_dir'], str(Path(tmp) / 'logs'))
            self.assertTrue(status['db_exists'])
            self.assertIn('module_that_does_not_exist_for_desktop_test', status['missing_dependencies'])
            self.assertIn('python_version', status)

    def test_format_runtime_status_is_user_readable_for_windows_delivery(self):
        status = {
            'app_title': desktop_app.APP_TITLE,
            'python_version': '3.11.0',
            'executable': r'C:\\Python311\\python.exe',
            'data_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystemData',
            'db_path': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystemData\\database\\property.db',
            'backup_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystemData\\backups',
            'import_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystemData\\imports',
            'export_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystemData\\exports',
            'update_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystemData\\updates',
            'log_dir': r'C:\\Users\\Tester\\AppData\\Roaming\\PropertyFeeSystemData\\logs',
            'db_exists': True,
            'backup_dir_exists': True,
            'missing_dependencies': ['openpyxl'],
        }
        text = desktop_app.format_runtime_status(status)
        self.assertIn('物业管理收费系统', text)
        self.assertIn('Data directory', text)
        self.assertIn('Import cache', text)
        self.assertIn('Export directory', text)
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
        server_script = Path('start_windows_server.bat')
        self.assertTrue(spec.exists())
        self.assertTrue(script.exists())
        self.assertTrue(server_script.exists())
        spec_text = spec.read_text(encoding='utf-8')
        self.assertIn('desktop_app.py', spec_text)
        self.assertIn('server', spec_text)
        self.assertIn('templates', spec_text)
        self.assertIn('static', spec_text)
        self.assertIn('Windows客户试用说明.md', spec_text)
        self.assertIn('清空本机试用数据.bat', spec_text)
        self.assertIn('Windows打包操作步骤.md', spec_text)
        self.assertIn('check_windows_packaging_ready.bat', spec_text)
        self.assertIn('Windows用户发送文案.md', spec_text)
        self.assertIn('真实数据试运行保护方案.md', spec_text)
        self.assertIn('真实数据导入前验收清单.md', spec_text)
        self.assertIn('update_manifest.json', spec_text)
        self.assertNotIn("('property.db', '.')", spec_text)
        script_text = script.read_text(encoding='utf-8')
        self.assertIn('pyinstaller', script_text.lower())
        self.assertIn('property_fee_system.spec', script_text)
        self.assertIn('package_windows_release.bat', script_text)
        server_text = server_script.read_text(encoding='utf-8')
        self.assertIn('PM_HOST=0.0.0.0', server_text)
        self.assertIn('PM_PORT=5001', server_text)
        self.assertIn('PM_DB_PATH', server_text)
        self.assertIn('PropertyFeeSystem\\PropertyFeeSystem.exe', server_text)
        self.assertIn('--serve-only', server_text)
        launcher_text = Path('start_windows.bat').read_text(encoding='utf-8')
        self.assertIn('PropertyFeeSystem\\PropertyFeeSystem.exe', launcher_text)

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
        self.assertIn('Windows客户试用说明.md', build_text)
        package_text = Path('package_windows_release.bat').read_text(encoding='utf-8')
        self.assertIn('start_windows_server.bat', package_text)
        ready_text = Path('check_windows_packaging_ready.bat').read_text(encoding='utf-8')
        self.assertIn('start_windows_server.bat', ready_text)

    def test_final_delivery_assets_and_docs_are_ready_for_release_closeout(self):
        final_checklist = Path('正式交付清单.md')
        self.assertTrue(final_checklist.exists())
        final_text = final_checklist.read_text(encoding='utf-8')
        for phrase in ['UI 细节收口', '文档 / 使用说明', 'Windows 打包准备', '正式交付清单', 'P0/P1', 'PropertyFeeSystemData']:
            self.assertIn(phrase, final_text)

        ready = Path('check_windows_packaging_ready.bat').read_text(encoding='utf-8')
        self.assertIn('正式交付清单.md', ready)

        package = Path('package_windows_release.bat').read_text(encoding='utf-8')
        self.assertIn('正式交付清单.md', package)

        for guide_name in ['Windows客户试用说明.md', '用户快速开始.md', '交付验收清单.md']:
            guide_text = Path(guide_name).read_text(encoding='utf-8')
            self.assertNotIn('业主端', guide_text)
            self.assertNotIn('支付订单', guide_text)

    def test_desktop_window_model_has_release_ready_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = desktop_app.build_window_model(
                url='http://127.0.0.1:5001',
                data_dir=Path(tmp),
                db_path=Path(tmp) / 'database' / 'property.db',
                backup_dir=Path(tmp) / 'backups',
            )
            self.assertIn('本地桌面版', model['hint'])
            self.assertIn('PropertyFeeSystemData', model['hint'])
            self.assertIn('127.0.0.1', model['service_status'])

    def test_windows_release_helpers_are_safe_and_simple(self):
        for path in [Path('package_windows_release.bat'), Path('清空本机试用数据.bat'), Path('Windows客户试用说明.md'), Path('Windows打包操作步骤.md'), Path('check_windows_packaging_ready.bat'), Path('明天Windows打包从这里开始.md'), Path('Windows用户发送文案.md'), Path('真实数据试运行保护方案.md'), Path('真实数据导入前验收清单.md')]:
            self.assertTrue(path.exists(), str(path))
        reset = Path('清空本机试用数据.bat').read_text(encoding='utf-8')
        self.assertIn('%APPDATA%\\PropertyFeeSystemData', reset)
        self.assertIn('PropertyFeeSystemDataBackups', reset)
        self.assertIn('xcopy', reset.lower())
        self.assertIn('rmdir /S /Q "%APP_DATA_DIR%"', reset)
        self.assertNotIn('rmdir /S /Q %APPDATA%', reset)
        package = Path('package_windows_release.bat').read_text(encoding='utf-8')
        self.assertIn('Compress-Archive', package)
        self.assertIn('Windows客户试用说明.md', package)
        self.assertIn('清空本机试用数据.bat', package)
        self.assertIn('Windows打包操作步骤.md', package)
        self.assertIn('check_windows_packaging_ready.bat', package)
        self.assertIn('Windows用户发送文案.md', package)
        self.assertIn('真实数据试运行保护方案.md', package)
        self.assertIn('真实数据导入前验收清单.md', package)
        ready = Path('check_windows_packaging_ready.bat').read_text(encoding='utf-8')
        self.assertIn('property_fee_system.spec', ready)
        self.assertIn('package_windows_release.bat', ready)
        self.assertIn('property.db', ready)
        ops = Path('Windows打包操作步骤.md').read_text(encoding='utf-8')
        for phrase in ['check_windows_packaging_ready.bat', 'package_windows_release.bat', '物业管理收费系统-v2.0-windows.zip']:
            self.assertIn(phrase, ops)
        tomorrow = Path('明天Windows打包从这里开始.md').read_text(encoding='utf-8')
        for phrase in ['Code → Download ZIP', 'check_windows_packaging_ready.bat', 'package_windows_release.bat', 'release\\windows\\物业管理收费系统-v2.0-windows.zip']:
            self.assertIn(phrase, tomorrow)
        send_text = Path('Windows用户发送文案.md').read_text(encoding='utf-8')
        for phrase in ['微信短文案', '邮件文案', 'PropertyFeeSystem\\PropertyFeeSystem.exe', '更多信息', '仍要运行']:
            self.assertIn(phrase, send_text)
        real_plan = Path('真实数据试运行保护方案.md').read_text(encoding='utf-8')
        for phrase in ['真实业务数据', '严禁提交', 'property.db', '在线支付接入前']:
            self.assertIn(phrase, real_plan)
        real_checklist = Path('真实数据导入前验收清单.md').read_text(encoding='utf-8')
        for phrase in ['导入前备份', '源数据核对', '账单生成前确认']:
            self.assertIn(phrase, real_checklist)
        guide = Path('Windows客户试用说明.md').read_text(encoding='utf-8')
        for phrase in ['双击', 'PropertyFeeSystem.exe', 'admin123', '仍要运行', '清空本机试用数据.bat']:
            self.assertIn(phrase, guide)


    def test_trial_data_reset_scripts_require_explicit_confirmation(self):
        mac_reset = Path('清空本机试用数据.command').read_text(encoding='utf-8')
        win_reset = Path('清空本机试用数据.bat').read_text(encoding='utf-8')
        for text in [mac_reset, win_reset]:
            self.assertIn('RESET', text)
            self.assertIn('trial', text.lower())
            self.assertIn('real business data', text.lower())

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
            self.assertIn('检查更新', labels)
            self.assertIn('退出', labels)
            self.assertIn('数据保存在本机', model['hint'])
            self.assertEqual(model['startup_log'], str(Path(tmp) / 'logs' / 'startup_error.log'))


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
        for asset in ['server', 'templates', 'static', '用户快速开始.md', '交付验收清单.md', '使用说明.md', 'update_manifest.json']:
            self.assertIn(asset, spec_text)
        self.assertNotIn("('property.db', '.')", spec_text)
        script_text = script.read_text(encoding='utf-8')
        self.assertIn('property_fee_system_macos.spec', script_text)
        self.assertIn('PyInstaller', script_text)


    def test_macos_trial_data_reset_script_is_safe(self):
        script = Path('清空本机试用数据.command')
        self.assertTrue(script.exists())
        text = script.read_text(encoding='utf-8')
        self.assertIn('Application Support/PropertyFeeSystemData', text)
        self.assertIn('PropertyFeeSystemDataBackups', text)
        self.assertIn('cp -R', text)
        self.assertIn('rm -rf "$APP_DATA_DIR"', text)
        self.assertNotIn('rm -rf /', text)
        self.assertNotIn('property.db', Path('property_fee_system_macos.spec').read_text(encoding='utf-8'))


    def test_customer_trial_guide_exists_and_covers_delivery_topics(self):
        guide = Path('客户试用说明.md')
        self.assertTrue(guide.exists())
        text = guide.read_text(encoding='utf-8')
        for phrase in [
            '系统设置', '隐私与安全性', 'admin123',
            '清空本机试用数据.command', 'PropertyFeeSystemDataBackups',
            'Application Support/PropertyFeeSystemData', '反馈'
        ]:
            self.assertIn(phrase, text)

    def test_delivery_docs_cover_macos_app_build(self):
        usage = Path('使用说明.md').read_text(encoding='utf-8')
        checklist = Path('交付验收清单.md').read_text(encoding='utf-8')
        self.assertIn('build_macos_app.command', usage)
        self.assertIn('物业管理收费系统.app', usage)
        self.assertIn('macOS 启动验收', checklist)
        self.assertIn('物业管理收费系统.app', checklist)

class TestGitHubInternalReleaseWorkflow(unittest.TestCase):
    def test_internal_release_workflow_builds_windows_and_macos_assets(self):
        workflow = Path('.github/workflows/internal-desktop-release.yml')
        self.assertTrue(workflow.exists())
        text = workflow.read_text(encoding='utf-8')
        for phrase in [
            'windows-latest', 'macos-latest', 'package_windows_release.bat',
            '物业管理收费系统-v2.0-windows.zip', '物业管理收费系统-v2.0-macos.zip',
            'update_manifest.json', 'internal-latest', 'gh release upload',
        ]:
            self.assertIn(phrase, text)

    def test_windows_packaging_scripts_do_not_pause_in_ci(self):
        for name in ['package_windows_release.bat', 'check_windows_packaging_ready.bat', 'build_windows_exe.bat']:
            text = Path(name).read_text(encoding='utf-8')
            self.assertNotRegex(text.lower(), r'(?m)^\s*pause\s*$')
            self.assertIn('if not defined CI pause'.lower(), text.lower())

    def test_default_update_manifest_points_to_internal_latest_release(self):
        from server.app_version import DEFAULT_UPDATE_MANIFEST_URL
        self.assertIn('/releases/download/internal-latest/update_manifest.json', DEFAULT_UPDATE_MANIFEST_URL)
        manifest = json.loads(Path('update_manifest.json').read_text(encoding='utf-8'))
        self.assertIn('/releases/download/internal-latest/', manifest['assets']['mac']['url'])
        self.assertIn('/releases/download/internal-latest/', manifest['assets']['windows']['url'])
