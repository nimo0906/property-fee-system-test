#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operational readiness check for SaaS cloud backoffice."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    runbook = ROOT / 'docs/saas-cloud-ops-runbook.md'
    require(runbook.exists(), 'missing ops runbook')
    text = runbook.read_text(encoding='utf-8')
    for item in [
        'SaaS 云端商业版运维手册', '通用 Linux/VPS', 'docker compose up -d',
        'scripts/saas_preflight_check.py', 'scripts/saas_acceptance_check.py',
        'scripts/saas_backup.sh', 'scripts/saas_restore.sh --verify-metadata',
    ]:
        require(item in text, f'missing runbook item: {item}')
    print('PASS saas ops runbook')

    logrotate = (ROOT / 'deploy/logrotate/property-saas').read_text(encoding='utf-8')
    for item in ['/var/log/property-saas/*.log', 'rotate 14', 'compress', 'copytruncate']:
        require(item in logrotate, f'missing logrotate item: {item}')
    print('PASS saas logrotate config')

    for item in [
        '管理员重置密码流程', '租户管理员只能重置本租户员工账号',
        '平台管理员可跨租户重置账号但必须写入目标租户审计', '密码不展示在页面、日志或审计明细',
    ]:
        require(item in text, f'missing password reset procedure: {item}')
    print('PASS saas password reset procedure')

    for item in ['恢复演练证据', 'metadata.json', '账单/收款/报表核对结果']:
        require(item in text, f'missing restore drill evidence: {item}')
    print('PASS saas restore drill evidence checklist')

    for path in ['docker-compose.yml', 'deploy/nginx/property-saas.conf', 'deploy/systemd/property-saas.service']:
        require((ROOT / path).exists(), f'missing deploy asset: {path}')
    print('PASS saas deployment commands')


if __name__ == '__main__':
    main()
