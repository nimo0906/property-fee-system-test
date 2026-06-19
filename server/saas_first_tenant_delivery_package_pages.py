#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant delivery package overview page."""

from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page

ENTRIES = [
    ('登录入口', '/login', '实施人员和客户员工进入正式商业云端后台。'),
    ('客户首租户初始化向导', '/backoffice/first-tenant-wizard', '创建客户公司、默认项目、租户管理员并绑定授权。'),
    ('首租户业务引导闭环', '/backoffice/first-tenant-wizard', '导入模板、收费项目、测试账单、测试收款、报表和验收记录。'),
    ('首租户交付验收记录', '/backoffice/first-tenant-acceptance', '勾选上线交付项，留存实施人员和客户签收人。'),
    ('验收记录打印版', '/backoffice/first-tenant-acceptance/print', '打印客户签收材料。'),
    ('HTML 导出', '/backoffice/first-tenant-acceptance/export.html', '导出可归档的 HTML 验收记录。'),
    ('生产部署一键自检', '/backoffice/deploy-checklist', '执行服务器、端口、目录、Docker、Nginx、systemd、备份和证据检查。'),
    ('备份恢复演练', '/backoffice/backups', '创建备份记录并提交恢复演练。'),
    ('授权绑定', '/backoffice/license-ops', '平台管理员绑定 SaaS 租户与授权客户编号。'),
    ('租户隔离证据', '/backoffice/data-boundaries', '验证客户上传数据与系统自身数据隔离，业务数据按公司隔离。'),
]


def _entry_rows():
    return ''.join(
        f'<tr><td><strong>{_h(name)}</strong></td><td>{_h(desc)}</td><td><a class="ghost-link" href="{_h(href)}">进入</a></td></tr>'
        for name, href, desc in ENTRIES
    )


def _render(user):
    body = f'''
<section class="hero"><div><h1>首租户交付包总览</h1><div class="sub">实施人员统一入口：把登录、初始化向导、业务闭环、验收记录、打印导出、部署自检、备份恢复、授权绑定和租户隔离证据集中在一个页面，减少真实交付时漏项。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">交付边界</div><div class="card-b"><p class="sub">客户上传数据与系统自身数据隔离；业务数据不进入授权云服务；平台管理员负责客户开通、授权绑定和交付证据，租户管理员负责本公司业务数据。</p><div class="actions"><a class="ghost-link" href="/backoffice/first-tenant-wizard">开始首租户初始化</a><a class="ghost-link" href="/backoffice/first-tenant-acceptance">填写验收记录</a><a class="ghost-link" href="/backoffice/deploy-checklist">查看部署自检</a></div></div></section>
<section class="card"><div class="card-h">实施人员统一入口</div><div class="card-b"><table><thead><tr><th>入口</th><th>用途</th><th>操作</th></tr></thead><tbody>{_entry_rows()}</tbody></table></div></section>'''
    return _page('首租户交付包总览', body)


def register_first_tenant_delivery_package_pages(app, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    def _require_admin(user):
        if user.get('role_code') not in {'platform_admin', 'system_admin'}:
            raise PermissionDenied('admin only')

    @app.get('/backoffice/first-tenant-delivery-package', response_class=HTMLResponse)
    def delivery_package_page(user=Depends(current_user)):
        try:
            _require_admin(user)
            return HTMLResponse(_render(user))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
