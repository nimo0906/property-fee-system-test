#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production acceptance evidence package precheck status."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
from server.saas_production_acceptance_package import package_precheck
import server.saas_production_acceptance_pages as production_pages

SCRIPT = 'scripts/saas_production_acceptance_evidence_package_precheck.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        production_pages.ROOT = root
        release = root / 'release'
        release.mkdir(parents=True)
        (release / 'saas-production-acceptance-result.md').write_text('ok', encoding='utf-8')
        rows = package_precheck(root)
        by_name = {row['package_name']: row for row in rows}
        require(by_name['saas-production-acceptance-result.md']['status'] == '存在', 'existing result not detected')
        require(by_name['saas-release-evidence.md']['included'] == '占位进入总包', 'missing evidence should be placeholder')
        require(by_name['backup-coverage.md']['status'] == '自动生成', 'backup coverage should be generated')
        client = TestClient(create_app())
        login = client.post('/api/auth/login', json={
            'tenant_name': '证据包预检检查物业', 'project_name': '证据包预检检查项目',
            'username': 'admin', 'role_code': 'system_admin',
        })
        require(login.status_code == 200, 'login failed')
        page = client.get('/backoffice/production-acceptance')
        for item in ['证据包预检状态', '存在', '缺失', '自动生成', '占位进入总包', 'backup-coverage.md']:
            require(item in page.text, f'missing precheck page item: {item}')
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
            require(hidden not in page.text, f'forbidden precheck page content: {hidden}')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_acceptance_evidence_package_precheck: PASS')


if __name__ == '__main__':
    main()
