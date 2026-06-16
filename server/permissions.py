#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Route-level role policy for local operator actions."""

import re

ADMIN_POST_PATTERNS = [
    r'^/rooms/\d+/delete$',
    r'^/rooms/batch_delete$',
    r'^/owners/\d+/delete$',
    r'^/fee_types/\d+/delete$',
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
    r'^/auto_billing/runs/[^/]+/rollback$',
]

MANAGER_POST_PATTERNS = [
    r'^/users(/.*)?$',
]

FINANCE_GET_PATTERNS = [
    r'^/billing$',
    r'^/commercial_billing$',
    r'^/auto_billing$',
    r'^/shared_expenses$',
    r'^/payments$',
    r'^/invoices$',
    r'^/invoice_requests$',
    r'^/closing$',
    r'^/merchant_contracts/create$',
    r'^/merchant_contracts/import$',
    r'^/commercial_receivables$',
    r'^/merchant_contracts/\d+/(billing|turnover_rent)$',
    r'^/merchant_contracts/\d+/amendments/\d+$',
    r'^/fee_types/create$',
    r'^/fee_types/\d+/edit$',
    r'^/reports/.+\.(csv|xlsx)$',
    r'^/export/kingdee$',
    r'^/bills/export.*$',
]

CUSTOMER_SERVICE_GET_PATTERNS = [
    r'^/import$',
    r'^/merchant_contracts/create$',
    r'^/merchant_contracts/import$',
    r'^/merchant_contracts/\d+/(edit|renew|deactivate|transfer)$',
    r'^/rooms/create$',
    r'^/rooms/\d+/(edit|tenant_transfer)$',
    r'^/owners/create$',
    r'^/owners/\d+/edit$',
    r'^/meter_readings/create$',
]

FINANCE_POST_PATTERNS = [
    r'^/fee_types/create$',
    r'^/fee_types/\d+/edit$',
    r'^/meter_readings/\d+/delete$',
    r'^/invoices/create$',
    r'^/invoice_requests/[^/]+/status$',
    r'^/invoices/\d+/delete$',
    r'^/billing/calc$',
    r'^/auto_billing/confirm$',
    r'^/commercial_receivables/confirm$',
    r'^/shared_expenses/allocate$',
    r'^/payments/(print|receipts)$',
    r'^/bills/generate$',
    r'^/bills/\d+/pay$',
    r'^/bills/\d+/edit$',
    r'^/bills/batch_pay$',
    r'^/bills/batch_edit.*$',
    r'^/bills/export_selected$',
    r'^/bills/receipt_by_ids$',
    r'^/merchant_contracts/\d+/delete$',
    r'^/merchant_contracts/\d+/turnover_rent$',
    r'^/merchant_contracts/\d+/amendments/\d+/confirm$',
    r'^/merchant_contracts/\d+/billing/confirm$',
    r'^/merchant_contracts/\d+/generate$',
]

CUSTOMER_SERVICE_POST_PATTERNS = [
    r'^/rooms/create$',
    r'^/rooms/\d+/(edit|tenant_transfer)$',
    r'^/owners/create$',
    r'^/owners/\d+/edit$',
    r'^/meter_readings/create$',
    r'^/meter_readings/ledger/save$',
    r'^/meter_readings/\d+/confirm$',
    r'^/merchant_contracts/create$',
    r'^/merchant_contracts/import$',
    r'^/merchant_contracts/import/confirm$',
    r'^/merchant_contracts/\d+/edit$',
    r'^/merchant_contracts/\d+/renew$',
    r'^/merchant_contracts/\d+/deactivate$',
    r'^/merchant_contracts/\d+/transfer$',
    r'^/merchant_contracts/\d+/attachments$',
    r'^/merchant_contracts/\d+/attachments/\d+/recognize$',
    r'^/commercial_spaces/create$',
    r'^/commercial_spaces/\d+/edit$',
    r'^/import/upload$',
]

ROLE_ALIASES = {
    'system_admin': 'admin',
    'finance': 'operator',
    'cashier': 'operator',
    'executive': 'readonly',
}

READONLY_ROLES = {'readonly', 'executive'}


def canonical_role(role):
    return ROLE_ALIASES.get(role, role)


def is_readonly_role(role):
    return role in READONLY_ROLES or canonical_role(role) == 'readonly'


def required_get_role(path):
    for pattern in CUSTOMER_SERVICE_GET_PATTERNS:
        if re.match(pattern, path):
            return 'customer_service'
    for pattern in FINANCE_GET_PATTERNS:
        if re.match(pattern, path):
            return 'finance'
    return ''


def required_post_role(path):
    for pattern in ADMIN_POST_PATTERNS:
        if re.match(pattern, path):
            return 'admin'
    for pattern in MANAGER_POST_PATTERNS:
        if re.match(pattern, path):
            return 'manager'
    for pattern in CUSTOMER_SERVICE_POST_PATTERNS:
        if re.match(pattern, path):
            return 'customer_service'
    for pattern in FINANCE_POST_PATTERNS:
        if re.match(pattern, path):
            return 'finance'
    return ''


def role_allows(user_role, required_role):
    if not required_role:
        return True
    raw_user_role = user_role
    user_role = canonical_role(user_role)
    if required_role == 'admin':
        return user_role == 'admin'
    if required_role == 'finance':
        return raw_user_role in ('finance', 'operator', 'manager', 'admin', 'system_admin')
    if required_role == 'customer_service':
        return raw_user_role in ('frontdesk', 'finance', 'operator', 'manager', 'admin', 'system_admin')
    if required_role == 'cashier':
        return raw_user_role in ('cashier', 'finance', 'manager', 'admin', 'system_admin')
    if required_role == 'readonly':
        return user_role in ('readonly', 'operator', 'manager', 'admin')
    if required_role == 'manager':
        return user_role in ('manager', 'admin')
    return user_role in (required_role, 'admin')
