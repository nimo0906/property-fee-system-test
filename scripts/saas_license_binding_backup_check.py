#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check license binding backup, restore, and verification flow."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_license_binding_backup import export_binding_backup, restore_binding_backup, verify_binding_backup
from server.saas_license_binding_store import LicenseBindingStore


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source = LicenseBindingStore(base / 'source')
        source.save({1: 'cust-alpha'})
        manifest = export_binding_backup(source, base / 'backup')
        require(manifest['binding_file'] == 'system/license_bindings/tenant_license_bindings.json', 'wrong binding backup path')
        require(verify_binding_backup(base / 'backup')['ok'] is True, 'backup verify failed')
        target = LicenseBindingStore(base / 'restore')
        restored = restore_binding_backup(base / 'backup', target)
        require(restored == {1: 'cust-alpha'}, 'restore failed')
        text = target.path.read_text(encoding='utf-8')
        for forbidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/tenants/']:
            require(forbidden not in text, f'restore leaks forbidden value: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_binding_backup_check.py' in gate, 'release gate missing license binding backup check')
    print('saas_license_binding_backup_check: PASS')


if __name__ == '__main__':
    main()
