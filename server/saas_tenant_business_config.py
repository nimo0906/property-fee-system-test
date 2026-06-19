#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""System-scoped tenant business configuration for SaaS."""

import json
from pathlib import Path

from server.saas_business_templates import TEMPLATES, business_template

_CONFIG_ATTR = 'tenant_business_configs'


class TenantBusinessConfigStore:
    relative_path = 'system/tenant_business_configs/tenant_business_configs.json'

    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.path = self.root_dir / self.relative_path

    def load(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        configs = {}
        for key, value in data.get('configs', {}).items():
            code = str((value or {}).get('template_code') or 'residential')
            configs[int(key)] = {'template_code': code if code in TEMPLATES else 'residential'}
        return configs

    def save(self, configs):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'configs': {
                str(int(tenant_id)): {'template_code': _safe_code(item.get('template_code'))}
                for tenant_id, item in configs.items()
            }
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
        return payload


def save_tenant_business_template(service, repository, user, template_code, store=None):
    configs = _configs(service, store)
    code = _safe_code(template_code)
    configs[int(user['tenant_id'])] = {'template_code': code}
    if store:
        store.save(configs)
    service._log(user, user['project_id'], 'tenant.business_config_update', 'tenant_business_config', None, {'template': code})
    return business_template_for_user(service, repository, user, store)


def business_template_for_user(service, repository, user, store=None):
    code = template_code_for_user(service, repository, user, store)
    item = dict(business_template(code))
    item['code'] = code
    return item


def template_code_for_user(service, repository, user, store=None):
    configs = _configs(service, store)
    item = configs.get(int(user.get('tenant_id') or 0), {})
    return _safe_code(item.get('template_code'))


def _configs(service, store=None):
    configs = getattr(service, _CONFIG_ATTR, None)
    if configs is None:
        configs = store.load() if store else {}
        setattr(service, _CONFIG_ATTR, configs)
    return configs


def _safe_code(code):
    code = str(code or 'residential').strip()
    return code if code in TEMPLATES else 'residential'
