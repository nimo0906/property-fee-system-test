#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check license tenant binding persistence stays in system storage."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_license_binding import bind_tenant_license_customer, license_customer_code_for_user
from server.saas_license_binding_store import LicenseBindingStore
from server.saas_service import SaasBackofficeService


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        store = LicenseBindingStore(tmp)
        require(store.relative_path == 'system/license_bindings/tenant_license_bindings.json', 'wrong binding path')
        require('/tenants/' not in str(store.path), 'binding stored under tenant uploads')
        service = SaasBackofficeService.in_memory()
        tenant_id = service.create_tenant('绑定持久化检查物业')
        project_id = service.create_project(tenant_id, '绑定持久化检查项目')
        user = service.create_user(tenant_id, 'admin', 'system_admin')
        user.update({'project_id': project_id, 'tenant_name': '绑定持久化检查物业'})
        bind_tenant_license_customer(service, None, user, 'cust-persist-check', store=store)
        require(license_customer_code_for_user(service, None, user, store=store) == 'cust-persist-check', 'binding read failed')
        text = store.path.read_text(encoding='utf-8')
        for forbidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/tenants/']:
            require(forbidden not in text, f'binding store leaks forbidden value: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_binding_persistence_check.py' in gate, 'release gate missing license binding persistence check')
    print('saas_license_binding_persistence_check: PASS')


if __name__ == '__main__':
    main()
