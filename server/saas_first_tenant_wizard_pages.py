#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant delivery wizard for SaaS commercial onboarding."""

import urllib.parse

from server.saas_license_binding import bind_tenant_license_customer
from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _delivery_state(message='', tenant_name='', project_name='', license_customer_code=''):
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    summary = ''
    if tenant_name or project_name or license_customer_code:
        summary = f'''<section class="card" style="margin-bottom:18px"><div class="card-h">本次初始化结果</div><div class="card-b"><p class="sub">客户公司：{_h(tenant_name)} · 默认项目：{_h(project_name)} · 授权客户编号：{_h(license_customer_code)}</p><div class="actions"><a class="ghost-link" href="/backoffice/imports/templates/charge-targets">下一步：导入收费对象模板</a><a class="ghost-link" href="/backoffice/fee-types">下一步：配置收费项目</a><a class="ghost-link" href="/backoffice/license-ops">查看授权绑定</a></div></div></section>'''
    steps = ['创建客户公司', '创建默认项目', '创建租户管理员', '绑定授权客户编号', '导入收费对象模板', '配置收费项目', '生成首批测试账单', '登记测试收款', '验收租户隔离', '执行备份恢复演练']
    rows = ''.join(f'<tr><td>{idx}</td><td><strong>{_h(step)}</strong></td><td>待实施人员按客户业务确认</td></tr>' for idx, step in enumerate(steps, 1))
    body = f'''
<section class="hero"><div><h1>客户首租户初始化向导</h1><div class="sub">面向正式商业交付：从空库开通新公司，建立默认项目、首个租户管理员、授权绑定，并引导导入收费对象、配置收费项目、首批测试账单和备份隔离验收。</div></div><div class="badge tenant-scope">平台管理员</div></section>{notice}{summary}
<section class="grid"><div class="card"><div class="card-h">首租户资料</div><div class="card-b"><form method="post" action="/backoffice/first-tenant-wizard/create"><label>客户公司 / 租户名称</label><input name="tenant_name" required placeholder="例如 金桥物业"><label>默认项目名称</label><input name="project_name" required placeholder="例如 金桥一期"><label>项目编码</label><input name="project_code" placeholder="例如 JQ-001"><label>租户管理员账号</label><input name="admin_username" required placeholder="例如 tenant_admin_jq"><label>临时密码</label><input type="password" name="admin_password" required minlength="8"><label>授权客户编号</label><input name="license_customer_code" required placeholder="例如 CUST-JQ-001"><button class="primary">创建首租户并绑定授权</button><div class="hint">临时密码只用于初始化，不在页面、日志或审计明细展示。授权绑定只写系统侧映射，不写客户业务表。</div></form></div></div>
<aside class="card"><div class="card-h">隔离边界</div><div class="card-b"><p class="sub">客户上传数据与系统自身数据隔离。</p><p class="sub">业务数据不进入授权云服务。</p><p class="sub">收费对象、账单、收款、导入和报表都归属新客户公司和项目。</p><p class="sub">授权绑定写入系统侧授权映射，并保留审计。</p></div></aside></section>
<section class="card" style="margin-top:18px"><div class="card-h">交付步骤</div><div class="card-b"><table><thead><tr><th>序号</th><th>步骤</th><th>验收口径</th></tr></thead><tbody>{rows}</tbody></table></div></section>{_business_delivery_loop(bool(summary))}'''
    return _page('客户首租户初始化向导', body)


