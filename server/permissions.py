#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Route-level role policy for local operator actions."""

import re

ADMIN_POST_PATTERNS = [
    r'^/rooms/\d+/delete$',
    r'^/rooms/batch_delete$',
    r'^/owners/\d+/delete$',
    r'^/fee_types/(create|\d+/edit|\d+/delete)$',
    r'^/elevator_tiers/update$',
    r'^/late_fee_config/update$',
    r'^/batch_ops/(room_rate|fee_rate)$',
    r'^/bills/\d+/delete$',
    r'^/bills/undo_generated$',
    r'^/backups(/.*)?$',
    r'^/closing/(close|reopen)$',
    r'^/system_health/repair$',
    r'^/system_update/check$',
    r'^/system_update/prepare$',
    r'^/system_update/open_folder$',
    r'^/trial_data_reset$',
    r'^/audit_logs/delete$',
    r'^/import/upload$',
    r'^/auto_billing/runs/[^/]+/rollback$',
]

MANAGER_POST_PATTERNS = [
    r'^/users(/.*)?$',
]

FINANCE_POST_PATTERNS = [
    r'^/merchant_contracts/create$',
    r'^/merchant_contracts/\d+/generate$',
]


def required_post_role(path):
    for pattern in ADMIN_POST_PATTERNS:
        if re.match(pattern, path):
            return 'admin'
    for pattern in MANAGER_POST_PATTERNS:
        if re.match(pattern, path):
            return 'manager'
    for pattern in FINANCE_POST_PATTERNS:
        if re.match(pattern, path):
            return 'finance'
    return ''


def role_allows(user_role, required_role):
    if not required_role:
        return True
    user_role_aliases = {
        'system_admin': 'admin',
        'finance': 'operator',
        'cashier': 'operator',
        'frontdesk': 'readonly',
        'executive': 'readonly',
    }
    raw_user_role = user_role
    user_role = user_role_aliases.get(user_role, user_role)
    if required_role == 'admin':
        return user_role == 'admin'
    if required_role == 'finance':
        return raw_user_role in ('finance', 'manager', 'admin', 'system_admin')
    if required_role == 'cashier':
        return raw_user_role in ('cashier', 'finance', 'manager', 'admin', 'system_admin')
    if required_role == 'readonly':
        return user_role in ('readonly', 'operator', 'manager', 'admin')
    if required_role == 'manager':
        return user_role in ('manager', 'admin')
    return user_role in (required_role, 'admin')
