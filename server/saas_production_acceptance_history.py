#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""System-side history for production acceptance signoff records."""

import json
from pathlib import Path

FORBIDDEN = ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id']


def safe_text(value):
    text = str(value or '').strip()
    for forbidden in FORBIDDEN:
        text = text.replace(forbidden, '[redacted]')
    return text


def history_path(root):
    return Path(root) / 'release' / 'production_acceptance_signoffs' / 'history.json'


def load_history(root):
    path = history_path(root)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    return [_clean(item) for item in data.get('records', []) if isinstance(item, dict)]


def save_history(root, records):
    path = history_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'records': [_clean(item) for item in records]}
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
    return payload


def append_history(root, data, markdown):
    records = load_history(root)
    record_id = len(records) + 1
    record = _clean({**data, 'id': record_id, 'markdown': markdown})
    records.append(record)
    save_history(root, records)
    return record


def get_history(root, record_id):
    for record in load_history(root):
        if int(record.get('id') or 0) == int(record_id):
            return record
    return None


def history_rows(root, escape):
    rows = []
    for record in load_history(root):
        rid = int(record.get('id') or 0)
        rows.append(
            f'<tr><td>{rid}</td><td>{escape(record.get("operator_name"))}</td>'
            f'<td>{escape(record.get("customer_signer"))}</td><td>{escape(record.get("signoff_date"))}</td>'
            f'<td>{escape(record.get("notes"))}</td><td><a class="ghost-link" href="/backoffice/production-acceptance/signoff/history/{rid}/download.md">下载</a></td></tr>'
        )
    return ''.join(rows) or '<tr><td colspan="6">暂无签收历史记录</td></tr>'


def _clean(item):
    return {
        'id': int(item.get('id') or 0),
        'operator_name': safe_text(item.get('operator_name')),
        'server_domain': safe_text(item.get('server_domain')),
        'acceptance_status': safe_text(item.get('acceptance_status')),
        'customer_signer': safe_text(item.get('customer_signer')),
        'implementation_signer': safe_text(item.get('implementation_signer')),
        'signoff_date': safe_text(item.get('signoff_date')),
        'notes': safe_text(item.get('notes')),
        'markdown': safe_text(item.get('markdown')),
    }
