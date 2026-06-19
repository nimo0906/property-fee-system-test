#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Platform license operations page for SaaS tenants."""

from server.saas_license_binding import bind_tenant_license_customer, license_customer_code_for_tenant
from server.saas_license_seats import active_staff_count
from server.saas_license_status import build_saas_license_status
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page

PRODUCT_CODE = 'property-saas-backoffice'


def build_license_ops_rows(service, repository, license_service):
    tenant_map = {str(t.get('name') or ''): t for t in _tenant_items(service, repository)}
    for customer in _license_customers(license_service):
        name = str(customer.get('customer_code') or customer.get('name') or '')
        tenant_map.setdefault(name, {'name': name, 'id': None})
    rows = []
    for tenant_name in sorted(name for name in tenant_map if name):
        tenant = tenant_map[tenant_name]
        customer_code = license_customer_code_for_tenant(service, repository, tenant)
        if not customer_code and tenant.get('id') is None:
            customer_code = tenant_name
        status = build_saas_license_status(license_service, customer_code)
        active_count = _active_count_for_tenant(service, repository, tenant)
        seats = int(status.get('seats') or 0)
        rows.append({
            'tenant_name': tenant_name,
            'status_label': '已授权' if status.get('allowed') else _status_label(status.get('status')),
            'customer_code': customer_code or '未绑定',
            'binding_label': _binding_label(tenant, customer_code),
            'licensed_seats': seats,
            'active_staff_count': active_count,
            'expires_at': status.get('expires_at') or '未配置',
            'risk_label': _risk_label(status.get('allowed'), seats, active_count),
        })
    return rows


def _license_customers(license_service):
    if not license_service or not hasattr(license_service, 'list_customers'):
        return []
    return license_service.list_customers()


def _active_count_for_tenant(service, repository, tenant):
    if tenant.get('id') is None:
        return 0
    return active_staff_count(service, repository, _tenant_probe_user(service, repository, tenant))


def register_license_ops_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    @app.get('/backoffice/license-ops', response_class=HTMLResponse)
    def license_ops_page(user=Depends(current_user)):
        if user.get('role_code') != 'platform_admin':
            raise HTTPException(status_code=403, detail='forbidden')
        rows = build_license_ops_rows(service, repository, getattr(app.state, 'license_service', None))
        return HTMLResponse(_render_page(rows))

    @app.post('/backoffice/license-ops/bind')
    def bind_license_customer(tenant_name: str = Form(...), customer_code: str = Form(...), user=Depends(current_user)):
        if user.get('role_code') != 'platform_admin':
            raise HTTPException(status_code=403, detail='forbidden')
        tenant_user = _binding_user_for_tenant(service, repository, tenant_name.strip(), user)
        if not tenant_user:
            raise HTTPException(status_code=404, detail='tenant not found')
        bind_tenant_license_customer(service, repository, tenant_user, customer_code.strip())
        return RedirectResponse('/backoffice/license-ops?message=授权客户已绑定', status_code=303)


def _tenant_items(service, repository):
    if repository:
        return repository.list_tenants()
    return list(service.tenants.values())


def _tenant_probe_user(service, repository, tenant):
    tenant_id = tenant.get('id')
    if repository:
        project = next((p for p in repository.list_projects(int(tenant_id)) if int(p.get('tenant_id')) == int(tenant_id)), None)
        return {'tenant_id': tenant_id, 'project_id': project.get('id') if project else 0, 'role_code': 'platform_admin'}
    project = next((p for p in service.projects.values() if int(p.get('tenant_id')) == int(tenant_id)), {'id': 0})
    return {'tenant_id': tenant_id, 'project_id': project.get('id'), 'role_code': 'platform_admin'}


def _binding_user_for_tenant(service, repository, tenant_name, actor):
    tenant = next((item for item in _tenant_items(service, repository) if item.get('name') == tenant_name), None)
    if not tenant:
        return None
    probe = _tenant_probe_user(service, repository, tenant)
    user = dict(actor)
    user.update({
        'tenant_id': probe.get('tenant_id'),
        'project_id': probe.get('project_id'),
        'tenant_name': tenant_name,
    })
    return user


def _render_page(rows):
    table_rows = ''.join(_row(item) for item in rows) or '<tr><td colspan="7">暂无租户</td></tr>'
    form = '''<section class="card" style="margin-bottom:18px"><div class="card-h">绑定授权客户</div><div class="card-b"><form method="post" action="/backoffice/license-ops/bind" class="filters"><div><label>客户公司</label><input name="tenant_name" required placeholder="SaaS 租户名称"></div><div><label>授权客户编号</label><input name="customer_code" required placeholder="license customer_code"></div><div><button class="primary">绑定授权客户</button></div></form><div class="hint">绑定只写入授权映射和租户范围审计，不写入客户业务数据。</div></div></section>'''
    body = f'''<section class="hero"><div><h1>授权状态运维</h1><div class="sub">平台管理员查看各租户授权状态、席位使用、到期时间和超限风险；不展示业务数据、授权库内部字段或生产密钥。</div></div><div class="badge tenant-scope">平台运维视图</div></section>
{form}<section class="card"><div class="card-h">授权租户概览</div><div class="card-b"><table><thead><tr><th>客户公司</th><th>授权客户</th><th>绑定状态</th><th>授权状态</th><th>席位使用</th><th>到期时间</th><th>超限风险</th></tr></thead><tbody>{table_rows}</tbody></table></div></section>'''
    return _page('授权状态运维', body)


def _row(item):
    seats = f"{item.get('active_staff_count')} / {item.get('licensed_seats')}"
    return f'''<tr><td><strong>{_h(item.get('tenant_name'))}</strong></td><td>{_h(item.get('customer_code'))}</td><td>{_h(item.get('binding_label'))}</td><td>{_h(item.get('status_label'))}</td><td>{_h(seats)}</td><td>{_h(item.get('expires_at'))}</td><td>{_h(item.get('risk_label'))}</td></tr>'''


def _binding_label(tenant, customer_code):
    if tenant.get('id') is None and customer_code:
        return '仅授权客户'
    return '已绑定' if customer_code else '未绑定'


def _risk_label(allowed, seats, active_count):
    if not allowed:
        return '未授权风险'
    if seats and active_count > seats:
        return '已超限'
    if seats and active_count == seats:
        return '正常'
    return '正常'


def _status_label(value):
    return {'missing': '未授权', 'not_configured': '未接入授权服务', 'inactive': '已停用'}.get(str(value or ''), str(value or '未知'))
