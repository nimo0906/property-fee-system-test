#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant and project management pages for SaaS backoffice."""

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _tenant_name_map(tenants):
    return {int(t['id']): t.get('name') for t in tenants}


def _render_page(user, tenants, projects, message=''):
    platform = user.get('role_code') == 'platform_admin'
    title_badge = '平台租户视图' if platform else '本租户项目视图'
    names = _tenant_name_map(tenants)
    rows = ''.join(
        f'''<tr><td>{_h(row.get('id'))}</td><td>{_h(names.get(int(row.get('tenant_id'))))}</td><td><strong>{_h(row.get('name'))}</strong></td><td>{_h(row.get('code'))}</td><td>{'启用' if row.get('is_active', 1) else '停用'}</td></tr>'''
        for row in projects
    ) or '<tr><td colspan="5">暂无项目</td></tr>'
    tenant_rows = ''.join(
        f'''<tr><td>{_h(row.get('id'))}</td><td><strong>{_h(row.get('name'))}</strong></td><td>{_h(row.get('status'))}</td></tr>'''
        for row in tenants
    )
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    create_form = '' if platform else '''<aside class="card"><div class="card-h">新增本公司项目</div><div class="card-b"><form method="post" action="/backoffice/tenant-projects/create"><label>项目名称</label><input name="name" required placeholder="例如 一期 / 二期 / 商业街"><label>项目编码</label><input name="code" placeholder="例如 A-001"><button class="primary">创建项目</button><div class="hint">新项目只归属当前公司，后续收费对象、账单、收款都会按项目隔离。</div></form></div></aside>'''
    tenant_card = f'''<section class="card" style="margin-top:18px"><div class="card-h">租户列表</div><div class="card-b"><table><thead><tr><th>ID</th><th>公司/租户</th><th>状态</th></tr></thead><tbody>{tenant_rows}</tbody></table></div></section>''' if platform else ''
    body = f'''
<section class="hero"><div><h1>租户项目管理</h1><div class="sub">正式商业版用于确认公司租户和项目边界。租户管理员只能维护本公司项目，平台管理员只读查看租户全局。</div></div><div class="badge tenant-scope">{_h(title_badge)}</div></section>{notice}
<section class="grid"><div class="card"><div class="card-h">项目列表</div><div class="card-b"><table><thead><tr><th>ID</th><th>公司/租户</th><th>项目</th><th>编码</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table></div></div>{create_form}</section>{tenant_card}'''
    return _page('租户项目管理', body)


def _items(user, repository, service):
    if user.get('role_code') not in {'system_admin', 'platform_admin'}:
        raise PermissionDenied('admin only')
    if repository:
        tenants = repository.list_tenants() if user.get('role_code') == 'platform_admin' else [repository.get_tenant(user['tenant_id'])]
        projects = repository.list_projects() if user.get('role_code') == 'platform_admin' else repository.list_projects(user['tenant_id'])
        return tenants, projects
    tenant = service.tenants[user['tenant_id']]
    projects = [p for p in service.projects.values() if p['tenant_id'] == user['tenant_id']]
    return [tenant], projects


def register_tenant_project_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    @app.get('/backoffice/tenant-projects', response_class=HTMLResponse)
    def tenant_project_page(user=Depends(current_user), message: str = ''):
        try:
            tenants, projects = _items(user, repository, service)
            return HTMLResponse(_render_page(user, tenants, projects, message))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/tenant-projects/create')
    def create_project_page(name: str = Form(...), code: str = Form(''), user=Depends(current_user)):
        try:
            if user.get('role_code') != 'system_admin':
                raise PermissionDenied('tenant admin only')
            if repository:
                repository.create_project_for_actor(user, name.strip(), code.strip() or None)
            else:
                service.create_project(user['tenant_id'], name.strip())
            return RedirectResponse('/backoffice/tenant-projects?message=项目已创建', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
