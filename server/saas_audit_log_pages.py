#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML audit log pages for SaaS backoffice."""

import json

from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page, _role_name


def _detail_text(detail):
    return json.dumps(detail or {}, ensure_ascii=False, sort_keys=True)


def _rows(items):
    rows = []
    for item in items:
        rows.append(f'''<tr><td>{_h(item.get('id'))}</td><td>{_h(item.get('action'))}</td><td>{_h(item.get('entity_type'))}</td><td>{_h(item.get('entity_id'))}</td><td>{_h(item.get('user_id'))}</td><td><pre class="hint">{_h(_detail_text(item.get('detail')))}</pre></td></tr>''')
    return ''.join(rows) or '<tr><td colspan="6">暂无审计日志</td></tr>'


def _render(user, items):
    readonly = '<span class="badge">只读</span>' if user.get('role_code') == 'executive' else ''
    body = f'''
<section class="hero"><div><h1>审计日志</h1><div class="sub">查看当前租户和项目内的账号、导入、出账、审核、收款等关键操作记录。审计日志只读展示，不提供页面删除。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><strong>当前角色：</strong>{_h(_role_name(user.get('role_code')))} {readonly}</div></section>
<section class="card"><div class="card-h">操作记录</div><div class="card-b"><table><thead><tr><th>ID</th><th>动作</th><th>对象类型</th><th>对象ID</th><th>用户ID</th><th>详情</th></tr></thead><tbody>{_rows(items)}</tbody></table></div></section>'''
    return _page('审计日志', body)


def register_audit_log_pages(app, service, repository, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/audit-logs', response_class=HTMLResponse)
    def audit_log_page(user=Depends(current_user)):
        try:
            service._require(user, 'read')
            if repository:
                items = repository.list_audit_logs(user['tenant_id'], user['project_id'])
            else:
                items = service.list_audit_logs(user, user['project_id'])
            return HTMLResponse(_render(user, items))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
