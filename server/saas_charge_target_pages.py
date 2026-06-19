#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML charge target management pages for SaaS backoffice."""

from server.saas_business_closure import render_business_closure
from server.saas_user_pages import _h, _page
from server.saas_service import PermissionDenied


def _render_targets(user, items, message=''):
    rows = ''.join(_row(item) for item in items) or '<tr><td colspan="6">暂无收费对象</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    form = _create_form() if can_write else '<div class="hint">当前角色只能查看收费对象，不能新增。</div>'
    body = f'''
<section class="hero"><div><h1>收费对象管理</h1><div class="sub">统一维护楼栋 / 区域、单元 / 分区、房号 / 铺位号。所有数据按当前租户和项目隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{render_business_closure('charge_targets')}
<section class="grid"><div class="card"><div class="card-h">收费对象列表</div><div class="card-b"><table><thead><tr><th>ID</th><th>楼栋 / 区域</th><th>单元 / 分区</th><th>房号 / 铺位号</th><th>类型</th><th>面积</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<aside class="card"><div class="card-h">新增收费对象</div><div class="card-b">{form}</div></aside></section>'''
    return _page('收费对象管理', body)


def _row(item):
    return f'''<tr><td>{_h(item.get('id'))}</td><td>{_h(item.get('building'))}</td><td>{_h(item.get('unit'))}</td><td><strong>{_h(item.get('room_number'))}</strong></td><td>{_h(item.get('category'))}</td><td>{_h(item.get('area'))}</td></tr>'''


def _create_form():
    return '''<form method="post" action="/backoffice/charge-targets/create"><label>楼栋 / 区域</label><input name="building" required placeholder="例如 住宅楼 / 商业区A"><label>单元 / 分区</label><input name="unit" placeholder="例如 1单元 / 一层"><label>房号 / 铺位号</label><input name="room_number" required placeholder="例如 101 / A-101"><label>类型</label><select name="category"><option value="居民">居民</option><option value="商户">商户</option><option value="办公">办公</option><option value="其他">其他</option></select><label>面积</label><input name="area" required type="number" step="0.01" min="0.01" placeholder="建筑面积"><button class="primary">新增对象</button><div class="hint">第一版保持通用结构，后续按不同行业扩展字段。</div></form>'''


def register_charge_target_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _items_for(user):
        service._require(user, 'read')
        return repository.list_charge_targets(user['tenant_id'], user['project_id']) if repository else service.list_charge_targets(user, user['project_id'])

    @app.get('/backoffice/charge-targets', response_class=HTMLResponse)
    def charge_target_page(user=Depends(current_user), message: str = ''):
        try:
            return HTMLResponse(_render_targets(user, _items_for(user), message))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/charge-targets/create')
    def create_charge_target_page(building: str = Form(...), unit: str = Form(''), room_number: str = Form(...), category: str = Form('居民'), area: float = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'write')
            if repository:
                item = repository.create_charge_target(user['tenant_id'], user['project_id'], building, unit, room_number, category, area)
                service._log(user, user['project_id'], 'charge_target.create', 'charge_target', item['id'], {'building': building, 'room_number': room_number})
            else:
                service.create_charge_target(user, user['project_id'], building, unit, room_number, category, area)
            return RedirectResponse('/backoffice/charge-targets?message=收费对象已新增', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
