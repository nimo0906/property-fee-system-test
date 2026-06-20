#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit summary rendering helpers for SaaS backoffice."""

from server.saas_user_pages import _h

CATEGORIES = [
    ('账号操作', ('user.',)),
    ('密码操作', ('user.password_', 'user.password_change')),
    ('导入操作', ('import.',)),
    ('出账操作', ('bill.generate', 'bill.batch_generate', 'bill.approve')),
    ('收款操作', ('payment.',)),
    ('备份操作', ('backup.',)),
    ('恢复操作', ('restore.',)),
]


def render_audit_summary(items):
    cards = ''.join(_category_card(name, prefixes, items) for name, prefixes in CATEGORIES)
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">高风险操作分类</div><div class="card-b"><div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">{cards}</div><div class="hint">只显示当前租户和当前项目的审计日志；密码不展示在页面、日志或审计明细；审计日志只读展示，不提供页面删除。</div></div></section>'''


def _category_card(name, prefixes, items):
    count = sum(1 for item in items if _matches(item.get('action'), prefixes))
    return f'''<div class="card" style="box-shadow:none"><div class="card-b"><strong>{_h(name)}</strong><div class="sub">{count} 条</div></div></div>'''


def _matches(action, prefixes):
    action = str(action or '')
    return any(action.startswith(prefix) for prefix in prefixes)
