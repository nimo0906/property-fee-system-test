#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant admin console pages for SaaS backoffice."""

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page, _render_user_row


def _render_tenant_admin(user, items):
    rows = ''.join(_render_user_row(row) for row in items) or '<tr><td colspan="7">暂无账号</td></tr>'
    body = f'''
<section class="hero"><div><h1>租户管理员控制台</h1><div class="sub">正式商业后台的本公司管理入口。这里仅展示当前公司员工账号，客户上传数据、系统运维数据和其他公司数据保持隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · 本租户视图</div></section>
<section class="grid"><div class="card"><div class="card-h">本公司账号列表</div><div class="card-b"><div class="hint" style="margin-bottom:12px">可在本页直接停用/启用员工账号、重置临时密码；完整搜索、角色筛选、状态筛选和分页请进入 <a class="ghost-link" href="/backoffice/users">账号管理</a>。</div><table><thead><tr><th>ID</th><th>租户</th><th>账号</th><th>角色</th><th>状态</th><th>重置密码</th><th>账号状态</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<aside class="card"><div class="card-h">客户数据隔离</div><div class="card-b"><p class="sub">租户管理员只能管理本公司员工账号；所有账号操作写入本租户审计日志，不记录密码明文。</p><p class="sub">客户上传文件进入租户目录，系统自身部署、备份和运行数据使用独立系统目录，不能与客户业务数据混放。</p><a class="ghost-link" href="/backoffice/audit-logs">查看审计日志</a></div></aside></section>'''
    return _page('租户管理员控制台', body)


def register_tenant_admin_pages(app, service, repository, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/tenant-admin', response_class=HTMLResponse)
    def tenant_admin_page(user=Depends(current_user)):
        try:
            service._require(user, 'manage_users')
            if user.get('role_code') != 'system_admin':
                raise PermissionDenied('tenant admin only')
            items = repository.list_users_for_actor(user) if repository else service.list_staff_users(user, user['project_id'])
            return HTMLResponse(_render_tenant_admin(user, items))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
