import subprocess
import sys
import unittest
from pathlib import Path


class TestSaasOpsRunbookAssets(unittest.TestCase):
    def test_cloud_ops_runbook_documents_vps_operations(self):
        doc = Path('docs/saas-cloud-ops-runbook.md')
        self.assertTrue(doc.exists(), 'missing SaaS cloud ops runbook')
        text = doc.read_text(encoding='utf-8')
        required = [
            'SaaS 云端商业版运维手册',
            '通用 Linux/VPS',
            'docker compose up -d',
            'deploy/nginx/property-saas.conf',
            'deploy/systemd/property-saas.service',
            'deploy/logrotate/property-saas',
            'scripts/saas_preflight_check.py',
            'scripts/saas_acceptance_check.py',
            'scripts/saas_ops_check.py',
            'scripts/saas_backup.sh',
            'scripts/saas_restore.sh --verify-metadata',
            '管理员重置密码流程',
            '租户管理员只能重置本租户员工账号',
            '平台管理员可跨租户重置账号但必须写入目标租户审计',
            '恢复演练证据',
            '日志轮转安装',
            '客户上传数据与系统自身数据隔离',
        ]
        for item in required:
            self.assertIn(item, text)
        forbidden = ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']
        for item in forbidden:
            self.assertNotIn(item, text)

    def test_ops_check_script_exists_and_reports_operational_readiness(self):
        script = Path('scripts/saas_ops_check.py')
        self.assertTrue(script.exists(), 'missing SaaS ops check script')
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=Path.cwd(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        for text in [
            'PASS saas ops runbook',
            'PASS saas logrotate config',
            'PASS saas password reset procedure',
            'PASS saas restore drill evidence checklist',
            'PASS saas deployment commands',
        ]:
            self.assertIn(text, result.stdout)

    def test_deploy_checklist_links_runbook_and_ops_check(self):
        from fastapi.testclient import TestClient
        from server.saas_app import create_app

        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '运维验收物业', 'project_name': '运维验收项目', 'username': 'system_admin', 'role_code': 'system_admin'
        })
        self.assertEqual(response.status_code, 200)
        page = client.get('/backoffice/deploy-checklist')
        self.assertEqual(page.status_code, 200)
        for text in [
            'docs/saas-cloud-ops-runbook.md',
            'scripts/saas_ops_check.py',
            '日志轮转安装',
            '管理员重置密码流程',
            '恢复演练证据',
        ]:
            self.assertIn(text, page.text)


if __name__ == '__main__':
    unittest.main()
