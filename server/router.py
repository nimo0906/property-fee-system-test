#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP route dispatch for backend pages."""

import re
import urllib.parse

from server.db import qs
from server.permissions import canonical_role, is_readonly_role, required_get_role, required_post_role, role_allows

DISABLED_MODULE_PATTERNS = (
    r'^/repairs(?:/.*)?$',
    r'^/parking(?:/.*)?$',
    r'^/deposits(?:/.*)?$',
)


def _is_disabled_module_path(path):
    return any(re.match(pattern, path) for pattern in DISABLED_MODULE_PATTERNS)


READONLY_GET_ALLOWED = (
    r'^/$',
    r'^/owners$',
    r'^/rooms$',
    r'^/bills(?:/.*)?$',
    r'^/collections(?:/.*)?$',
    r'^/reminders(?:/.*)?$',
    r'^/reports(?:/.*)?$',
    r'^/logout$',
)

CUSTOMER_SERVICE_GET_ALLOWED = (
    r'^/$',
    r'^/owners(?:/create|/\d+/edit)?$',
    r'^/rooms(?:/create|/\d+/(?:edit|tenant_transfer))?$',
    r'^/bills(?:/.*)?$',
    r'^/collections(?:/.*)?$',
    r'^/reminders(?:/.*)?$',
    r'^/reports(?:/.*)?$',
    r'^/meter_readings(?:/ledger|/create)?$',
    r'^/merchant_contracts(?:$|/create$|/import$|/\d+$|/\d+/(?:edit|renew|deactivate|transfer)$|/\d+/attachments/\d+/download$)',
    r'^/commercial_spaces(?:$|/create$|/\d+/edit$)',
    r'^/import(?:/.*)?$',
    r'^/logout$',
)


OPERATOR_GET_BLOCKED = (
    r'^/backups(?:/.*)?$',
    r'^/audit_logs$',
    r'^/system_health(?:/.*)?$',
    r'^/system_update(?:/.*)?$',
    r'^/trial_data_reset$',
    r'^/users(?:/.*)?$',
    r'^/cloud_schema$',
    r'^/delivery_center(?:/.*)?$',
)


MANAGER_GET_BLOCKED = (
    r'^/backups(?:/.*)?$',
    r'^/audit_logs$',
    r'^/system_health(?:/.*)?$',
    r'^/system_update(?:/.*)?$',
    r'^/trial_data_reset$',
    r'^/cloud_schema$',
)


def _role_blocks_get(role, path):
    role = canonical_role(role)
    if role == 'readonly':
        return not any(re.match(pattern, path) for pattern in READONLY_GET_ALLOWED)
    if role == 'frontdesk':
        return not any(re.match(pattern, path) for pattern in CUSTOMER_SERVICE_GET_ALLOWED)
    if role == 'operator':
        return any(re.match(pattern, path) for pattern in OPERATOR_GET_BLOCKED)
    if role == 'manager':
        return any(re.match(pattern, path) for pattern in MANAGER_GET_BLOCKED)
    return False


# ── GET routing ────────────────────────────────────────────
from server.router_get import handle_get
from server.router_post import handle_post
