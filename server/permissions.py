#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Route-level role policy for local operator actions."""

import re

ADMIN_POST_PATTERNS = [
    r'^/rooms/\d+/delete$',
    r'^/owners/\d+/delete$',
    r'^/fee_types/(create|\d+/edit|\d+/delete)$',
    r'^/elevator_tiers/update$',
    r'^/late_fee_config/update$',
    r'^/batch_ops/(room_rate|fee_rate)$',
    r'^/bills/\d+/delete$',
    r'^/bills/undo_generated$',
    r'^/backups(/.*)?$',
    r'^/users(/.*)?$',
    r'^/closing/(close|reopen)$',
    r'^/system_health/repair$',
    r'^/system_update/check$',
    r'^/system_update/prepare$',
    r'^/system_update/open_folder$',
    r'^/trial_data_reset$',
    r'^/audit_logs/delete$',
    r'^/import/upload$',
]


def required_post_role(path):
    for pattern in ADMIN_POST_PATTERNS:
        if re.match(pattern, path):
            return 'admin'
    return ''


def role_allows(user_role, required_role):
    if not required_role:
        return True
    if required_role == 'admin':
        return user_role == 'admin'
    return user_role in (required_role, 'admin')
