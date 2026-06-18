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

    def test_validator_checks_deployment_isolation_contract(self):
        result = validate_deployment_assets(self.root)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['isolation']['customer_files'], '/var/lib/property-saas/tenants')
        self.assertEqual(result['isolation']['system_files'], '/var/lib/property-saas/system')
        self.assertEqual(result['isolation']['backups'], '/var/backups/property-saas')
        self.assertEqual(result['isolation']['logs'], '/var/log/property-saas')


if __name__ == '__main__':
    unittest.main()

class TestSaasSystemdIsolation(unittest.TestCase):
    def test_systemd_service_declares_storage_and_log_roots(self):
        service = Path('deploy/systemd/property-saas.service').read_text(encoding='utf-8')
        self.assertIn('SAAS_CUSTOMER_FILES_DIR=/var/lib/property-saas/tenants', service)
        self.assertIn('SAAS_SYSTEM_FILES_DIR=/var/lib/property-saas/system', service)
        self.assertIn('SAAS_BACKUP_DIR=/var/backups/property-saas', service)
        self.assertIn('SAAS_LOG_DIR=/var/log/property-saas', service)
