#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operational runbook assets for SaaS license binding delivery."""

import subprocess
import sys
from pathlib import Path


def test_license_binding_runbook_covers_delivery_backup_restore_and_audit():
    doc = Path('docs/saas-license-binding-ops-runbook.md')
    assert doc.exists(), 'missing license binding ops runbook'
    text = doc.read_text(encoding='utf-8')
    for required in [
        'SaaS 授权绑定运维交付清单',
        '授权绑定',
        '备份',
        '恢复',
        '迁移',
        '审计检查',
        'system/license_bindings/tenant_license_bindings.json',
        'scripts/saas_license_tenant_binding_check.py',
        'scripts/saas_license_binding_page_check.py',
        'scripts/saas_license_binding_persistence_check.py',
        'scripts/saas_license_binding_backup_check.py',
        '不得写入客户上传数据目录',
        '不得写入 SaaS 业务表',
        'license.tenant_bind',
    ]:
        assert required in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_license_binding_runbook_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_license_binding_runbook_check.py')
    assert script.exists(), 'missing license binding runbook check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_binding_runbook_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_binding_runbook_check.py' in gate
