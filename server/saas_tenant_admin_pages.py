#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant admin console pages for SaaS backoffice."""

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import (
    _filter_users, _h, _normalize_filters, _page, _render_user_row,
)


def _render_filter_form(filters):
    role_options = ''.join(
        f'<option value="{_h(code)}"{" selected" if filters.get("role_code") == code else ""}>{_h(name)}</option>'
        for code, name in [('', '全部角色'), ('system_admin', '租户管理员'), ('finance', '财务'), ('cashier', '收费员'), ('frontdesk', '客服业务编辑'), ('executive', '管理层只读')]
    )
    active_options = ''.join(
        f'<option value="{val}"{" selected" if filters.get("is_active") == val else ""}>{label}</option>'
        for val, label in [('', '全部状态'), ('1', '仅启用'), ('0', '仅停用')]
    )
    return f'''<form method="get" action="/backoffice/tenant-admin" class="filters" style="grid-template-columns:repeat(4,minmax(0,1fr))"><div><label>关键字</label><input name="q" value="{_h(filters.get('q', ''))}" placeholder="本公司账号关键词"></div><div><label>角色</label><select name="role_code">{role_options}</select></div><div><label>状态</label><select name="is_active">{active_options}</select></div><div><button class="primary">筛选本公司账号</button></div></form>'''


def _render_tenant_admin(user, items, filters=None):
    filters = filters or {}
    current_user_id = user.get('id')
    rows = ''.join(_render_user_row(row, current_user_id) for row in items) or '<tr><td colspan="7">暂无账号</td></tr>'
    filter_form = _render_filter_form(filters)
    body = f'''
<section class="hero"><div><h1>租户管理员控制台</h1><div class="sub">正式商业后台的本公司管理入口。这里仅展示当前公司员工账号，客户上传数据、系统运维数据和其他公司数据保持隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · 本租户视图</div></section>
<section class="grid"><div class="card"><div class="card-h">本公司账号列表</div><div class="card-b"><div class="hint" style="margin-bottom:12px">可在本页直接停用/启用员工账号、重置临时密码；更多分页能力请进入 <a class="ghost-link" href="/backoffice/users">账号管理</a>。</div>{filter_form}<table><thead><tr><th>ID</th><th>租户</th><th>账号</th><th>角色</th><th>状态</th><th>重置密码</th><th>账号状态</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<aside class="card"><div class="card-h">客户数据隔离</div><div class="card-b"><p class="sub">租户管理员只能管理本公司员工账号；所有账号操作写入本租户审计日志，不记录密码明文。</p><p class="sub">客户上传文件进入租户目录，系统自身部署、备份和运行数据使用独立系统目录，不能与客户业务数据混放。</p><a class="ghost-link" href="/backoffice/audit-logs">查看审计日志</a></div></aside></section>'''
    return _page('租户管理员控制台', body)


def register_tenant_admin_pages(app, service, repository, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/tenant-admin', response_class=HTMLResponse)
    def tenant_admin_page(user=Depends(current_user), q: str = '', role_code: str = '', is_active: str = ''):
        try:
            service._require(user, 'manage_users')
            if user.get('role_code') != 'system_admin':
                raise PermissionDenied('tenant admin only')
            q, role_code, is_active, _page_num, page_size, _tenant_name = _normalize_filters(q, role_code, is_active, 1, 50)
            items = repository.list_users_for_actor(user) if repository else service.list_staff_users(user, user['project_id'])
            items = _filter_users(items, q=q, role_code=role_code, is_active=is_active)[:page_size]
            filters = {'q': q, 'role_code': role_code, 'is_active': is_active}
            return HTMLResponse(_render_tenant_admin(user, items, filters=filters))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
