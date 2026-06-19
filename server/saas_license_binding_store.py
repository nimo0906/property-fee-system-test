#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""System-scoped persistent storage for SaaS license bindings."""

import json
from pathlib import Path


class LicenseBindingStore:
    relative_path = 'system/license_bindings/tenant_license_bindings.json'

    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.path = self.root_dir / self.relative_path

    def load(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        return {int(k): str(v) for k, v in data.get('bindings', {}).items()}

    def save(self, bindings):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'bindings': {str(int(k)): str(v) for k, v in bindings.items() if str(v).strip()}}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
        return payload
