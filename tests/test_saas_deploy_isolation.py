import unittest
from pathlib import Path

from server.saas_deploy import validate_deployment_assets


class TestSaasDeployIsolation(unittest.TestCase):
    def setUp(self):
        self.root = Path.cwd()

    def test_compose_mounts_separate_customer_system_backup_and_log_volumes(self):
        compose = (self.root / 'docker-compose.yml').read_text(encoding='utf-8')
        self.assertIn('property_saas_customer_files:', compose)
        self.assertIn('property_saas_system_files:', compose)
        self.assertIn('property_saas_backups:', compose)
        self.assertIn('property_saas_logs:', compose)
        self.assertIn('/var/lib/property-saas/tenants', compose)
        self.assertIn('/var/lib/property-saas/system', compose)
        self.assertIn('/var/backups/property-saas', compose)
        self.assertIn('/var/log/property-saas', compose)

    def test_env_example_declares_isolated_storage_roots_without_real_secret(self):
        env = (self.root / '.env.example').read_text(encoding='utf-8')
        for key in [
            'SAAS_CUSTOMER_FILES_DIR=/var/lib/property-saas/tenants',
            'SAAS_SYSTEM_FILES_DIR=/var/lib/property-saas/system',
            'SAAS_BACKUP_DIR=/var/backups/property-saas',
            'SAAS_LOG_DIR=/var/log/property-saas',
        ]:
            self.assertIn(key, env)
        self.assertNotIn('sk-', env)

    def test_env_security_validator_rejects_weak_secret_placeholders(self):
        from server.saas_deploy import validate_env_security

        weak = validate_env_security({
            'POSTGRES_PASSWORD': 'replace-with-random-password',
            'APP_SECRET_KEY': 'replace-with-32-byte-random-secret',
        })
        self.assertFalse(weak['ok'])
        self.assertIn('POSTGRES_PASSWORD', weak['weak'])
        self.assertIn('APP_SECRET_KEY', weak['weak'])

        strong = validate_env_security({
            'POSTGRES_PASSWORD': 'P@ssw0rd-2026-tenant-safe-9c5f1e7b',
            'APP_SECRET_KEY': '0123456789abcdef0123456789abcdef',
        })
        self.assertTrue(strong['ok'], strong)
        self.assertEqual(strong['weak'], [])

    def test_env_example_uses_safe_instructional_secret_format(self):
        env = (self.root / '.env.example').read_text(encoding='utf-8')
        self.assertNotIn('replace-with-random-password', env)
        self.assertNotIn('replace-with-32-byte-random-secret', env)
        self.assertIn('generate-postgres-password-with-openssl-rand-hex-32', env)
        self.assertIn('generate-app-secret-with-openssl-rand-hex-32', env)

    def test_backup_script_keeps_database_and_files_in_separate_subdirectories(self):
        script = (self.root / 'scripts/saas_backup.sh').read_text(encoding='utf-8')
        self.assertIn('db/', script)
        self.assertIn('tenant-files/', script)
        self.assertIn('system-files/', script)
        self.assertIn('metadata.json', script)
        self.assertIn('SAAS_CUSTOMER_FILES_DIR', script)
        self.assertIn('SAAS_SYSTEM_FILES_DIR', script)

    def test_backup_metadata_records_checksums_and_restore_can_verify(self):
        backup = (self.root / 'scripts/saas_backup.sh').read_text(encoding='utf-8')
        restore = (self.root / 'scripts/saas_restore.sh').read_text(encoding='utf-8')
        self.assertIn('sha256sum', backup)
        self.assertIn('checksums', backup)
        self.assertIn('--verify-metadata', restore)
        self.assertIn('sha256sum -c', restore)
        self.assertIn('invalid backup metadata', restore)

    def test_restore_verify_metadata_detects_tampered_backup_file(self):
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            backup_dir = Path(td) / 'backup'
            (backup_dir / 'db').mkdir(parents=True)
            db = backup_dir / 'db/property_saas.sql'
            db.write_text('select 1;', encoding='utf-8')
            manifest = backup_dir / 'checksums.sha256'
            metadata = backup_dir / 'metadata.json'
            subprocess.run(['sha256sum', 'db/property_saas.sql'], cwd=backup_dir, text=True, stdout=manifest.open('w'), check=True)
            metadata.write_text('{"kind":"property-saas-backup","checksums":"checksums.sha256"}', encoding='utf-8')
            ok = subprocess.run(['bash', 'scripts/saas_restore.sh', '--verify-metadata', str(backup_dir)], cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            self.assertEqual(ok.returncode, 0, ok.stdout)
            db.write_text('select 2;', encoding='utf-8')
            bad = subprocess.run(['bash', 'scripts/saas_restore.sh', '--verify-metadata', str(backup_dir)], cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('FAILED', bad.stdout)


    def test_restore_verify_metadata_rejects_invalid_metadata_kind(self):
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            backup_dir = Path(td) / 'backup'
            (backup_dir / 'db').mkdir(parents=True)
            db = backup_dir / 'db/property_saas.sql'
            db.write_text('select 1;', encoding='utf-8')
            manifest = backup_dir / 'checksums.sha256'
            subprocess.run(['sha256sum', 'db/property_saas.sql'], cwd=backup_dir, text=True, stdout=manifest.open('w'), check=True)
            (backup_dir / 'metadata.json').write_text('{"kind":"not-property-backup","checksums":"checksums.sha256"}', encoding='utf-8')
            result = subprocess.run(['bash', 'scripts/saas_restore.sh', '--verify-metadata', str(backup_dir)], cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid backup metadata', result.stdout)
    def test_restore_script_requires_explicit_scope(self):
        script = (self.root / 'scripts/saas_restore.sh').read_text(encoding='utf-8')
        self.assertIn('--database', script)
        self.assertIn('--tenant-files', script)
        self.assertIn('--system-files', script)
        self.assertIn('Refusing implicit full restore', script)

    def test_preflight_script_exists_and_reports_deployment_readiness(self):
        import subprocess
        import sys

        script = self.root / 'scripts/saas_preflight_check.py'
        self.assertTrue(script.exists(), 'missing SaaS preflight check script')
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('PASS saas deploy assets', result.stdout)
        self.assertIn('PASS saas storage isolation contract', result.stdout)
        self.assertIn('PASS saas app port localhost binding', result.stdout)
        self.assertIn('PASS saas compose restart policy', result.stdout)
        self.assertIn('PASS saas postgres healthcheck', result.stdout)
        self.assertIn('PASS saas env example security', result.stdout)

    def test_preflight_script_reports_nginx_https_warning(self):
        import subprocess
        import sys

        script = self.root / 'scripts/saas_preflight_check.py'
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('WARN nginx http only', result.stdout)

    def test_restore_script_rejects_archive_path_traversal(self):
        import os
        import subprocess
        import sys
        import tempfile
        import tarfile

        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / 'evil.tar.gz'
            payload = Path(td) / 'payload.txt'
            payload.write_text('evil', encoding='utf-8')
            with tarfile.open(archive, 'w:gz') as tf:
                tf.add(payload, arcname='../escape.txt')
            result = subprocess.run(
                ['bash', 'scripts/saas_restore.sh', '--tenant-files', str(archive)],
                cwd=self.root,
                env={**os.environ, 'SAAS_CUSTOMER_FILES_DIR': str(Path(td) / 'tenant-target')},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unsafe archive member', result.stdout)


    def test_logrotate_config_keeps_saas_logs_bounded(self):
        logrotate = self.root / 'deploy/logrotate/property-saas'
        self.assertTrue(logrotate.exists(), 'missing SaaS logrotate config')
        text = logrotate.read_text(encoding='utf-8')
        self.assertIn('/var/log/property-saas/*.log', text)
        self.assertIn('rotate 14', text)
        self.assertIn('compress', text)
        self.assertIn('missingok', text)
        self.assertIn('copytruncate', text)



    def test_compose_declares_restart_policy_for_services(self):
        compose = (self.root / 'docker-compose.yml').read_text(encoding='utf-8')
        self.assertIn('restart: unless-stopped', compose)
        self.assertIn('restart: on-failure', compose)


    def test_validator_requires_postgres_healthcheck(self):
        from server.saas_deploy import inspect_compose_healthcheck

        compose = (self.root / 'docker-compose.yml').read_text(encoding='utf-8')
        health = inspect_compose_healthcheck(compose)
        self.assertTrue(health['postgres_has_healthcheck'], health)
        self.assertIn('pg_isready', health['postgres_test'])
        missing = inspect_compose_healthcheck("services:\n  postgres:\n    image: postgres:16-alpine\n")
        self.assertFalse(missing['postgres_has_healthcheck'], missing)

    def test_validator_requires_app_port_bound_to_localhost_only(self):
        from server.saas_deploy import inspect_compose_port_binding

        compose = (self.root / 'docker-compose.yml').read_text(encoding='utf-8')
        binding = inspect_compose_port_binding(compose)
        self.assertTrue(binding['localhost_only'], binding)
        self.assertIn('127.0.0.1:8000:8000', binding['ports'])
        unsafe = inspect_compose_port_binding("ports:\n  - \"8000:8000\"\n")
        self.assertFalse(unsafe['localhost_only'], unsafe)

    def test_validator_checks_deployment_isolation_contract(self):
        result = validate_deployment_assets(self.root)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['isolation']['customer_files'], '/var/lib/property-saas/tenants')
        self.assertEqual(result['isolation']['system_files'], '/var/lib/property-saas/system')
        self.assertEqual(result['isolation']['backups'], '/var/backups/property-saas')
        self.assertEqual(result['isolation']['logs'], '/var/log/property-saas')
        self.assertTrue(result['env_example_secure'], result)
        self.assertEqual(result['restart_policy'], {'postgres': True, 'app': True})
        self.assertTrue(result['healthcheck']['postgres_has_healthcheck'], result)


if __name__ == '__main__':
    unittest.main()

class TestSaasSystemdIsolation(unittest.TestCase):
    def test_systemd_service_declares_storage_and_log_roots(self):
        service = Path('deploy/systemd/property-saas.service').read_text(encoding='utf-8')
        self.assertIn('SAAS_CUSTOMER_FILES_DIR=/var/lib/property-saas/tenants', service)
        self.assertIn('SAAS_SYSTEM_FILES_DIR=/var/lib/property-saas/system', service)
        self.assertIn('SAAS_BACKUP_DIR=/var/backups/property-saas', service)
        self.assertIn('SAAS_LOG_DIR=/var/log/property-saas', service)
