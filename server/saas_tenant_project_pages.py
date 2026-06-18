#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant and project management pages for SaaS backoffice."""

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _tenant_name_map(tenants):
    return {int(t['id']): t.get('name') for t in tenants}


def _project_row(user, platform, names, row):
    action = ''
    if not platform:
        if int(row.get('id')) == int(user.get('project_id')):
            action = '<span class="status on">当前项目</span>'
        else:
            action = f'''<form method="post" action="/backoffice/tenant-projects/switch"><input type="hidden" name="project_id" value="{_h(row.get('id'))}"><button class="ghost">切换项目</button></form>'''
    return f'''<tr><td>{_h(row.get('id'))}</td><td>{_h(names.get(int(row.get('tenant_id'))))}</td><td><strong>{_h(row.get('name'))}</strong></td><td>{_h(row.get('code'))}</td><td>{'启用' if row.get('is_active', 1) else '停用'}</td><td>{action}</td></tr>'''


def _tenant_row(user, row):
    action = ''
    if user.get('role_code') == 'platform_admin' and int(row.get('id')) != int(user.get('tenant_id')):
        next_status = 'active' if row.get('status') == 'suspended' else 'suspended'
        label = '启用租户' if next_status == 'active' else '停用租户'
        cls = 'ghost' if next_status == 'active' else 'danger'
        action = f'''<form method="post" action="/backoffice/tenant-projects/tenant-status"><input type="hidden" name="tenant_id" value="{_h(row.get('id'))}"><input type="hidden" name="status" value="{_h(next_status)}"><button class="{cls}">{label}</button></form>'''
    return f'''<tr><td>{_h(row.get('id'))}</td><td><strong>{_h(row.get('name'))}</strong></td><td>{_h(row.get('status'))}</td><td>{action}</td></tr>'''


def _filter_platform_items(tenants, projects, tenant_q='', tenant_status=''):
    q = str(tenant_q or '').strip().lower()
    status = str(tenant_status or '').strip()
    if status not in {'', 'active', 'suspended'}:
        status = ''
    rows = []
    for tenant in tenants:
        if q and q not in str(tenant.get('name') or '').lower():
            continue
        if status and tenant.get('status') != status:
            continue
        rows.append(tenant)
    ids = {int(row['id']) for row in rows}
    return rows, [p for p in projects if int(p.get('tenant_id')) in ids], {'tenant_q': tenant_q or '', 'tenant_status': status}


def _filter_form(filters):
    q = _h(filters.get('tenant_q', ''))
    status = filters.get('tenant_status', '')
    options = ''.join(
        f'<option value="{value}"{" selected" if status == value else ""}>{label}</option>'
        for value, label in [('', '全部状态'), ('active', '启用'), ('suspended', '停用')]
    )
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-b"><form method="get" action="/backoffice/tenant-projects" class="filters"><div><label>客户关键词</label><input name="tenant_q" value="{q}" placeholder="公司名称"></div><div><label>租户状态</label><select name="tenant_status">{options}</select></div><div><button class="primary">筛选租户</button></div></form></div></section>'''


def _render_page(user, tenants, projects, message='', filters=None):
    platform = user.get('role_code') == 'platform_admin'
    title_badge = '平台租户视图' if platform else '本租户项目视图'
    names = _tenant_name_map(tenants)
    rows = ''.join(_project_row(user, platform, names, row) for row in projects) or '<tr><td colspan="6">暂无项目</td></tr>'
    tenant_rows = ''.join(_tenant_row(user, row) for row in tenants)
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    filter_bar = _filter_form(filters or {}) if platform else ''
    create_form = '' if platform else '''<aside class="card"><div class="card-h">新增本公司项目</div><div class="card-b"><form method="post" action="/backoffice/tenant-projects/create"><label>项目名称</label><input name="name" required placeholder="例如 一期 / 二期 / 商业街"><label>项目编码</label><input name="code" placeholder="例如 A-001"><button class="primary">创建项目</button><div class="hint">新项目只归属当前公司，后续收费对象、账单、收款都会按项目隔离。</div></form></div></aside>'''
    tenant_card = f'''<section class="card" style="margin-top:18px"><div class="card-h">租户列表</div><div class="card-b"><table><thead><tr><th>ID</th><th>公司/租户</th><th>状态</th><th>操作</th></tr></thead><tbody>{tenant_rows}</tbody></table></div></section>''' if platform else ''
    body = f'''
<section class="hero"><div><h1>租户项目管理</h1><div class="sub">正式商业版用于确认公司租户和项目边界。租户管理员只能维护本公司项目，平台管理员只读查看租户全局。</div></div><div class="badge tenant-scope">{_h(title_badge)}</div></section>{notice}{filter_bar}
<section class="grid"><div class="card"><div class="card-h">项目列表</div><div class="card-b"><table><thead><tr><th>ID</th><th>公司/租户</th><th>项目</th><th>编码</th><th>状态</th><th>操作</th></tr></thead><tbody>{rows}</tbody></table></div></div>{create_form}</section>{tenant_card}'''
    return _page('租户项目管理', body)


def _items(user, repository, service, tenant_q='', tenant_status=''):
    if user.get('role_code') not in {'system_admin', 'platform_admin'}:
        raise PermissionDenied('admin only')
    if repository:
        if user.get('role_code') == 'platform_admin':
            return _filter_platform_items(repository.list_tenants(), repository.list_projects(), tenant_q, tenant_status)
        return [repository.get_tenant(user['tenant_id'])], repository.list_projects(user['tenant_id']), {}
    tenant = service.tenants[user['tenant_id']]
    projects = [p for p in service.projects.values() if p['tenant_id'] == user['tenant_id']]
    return [tenant], projects, {}


def register_tenant_project_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    @app.get('/backoffice/tenant-projects', response_class=HTMLResponse)
    def tenant_project_page(user=Depends(current_user), message: str = '', tenant_q: str = '', tenant_status: str = ''):
        try:
            tenants, projects, filters = _items(user, repository, service, tenant_q, tenant_status)
            return HTMLResponse(_render_page(user, tenants, projects, message, filters))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/tenant-projects/tenant-status')
    def tenant_status_page(tenant_id: int = Form(...), status: str = Form(...), user=Depends(current_user)):
        try:
            if not repository:
                raise PermissionDenied('persistent mode required')
            repository.set_tenant_status_for_platform(user, tenant_id, status)
            return RedirectResponse('/backoffice/tenant-projects?message=租户状态已更新', status_code=303)
        except (PermissionDenied, TenantScopeError, ValueError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/tenant-projects/switch')
    def switch_project_page(project_id: int = Form(...), user=Depends(current_user)):
        try:
            if repository:
                project = repository.get_project(project_id)
                if not project or int(project['tenant_id']) != int(user['tenant_id']):
                    raise PermissionDenied('cross tenant project')
            else:
                project = service.projects.get(project_id)
                if not project or project['tenant_id'] != user['tenant_id']:
                    raise PermissionDenied('cross tenant project')
            user.update({'project_id': project['id'], 'project_name': project['name']})
            return RedirectResponse('/backoffice/tenant-projects?message=项目已切换', status_code=303)
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
