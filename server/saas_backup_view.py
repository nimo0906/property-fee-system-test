#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial backup and restore drill view helpers."""


def _usernames(users):
    return {int(u.get('id')): u.get('username', '') for u in users}


def _audit_map(audits, action):
    result = {}
    for row in audits:
        if row.get('action') != action:
            continue
        detail = row.get('detail') or {}
        backup_id = detail.get('backup_id')
        if backup_id and backup_id not in result:
            result[backup_id] = row.get('id')
    return result


def backup_items(records, users, audits):
    names = _usernames(users)
    audit_ids = _audit_map(audits, 'backup.create')
    rows = []
    for item in records:
        backup_id = item.get('backup_id')
        rows.append({
            'id': item.get('id'),
            'backup_id': backup_id,
            'status': item.get('status'),
            'created_at': item.get('created_at', ''),
            'created_by_username': names.get(int(item.get('created_by') or 0), ''),
            'audit_action': 'backup.create',
            'audit_log_id': audit_ids.get(backup_id),
        })
    return rows


def restore_drill_items(drills, users, audits):
    names = _usernames(users)
    audit_ids = _audit_map(audits, 'restore.drill')
    rows = []
    for item in drills:
        backup_id = item.get('backup_id')
        rows.append({
            'id': item.get('id'),
            'backup_id': backup_id,
            'scope': item.get('scope'),
            'status': item.get('status'),
            'created_at': item.get('created_at', ''),
            'created_by_username': names.get(int(item.get('created_by') or 0), ''),
            'audit_action': 'restore.drill',
            'audit_log_id': audit_ids.get(backup_id),
        })
    return rows
