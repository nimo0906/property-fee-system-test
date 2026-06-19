#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML fee type management pages for SaaS backoffice."""

from server.saas_business_closure import render_business_closure
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _render_fee_types(user, items, message=''):
    rows = ''.join(_row(item) for item in items) or '<tr><td colspan="3">暂无收费项目</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    form = _create_form() if can_write else '<div class="hint">当前角色只能查看收费项目，不能新增或修改价格规则。</div>'
    body = f'''
<section class="hero"><div><h1>收费项目管理</h1><div class="sub">配置物业费、水费、停车费等通用收费项目和单价。所有价格规则按当前租户和项目隔离保存。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{render_business_closure('fee_types')}
<section class="grid"><div class="card"><div class="card-h">收费项目列表</div><div class="card-b"><table><thead><tr><th>ID</th><th>收费项目</th><th>单价</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<aside class="card"><div class="card-h">新增收费项目</div><div class="card-b">{form}</div></aside></section>'''
    return _page('收费项目管理', body)


def _row(item):
    return f'''<tr><td>{_h(item.get('id'))}</td><td><strong>{_h(item.get('name'))}</strong></td><td>{_h(item.get('unit_price'))}</td></tr>'''


def _create_form():
    return '''<form method="post" action="/backoffice/fee-types/create"><label>收费项目名称</label><input name="name" required placeholder="例如 物业费 / 水费 / 停车费"><label>单价</label><input name="unit_price" required type="number" step="0.01" min="0" placeholder="例如 2.50"><button class="primary">新增收费项目</button><div class="hint">第一版先按项目维护基础单价，后续再扩展阶梯价和行业差异规则。</div></form>'''


def register_fee_type_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _items_for(user):
        service._require(user, 'read')
        if repository:
            return repository.list_fee_types(user['tenant_id'], user['project_id'])
        return service.list_fee_types(user, user['project_id'])

    @app.get('/backoffice/fee-types', response_class=HTMLResponse)
    def fee_type_page(user=Depends(current_user), message: str = ''):
        try:
            return HTMLResponse(_render_fee_types(user, _items_for(user), message))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/fee-types/create')
    def create_fee_type_page(name: str = Form(...), unit_price: float = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'write')
            if repository:
                item = repository.create_fee_type(user['tenant_id'], user['project_id'], name, unit_price)
                service._log(user, user['project_id'], 'fee_type.create', 'fee_type', item['id'], {'name': name, 'unit_price': float(unit_price)})
            else:
                service.create_fee_type(user, user['project_id'], name, unit_price)
            return RedirectResponse('/backoffice/fee-types?message=收费项目已新增', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
