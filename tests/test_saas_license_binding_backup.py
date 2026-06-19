#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup, restore, and verify license binding system file."""

import subprocess
import sys
from pathlib import Path

from server.saas_license_binding_backup import export_binding_backup, restore_binding_backup, verify_binding_backup
from server.saas_license_binding_store import LicenseBindingStore


def test_license_binding_backup_export_restore_and_verify(tmp_path):
    source_root = tmp_path / 'source'
    backup_root = tmp_path / 'backup'
    restore_root = tmp_path / 'restore'
    source = LicenseBindingStore(source_root)
    source.save({1: 'cust-alpha', 2: 'cust-beta'})

    package = export_binding_backup(source, backup_root)

    assert package['kind'] == 'license-binding-backup'
    assert package['binding_file'] == 'system/license_bindings/tenant_license_bindings.json'
    assert (backup_root / package['binding_file']).exists()
    assert verify_binding_backup(backup_root)['ok'] is True
    text = (backup_root / package['binding_file']).read_text(encoding='utf-8')
    assert 'cust-alpha' in text
    assert 'tenant_id' not in text
    assert 'project_id' not in text

    target = LicenseBindingStore(restore_root)
    restored = restore_binding_backup(backup_root, target)

    assert restored == {1: 'cust-alpha', 2: 'cust-beta'}
    assert target.load() == {1: 'cust-alpha', 2: 'cust-beta'}
    assert 'tenants' not in str(target.path)


def test_license_binding_backup_rejects_missing_or_tampered_manifest(tmp_path):
    source = LicenseBindingStore(tmp_path / 'source')
    source.save({1: 'cust-alpha'})
    export_binding_backup(source, tmp_path / 'backup')
    (tmp_path / 'backup' / 'manifest.json').write_text('{"kind":"bad"}', encoding='utf-8')

    result = verify_binding_backup(tmp_path / 'backup')

    assert result['ok'] is False
    assert 'invalid' in result['error']


def test_license_binding_backup_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_binding_backup_check.py')
    assert script.exists(), 'missing SaaS license binding backup check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_binding_backup_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_binding_backup_check.py' in gate
