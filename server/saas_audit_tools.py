#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit log filtering and sanitizing helpers for SaaS backoffice."""

import json

RISK_ACTIONS = ('password', 'reset', 'import', 'bill.', 'payment.', 'backup', 'restore', 'disable', 'active')
MASK_KEYS = {'tenant_id', 'project_id', 'password', 'password_hash', 'old_password', 'new_password', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD'}


def clean_detail(value):
    if isinstance(value, dict):
        return {k: clean_detail(v) for k, v in value.items() if k not in MASK_KEYS and 'password' not in str(k).lower()}
    if isinstance(value, list):
        return [clean_detail(v) for v in value]
    text = str(value)
    if 'POSTGRES_PASSWORD=' in text or 'APP_SECRET_KEY=' in text:
        return '[masked]'
    return value


def detail_text(detail):
    return json.dumps(clean_detail(detail or {}), ensure_ascii=False, sort_keys=True)


def risk_level(item):
    action = str(item.get('action') or '').lower()
    return 'high' if any(token in action for token in RISK_ACTIONS) else 'normal'


def sanitize_audit_item(item):
    row = dict(item)
    row['detail'] = clean_detail(row.get('detail'))
    row['risk_level'] = risk_level(row)
    return row


def filter_audit_items(items, action='', entity_type='', keyword='', risk=''):
    action = str(action or '').strip().lower()
    entity_type = str(entity_type or '').strip().lower()
    keyword = str(keyword or '').strip().lower()
    risk = str(risk or '').strip().lower()
    rows = []
    for raw in items:
        item = sanitize_audit_item(raw)
        if action and action not in str(item.get('action') or '').lower():
            continue
        if entity_type and entity_type != str(item.get('entity_type') or '').lower():
            continue
        if risk == 'high' and item.get('risk_level') != 'high':
            continue
        haystack = ' '.join(str(item.get(k, '')) for k in ['id', 'action', 'entity_type', 'entity_id', 'user_id'])
        haystack += ' ' + detail_text(item.get('detail'))
        if keyword and keyword not in haystack.lower():
            continue
        rows.append(item)
    return rows
