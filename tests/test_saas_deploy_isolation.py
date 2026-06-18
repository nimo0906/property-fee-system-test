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

    def test_validator_checks_deployment_isolation_contract(self):
        result = validate_deployment_assets(self.root)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['isolation']['customer_files'], '/var/lib/property-saas/tenants')
        self.assertEqual(result['isolation']['system_files'], '/var/lib/property-saas/system')
        self.assertEqual(result['isolation']['backups'], '/var/backups/property-saas')
        self.assertEqual(result['isolation']['logs'], '/var/log/property-saas')
        self.assertTrue(result['env_example_secure'], result)


if __name__ == '__main__':
    unittest.main()

class TestSaasSystemdIsolation(unittest.TestCase):
    def test_systemd_service_declares_storage_and_log_roots(self):
        service = Path('deploy/systemd/property-saas.service').read_text(encoding='utf-8')
        self.assertIn('SAAS_CUSTOMER_FILES_DIR=/var/lib/property-saas/tenants', service)
        self.assertIn('SAAS_SYSTEM_FILES_DIR=/var/lib/property-saas/system', service)
        self.assertIn('SAAS_BACKUP_DIR=/var/backups/property-saas', service)
        self.assertIn('SAAS_LOG_DIR=/var/log/property-saas', service)
