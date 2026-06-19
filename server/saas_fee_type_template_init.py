#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize recommended fee types from tenant business template."""

from server.saas_tenant_business_config import business_template_for_user

_WRITE_ROLES = {'system_admin', 'platform_admin'}


def recommended_fee_rows(service, repository, user):
    template = business_template_for_user(service, repository, user)
    return [_fee_row(name) for name in template['fees']]


def initialize_recommended_fee_types(service, repository, user):
    if user.get('role_code') not in _WRITE_ROLES:
        from server.saas_service import PermissionDenied
        raise PermissionDenied('fee template init denied')
    existing = _list_existing(service, repository, user)
    existing_names = {str(item.get('name')) for item in existing}
    created = []
    for row in recommended_fee_rows(service, repository, user):
        if row['name'] in existing_names:
            continue
        if repository:
            item = repository.create_fee_type(user['tenant_id'], user['project_id'], row['name'], row['unit_price'], row['billing_mode'])
            service._log(user, user['project_id'], 'fee_type.template_init', 'fee_type', item['id'], {'name': row['name'], 'billing_mode': row['billing_mode']})
        else:
            item = service.create_fee_type(user, user['project_id'], row['name'], row['unit_price'], row['billing_mode'])
        created.append(item)
        existing_names.add(row['name'])
    return {'created_count': len(created), 'created': created}


def _list_existing(service, repository, user):
    if repository:
        return repository.list_fee_types(user['tenant_id'], user['project_id'])
    return service.list_fee_types(user, user['project_id'])


def _fee_row(name):
    if name == '物业费':
        return {'name': name, 'unit_price': 2.0, 'billing_mode': 'area'}
    return {'name': name, 'unit_price': 0.0, 'billing_mode': 'fixed'}
