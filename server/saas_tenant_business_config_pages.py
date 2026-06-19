#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant business configuration page for SaaS backoffice."""

from server.saas_business_templates import render_template_summary, template_options
from server.saas_service import PermissionDenied
from server.saas_tenant_business_config import business_template_for_user, save_tenant_business_template
from server.saas_user_pages import _h, _page


_WRITE_ROLES = {'system_admin', 'platform_admin'}


def _render_business_config_page(user, service, repository, message=''):
    current = business_template_for_user(service, repository, user)
    can_write = user.get('role_code') in _WRITE_ROLES
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    form = (
        f'''<form method="post" action="/backoffice/tenant-business-config"><label>业务模板</label><select name="business_template">{template_options(current['code'])}</select><button class="primary">保存业务配置</button></form><div class="hint">保存后仅影响当前客户公司；导入模板会默认按本公司业务模板显示。</div>'''
        if can_write else '<div class="hint">当前角色只能查看业务配置，不能修改本公司业务模板。</div>'
    )
    body = f'''
<section class="hero"><div><h1>业务配置</h1><div class="sub">不同公司业务不同，本页保存当前客户公司的业务模板；客户上传数据、系统自身配置和授权服务继续分开存放。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>{notice}
<section class="grid"><div class="card"><div class="card-h">当前业务模板</div><div class="card-b"><p class="sub"><strong>{_h(current['name'])}</strong></p><p class="sub">推荐收费项目：{_h('、'.join(current['fees']))}</p><p class="sub">账单周期：{_h(current['cycle'])}</p>{form}</div></div>
<aside class="card"><div class="card-h">隔离边界</div><div class="card-b"><p class="sub">业务配置按当前客户公司保存，不允许跨公司读取或修改。</p><p class="sub">配置文件属于系统侧数据，不进入客户上传目录，不进入授权云服务。</p><p class="sub">页面和导出不展示内部编号、生产密钥或服务器路径。</p></div></aside></section>
{render_template_summary(current['code'])}'''
    return _page('业务配置', body)


def register_tenant_business_config_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    @app.get('/backoffice/tenant-business-config', response_class=HTMLResponse)
    def business_config_page(user=Depends(current_user), message: str = ''):
        return HTMLResponse(_render_business_config_page(user, service, repository, message))

    @app.post('/backoffice/tenant-business-config')
    def update_business_config(business_template: str = Form(...), user=Depends(current_user)):
        try:
            if user.get('role_code') not in _WRITE_ROLES:
                raise PermissionDenied('tenant business config write denied')
            save_tenant_business_template(service, repository, user, business_template)
            return RedirectResponse('/backoffice/tenant-business-config?message=业务配置已保存', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
