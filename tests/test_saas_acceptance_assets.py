import subprocess
import sys
import unittest
from pathlib import Path

from server.saas_deploy import validate_deployment_assets


class TestSaasAcceptanceAssets(unittest.TestCase):
    def test_acceptance_script_exists_and_passes(self):
        script = Path('scripts/saas_acceptance_check.py')
        self.assertTrue(script.exists(), 'missing SaaS acceptance script')
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=Path.cwd(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('PASS saas acceptance workflow', result.stdout)
        self.assertIn('PASS saas acceptance isolation', result.stdout)
        self.assertIn('PASS saas acceptance account boundary', result.stdout)
        self.assertIn('PASS saas acceptance storage boundary', result.stdout)
        self.assertIn('PASS saas acceptance import upload', result.stdout)

    def test_deploy_validator_includes_acceptance_script(self):
        result = validate_deployment_assets(Path.cwd())
        self.assertTrue(result['ok'], result)
        self.assertIn('scripts/saas_acceptance_check.py', result['files'])
        self.assertIn('scripts/saas_preflight_check.py', result['files'])

    def test_saas_plan_document_matches_current_cloud_backoffice_scope(self):
        doc = Path('docs/saas-cloud-backoffice-plan.md').read_text(encoding='utf-8')
        required = [
            'FastAPI',
            'SQLAlchemy',
            'Alembic',
            '登录、租户、角色权限',
            '收费对象、收费项目、出账、审核、收款',
            '导入预览、审核、确认',
            '收据、导出、对账报表',
            '备份记录、恢复演练、审计日志',
            'scripts/saas_acceptance_check.py',
            'scripts/saas_preflight_check.py',
        ]
        for text in required:
            self.assertIn(text, doc)
        self.assertNotIn('真实 PostgreSQL 运行时 ORM', doc)
        self.assertNotIn('真实 FastAPI 页面和登录 session', doc)


if __name__ == '__main__':
    unittest.main()
