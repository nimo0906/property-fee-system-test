#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Platform tenant onboarding pages for SaaS backoffice."""

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _render_onboarding(message=''):
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    body = f'''
<section class="hero"><div><h1>平台客户开通</h1><div class="sub">平台管理员为新客户公司开通租户、默认项目和首个租户管理员。客户业务数据会写入新租户，不与平台自身数据混放。</div></div><div class="badge tenant-scope">平台管理员</div></section>{notice}
<section class="grid"><div class="card"><div class="card-h">新客户资料</div><div class="card-b"><form method="post" action="/backoffice/tenant-onboarding/create"><label>客户公司 / 租户名称</label><input name="tenant_name" required placeholder="例如 金桥物业"><label>默认项目名称</label><input name="project_name" required placeholder="例如 金桥一期"><label>项目编码</label><input name="project_code" placeholder="例如 JQ-001"><label>租户管理员账号</label><input name="admin_username" required placeholder="例如 tenant_admin_jq"><label>临时密码</label><input type="password" name="admin_password" required minlength="8"><button class="primary">开通客户</button><div class="hint">密码只保存哈希；页面和审计不展示明文。开通后请让客户管理员登录并及时修改密码。</div></form></div></div>
<aside class="card"><div class="card-h">隔离说明</div><div class="card-b"><p class="sub">开通动作会创建独立 tenant_id、project_id 和 system_admin 账号。</p><p class="sub">后续收费对象、账单、收款、导入和报表都按新租户/项目隔离。</p><a class="ghost-link" href="/backoffice/tenant-projects">查看租户项目</a></div></aside></section>'''
    return _page('平台客户开通', body)


def register_tenant_onboarding_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _require_platform(user):
        if user.get('role_code') != 'platform_admin':
            raise PermissionDenied('platform admin only')

    @app.get('/backoffice/tenant-onboarding', response_class=HTMLResponse)
    def onboarding_page(user=Depends(current_user), message: str = ''):
        try:
            _require_platform(user)
            return HTMLResponse(_render_onboarding(message))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/tenant-onboarding/create')
    def create_onboarding_page(tenant_name: str = Form(...), project_name: str = Form(...), admin_username: str = Form(...), admin_password: str = Form(...), project_code: str = Form(''), user=Depends(current_user)):
        try:
            _require_platform(user)
            if repository:
                repository.onboard_tenant_for_platform(user, tenant_name.strip(), project_name.strip(), admin_username.strip(), admin_password, project_code.strip() or None)
            else:
                tenant_id = service.create_tenant(tenant_name.strip())
                project_id = service.create_project(tenant_id, project_name.strip())
                service.create_user(tenant_id, admin_username.strip(), 'system_admin')['project_id'] = project_id
            return RedirectResponse('/backoffice/tenant-onboarding?message=客户已开通', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