def _business_delivery_loop(created=False):
    intro = '创建完成后会显示可点击的业务交付路径' if not created else '按下面入口完成首租户从空库到可验收业务闭环'
    items = [
        ('1. 导入收费对象模板', '/backoffice/imports/templates/charge-targets', '下载模板并按客户楼栋/区域、单元/分区、房号/铺位号准备数据。'),
        ('2. 配置收费项目', '/backoffice/fee-types', '配置物业费、水费、停车费等项目，确认单价、计费方式和服务期。'),
        ('3. 生成首批测试账单', '/backoffice/bills', '用少量对象生成测试账单，核对金额、账期、服务期。'),
        ('4. 登记测试收款', '/backoffice/payments', '登记一笔测试收款，验证部分收款、已收和欠费联动。'),
        ('5. 查看欠费/实收报表', '/backoffice/reports', '检查应收、实收、欠费汇总，确认数据只属于当前客户。'),
        ('6. 生成交付验收记录', '/backoffice/first-tenant-acceptance', '留存租户隔离验收、备份恢复演练和客户签收证据。'),
    ]
    rows = ''.join(
        '<tr><td><strong>{}</strong></td><td>{}</td><td><a class="ghost-link" href="{}">进入</a></td></tr>'.format(
            _h(title), _h(desc), _h(href)
        )
        for title, href, desc in items
    )
    return f"""<section class="card" style="margin-top:18px"><div class="card-h">首租户业务引导闭环</div><div class="card-b"><p class="sub">{_h(intro)}；必须覆盖租户隔离验收、备份恢复演练、客户上传数据与系统自身数据隔离。</p><div class="actions" style="margin-bottom:12px"><a class="ghost-link" href="/backoffice/imports">导入收费对象</a><a class="ghost-link" href="/backoffice/fee-types">配置收费项目</a><a class="ghost-link" href="/backoffice/bills">生成首批测试账单</a><a class="ghost-link" href="/backoffice/payments">登记测试收款</a><a class="ghost-link" href="/backoffice/reports">查看欠费/实收报表</a><a class="ghost-link" href="/backoffice/first-tenant-acceptance">生成交付验收记录</a><a class="ghost-link" href="/backoffice/acceptance">商业验收总览</a></div><table><thead><tr><th>步骤</th><th>交付说明</th><th>入口</th></tr></thead><tbody>{rows}</tbody></table></div></section>"""


def _tenant_user_for_name(service, repository, tenant_name, actor):
    tenants = repository.list_tenants() if repository else list(service.tenants.values())
    tenant = next((item for item in tenants if item.get('name') == tenant_name), None)
    if not tenant:
        return None
    tenant_id = tenant.get('id')
    if repository:
        project = next((p for p in repository.list_projects(int(tenant_id)) if int(p.get('tenant_id')) == int(tenant_id)), None)
    else:
        project = next((p for p in service.projects.values() if int(p.get('tenant_id')) == int(tenant_id)), {'id': 0})
    user = dict(actor)
    user.update({'tenant_id': tenant_id, 'project_id': project.get('id') if project else 0, 'tenant_name': tenant_name})
    return user


def register_first_tenant_wizard_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _require_platform(user):
        if user.get('role_code') != 'platform_admin':
            raise PermissionDenied('platform admin only')

    @app.get('/backoffice/first-tenant-wizard', response_class=HTMLResponse)
    def wizard_page(user=Depends(current_user), message: str = '', tenant_name: str = '', project_name: str = '', license_customer_code: str = ''):
        try:
            _require_platform(user)
            return HTMLResponse(_delivery_state(message, tenant_name, project_name, license_customer_code))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/first-tenant-wizard/create')
    def wizard_create(tenant_name: str = Form(...), project_name: str = Form(...), admin_username: str = Form(...), admin_password: str = Form(...), license_customer_code: str = Form(...), project_code: str = Form(''), user=Depends(current_user)):
        try:
            _require_platform(user)
            tenant_name = tenant_name.strip()
            project_name = project_name.strip()
            customer_code = license_customer_code.strip()
            if repository:
                repository.onboard_tenant_for_platform(user, tenant_name, project_name, admin_username.strip(), admin_password, project_code.strip() or None)
            else:
                tenant_id = service.create_tenant(tenant_name)
                project_id = service.create_project(tenant_id, project_name)
                service.create_user(tenant_id, admin_username.strip(), 'system_admin')['project_id'] = project_id
            tenant_user = _tenant_user_for_name(service, repository, tenant_name, user)
            if not tenant_user:
                raise HTTPException(status_code=404, detail='tenant not found')
            bind_tenant_license_customer(service, repository, tenant_user, customer_code)
            query = urllib.parse.urlencode({'message': '首租户已创建并绑定授权', 'tenant_name': tenant_name, 'project_name': project_name, 'license_customer_code': customer_code})
            return RedirectResponse(f'/backoffice/first-tenant-wizard?{query}', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
