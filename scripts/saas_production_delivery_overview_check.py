#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production delivery overview page registration and links."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app

SCRIPT = 'scripts/saas_production_delivery_overview_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '生产交付总览检查物业', 'project_name': '生产交付总览检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/production-delivery')
    for item in [
        '生产交付总览', '现场实施顺序', '1. 生产部署自检', '2. 首租户业务冒烟',
        '3. 生产一键验收', '4. 生产验收结果中心', '5. 下载交付证据包',
        '6. 填写生产验收签收', '7. 查看签收历史', '8. 备份恢复覆盖核验',
        '/backoffice/deploy-checklist', '/backoffice/production-acceptance',
        '/backoffice/production-acceptance/evidence-package.zip', '/backoffice/production-acceptance/signoff', '/backoffice/backups',
        '客户上传数据与系统自身数据隔离', '业务数据不进入授权云服务',
    ]:
        require(item in page.text, f'missing overview item: {item}')
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
        require(hidden not in page.text, f'forbidden overview content: {hidden}')
    for path in ['/backoffice', '/backoffice/deploy-checklist', '/backoffice/production-acceptance', '/backoffice/acceptance']:
        response = client.get(path)
        require('/backoffice/production-delivery' in response.text, f'missing overview link from {path}')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_delivery_overview_check: PASS')


if __name__ == '__main__':
    main()
