#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""System-scoped persistence for first tenant acceptance records."""

import json
import os
from pathlib import Path


class FirstTenantAcceptanceStore:
    relative_path = 'system/first_tenant_acceptance/records.json'

    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.path = self.root_dir / self.relative_path

    def load(self):
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding='utf-8'))
        return [_clean_record(item) for item in data.get('records', []) if isinstance(item, dict)]

    def save(self, records):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'records': [_clean_record(item) for item in records]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
        return payload


def _clean_record(item):
    checked = [str(value) for value in (item.get('checked') or [])]
    return {
        'tenant_name': str(item.get('tenant_name') or ''),
        'project_name': str(item.get('project_name') or ''),
        'operator_name': str(item.get('operator_name') or ''),
        'customer_signer': str(item.get('customer_signer') or ''),
        'notes': str(item.get('notes') or ''),
        'checked': checked,
        'checked_count': int(item.get('checked_count') or len(checked)),
        'total_count': int(item.get('total_count') or len(checked)),
    }


def acceptance_store_from_env():
    system_dir = os.environ.get('SAAS_SYSTEM_FILES_DIR')
    return FirstTenantAcceptanceStore(Path(system_dir).parent) if system_dir else None
