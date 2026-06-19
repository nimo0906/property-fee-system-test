#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent storage for license tenant bindings outside customer data."""

import subprocess
import sys
from pathlib import Path

from server.saas_license_binding import (
    bind_tenant_license_customer,
    license_customer_code_for_tenant,
    license_customer_code_for_user,
)
from server.saas_license_binding_store import LicenseBindingStore
from server.saas_service import SaasBackofficeService


def _service_with_user():
    service = SaasBackofficeService.in_memory()
    tenant_id = service.create_tenant('持久化物业')
    project_id = service.create_project(tenant_id, '持久化项目')
    user = service.create_user(tenant_id, 'admin', 'system_admin')
    user.update({'project_id': project_id, 'tenant_name': '持久化物业'})
    return service, user


def test_license_binding_store_uses_system_path_not_customer_upload_path(tmp_path):
    store = LicenseBindingStore(tmp_path)

    assert store.relative_path == 'system/license_bindings/tenant_license_bindings.json'
    assert '/tenants/' not in str(store.path)
    assert 'imports' not in str(store.path)
    assert 'attachments' not in str(store.path)


def test_license_binding_persists_across_service_instances(tmp_path):
    store = LicenseBindingStore(tmp_path)
    service, user = _service_with_user()

    bound = bind_tenant_license_customer(service, None, user, 'cust-persist', store=store)

    assert bound == 'cust-persist'
    assert license_customer_code_for_user(service, None, user, store=store) == 'cust-persist'

    fresh_service = SaasBackofficeService.in_memory()
    fresh_service.license_binding_store = store
    tenant = {'id': user['tenant_id'], 'name': '持久化物业'}

    assert license_customer_code_for_tenant(fresh_service, None, tenant, store=store) == 'cust-persist'
    text = store.path.read_text(encoding='utf-8')
    assert 'cust-persist' in text
    assert 'tenant_id' not in text
    assert 'project_id' not in text
    assert 'POSTGRES_PASSWORD' not in text
    assert 'APP_SECRET_KEY' not in text


def test_license_binding_persistence_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_binding_persistence_check.py')
    assert script.exists(), 'missing SaaS license binding persistence check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_binding_persistence_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_binding_persistence_check.py' in gate
