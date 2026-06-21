#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Duplicate preview helpers for SaaS charge target imports."""

from server.saas_import_duplicates import target_key
from server.saas_user_pages import _h


def existing_charge_targets(service, repository, user):
    if repository:
        return repository.list_charge_targets(user['tenant_id'], user['project_id'])
    return service.list_charge_targets(user, user['project_id'])


def duplicate_preview_rows(valid_rows, existing_targets):
    existing = {target_key(row) for row in existing_targets}
    duplicates = []
    seen = set()
    for row in valid_rows:
        key = target_key(row)
        if key in existing or key in seen:
            duplicates.append(row)
        seen.add(key)
    return duplicates


def render_duplicate_preview_card(duplicates):
    if not duplicates:
        return ''
    rows = ''.join(
        f"<tr><td>{_h(' '.join(str(row.get(k) or '').strip() for k in ['building', 'unit', 'room_number']).strip())}</td><td>已存在收费对象</td></tr>"
        for row in duplicates
    )
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">重复预警</div><div class="card-b"><p class="sub">重复 {len(duplicates)} 行；确认导入时这些行会自动跳过，不会覆盖正式数据。</p><table><thead><tr><th>收费对象</th><th>原因</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''
