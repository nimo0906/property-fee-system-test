#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check independent license cloud service boundary assets."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_license_cloud import build_license_service_boundary, build_license_service_schema

DOC = ROOT / 'docs/saas-license-cloud-service-boundary.md'
GATE = ROOT / 'scripts/saas_release_gate.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    require(DOC.exists(), 'missing license cloud boundary doc')
    text = DOC.read_text(encoding='utf-8')
    for item in [
        '授权云服务后台边界设计', '独立服务', '独立数据库', '不得与 SaaS 业务主库混用',
        '不得保存客户上传业务数据', '只返回授权结果', 'license_customers', 'license_products',
        'license_entitlements', 'license_audit_logs',
    ]:
        require(item in text, f'missing doc item: {item}')
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in text, f'doc leaks sensitive or local value: {forbidden}')
    print('PASS license cloud boundary doc')

    schema = build_license_service_schema()
    for item in ['license_customers', 'license_products', 'license_entitlements', 'license_audit_logs']:
        require(item in schema, f'missing schema table: {item}')
    for forbidden in ['tenants', 'projects', 'owners', 'charge_targets', 'fee_types', 'bills', 'payments', 'imports', 'tenant_id', 'project_id']:
        require(forbidden not in schema, f'license schema mixes business boundary: {forbidden}')
    print('PASS license cloud schema boundary')

    boundary = build_license_service_boundary()
    require(boundary['database'] == 'property_license_cloud', 'license database must be independent')
    require(boundary['business_database'] == 'not_allowed', 'business database must be disallowed')
    require(boundary['stores_customer_uploads'] is False, 'license service must not store customer uploads')
    require(boundary['returns_business_data'] is False, 'license service must not return business data')
    print('PASS license cloud runtime boundary')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_license_cloud_boundary_check.py' in gate, 'release gate missing license cloud boundary check')
    print('PASS license cloud release gate')
    print('saas_license_cloud_boundary_check: PASS')


if __name__ == '__main__':
    main()
