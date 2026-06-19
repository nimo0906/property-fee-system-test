#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML charge target management pages for SaaS backoffice."""

import urllib.parse

from server.saas_business_closure import render_business_closure
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


FILTER_KEYS = ('building', 'unit', 'room_number', 'category')


def _render_targets(user, items, message='', filters=None, page=1, page_size=20, total=0, owners=None):
    filters = filters or {}
    owners = owners or []
    rows = ''.join(_row(item) for item in items) or '<tr><td colspan="9">暂无收费对象</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    form = _create_form(owners) if can_write else '<div class="hint">当前角色只能查看收费对象，不能新增。</div>'
    pager = _pager(filters, page, page_size, total)
    body = f'''
<section class="hero"><div><h1>收费对象管理</h1><div class="sub">统一维护楼栋 / 区域、单元 / 分区、房号 / 铺位号，并建立房间/铺位与业主的云端映射。所有数据按当前租户和项目隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{render_business_closure('charge_targets')}
{_filter_form(filters, page_size)}
<section class="grid"><div class="card"><div class="card-h">收费对象列表</div><div class="card-b">{pager}<table><thead><tr><th>ID</th><th>楼栋 / 区域</th><th>单元 / 分区</th><th>房号 / 铺位号</th><th>业主</th><th>联系电话</th><th>类型</th><th>面积</th><th>独立单价</th></tr></thead><tbody>{rows}</tbody></table>{pager}</div></div>
<aside class="card"><div class="card-h">新增收费对象</div><div class="card-b">{form}</div></aside></section>'''
    return _page('收费对象管理', body)


def _row(item):
    override = item.get('unit_price_override')
    price = '-' if override in (None, '') else override
    return f'''<tr><td>{_h(item.get('id'))}</td><td>{_h(item.get('building'))}</td><td>{_h(item.get('unit'))}</td><td><strong>{_h(item.get('room_number'))}</strong></td><td>{_h(item.get('owner_name') or '未绑定')}</td><td>{_h(item.get('owner_phone') or '')}</td><td>{_h(item.get('category'))}</td><td>{_h(item.get('area'))}</td><td>{_h(price)}</td></tr>'''


def _filter_form(filters, page_size):
    category = filters.get('category', '')
    options = ''.join(
        f'<option value="{_h(value)}"{" selected" if category == value else ""}>{_h(label)}</option>'
        for value, label in [('', '全部类型'), ('居民', '居民'), ('商户', '商户'), ('办公', '办公'), ('其他', '其他')]
    )
    page_size_options = ''.join(
        f'<option value="{n}"{" selected" if int(page_size) == n else ""}>{n}</option>'
        for n in [10, 20, 50]
    )
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">筛选收费对象</div><div class="card-b"><form method="get" action="/backoffice/charge-targets" class="filters"><input type="hidden" name="page" value="1"><div><label>楼栋 / 区域</label><input name="building" value="{_h(filters.get('building'))}" placeholder="楼栋或区域关键词"></div><div><label>单元 / 分区</label><input name="unit" value="{_h(filters.get('unit'))}" placeholder="单元或分区关键词"></div><div><label>房号 / 铺位号</label><input name="room_number" value="{_h(filters.get('room_number'))}" placeholder="房号关键词"></div><div><label>类型</label><select name="category">{options}</select></div><div><label>每页数量</label><select name="page_size">{page_size_options}</select></div><div><button class="primary">筛选</button></div></form></div></section>'''


def _create_form(owners):
    owner_options = '<option value="0">未绑定业主</option>' + ''.join(f'<option value="{_h(o.get("id"))}">{_h(o.get("name"))} {_h(o.get("phone"))}</option>' for o in owners)
    return f'''<form method="post" action="/backoffice/owners/create"><label>业主</label><input name="name" required placeholder="业主/商户姓名"><label>联系电话</label><input name="phone" placeholder="手机号"><label>类型</label><select name="owner_type"><option value="业主">业主</option><option value="住户">住户</option><option value="商户">商户</option></select><button class="ghost">新增业主</button><div class="hint">新增后可在下方绑定业主。</div></form><hr><form method="post" action="/backoffice/charge-targets/create"><label>绑定业主</label><select name="owner_id">{owner_options}</select><label>楼栋 / 区域</label><input name="building" required placeholder="例如 住宅楼 / 商业区A"><label>单元 / 分区</label><input name="unit" placeholder="例如 1单元 / 一层"><label>房号 / 铺位号</label><input name="room_number" required placeholder="例如 101 / A-101"><label>类型</label><select name="category"><option value="居民">居民</option><option value="商户">商户</option><option value="办公">办公</option><option value="其他">其他</option></select><label>面积</label><input name="area" required type="number" step="0.01" min="0.01" placeholder="建筑面积"><label>独立单价</label><input name="unit_price_override" type="number" step="0.01" min="0" placeholder="选填，覆盖收费项目单价"><button class="primary">新增对象</button><div class="hint">房间/铺位与业主建立绑定后，后续批量出账、欠费报表可按业主追踪；独立单价用于商户/铺位差异化收费。</div></form>'''


def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _normalize_filters(building='', unit='', room_number='', category='', page=1, page_size=20):
    filters = {k: str(v or '').strip() for k, v in {'building': building, 'unit': unit, 'room_number': room_number, 'category': category}.items()}
    if filters['category'] not in {'', '居民', '商户', '办公', '其他'}:
        filters['category'] = ''
    page = max(_to_int(page, 1), 1)
    page_size = min(max(_to_int(page_size, 20), 1), 50)
    return filters, page, page_size


def _filter_items(items, filters):
    rows = []
    for item in items:
        if filters.get('building') and filters['building'].lower() not in str(item.get('building', '')).lower():
            continue
        if filters.get('unit') and filters['unit'].lower() not in str(item.get('unit', '')).lower():
            continue
        if filters.get('room_number') and filters['room_number'].lower() not in str(item.get('room_number', '')).lower():
            continue
        if filters.get('category') and item.get('category') != filters['category']:
            continue
        rows.append(item)
    return rows


def _paginate(items, page, page_size):
    total = len(items)
    start = (page - 1) * page_size
    return items[start:start + page_size], total


def _query(filters, page, page_size):
    params = {key: value for key, value in filters.items() if value}
    params['page'] = str(page)
    params['page_size'] = str(page_size)
    return urllib.parse.urlencode(params)


def _pager(filters, page, page_size, total):
    prev_link = f'<a class="ghost-link" href="/backoffice/charge-targets?{_query(filters, page - 1, page_size)}">上一页</a>' if page > 1 else '<span class="ghost-link disabled">上一页</span>'
    next_link = f'<a class="ghost-link" href="/backoffice/charge-targets?{_query(filters, page + 1, page_size)}">下一页</a>' if page * page_size < total else '<span class="ghost-link disabled">下一页</span>'
    return f'<div class="pager"><span>共 {total} 个收费对象 · 第 {page} 页</span><span>{prev_link} {next_link}</span></div>'


def register_charge_target_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _items_for(user):
        service._require(user, 'read')
        return repository.list_charge_targets(user['tenant_id'], user['project_id']) if repository else service.list_charge_targets(user, user['project_id'])

    @app.get('/backoffice/charge-targets', response_class=HTMLResponse)
    def charge_target_page(user=Depends(current_user), message: str = '', building: str = '', unit: str = '', room_number: str = '', category: str = '', page: int = 1, page_size: int = 20):
        try:
            filters, page, page_size = _normalize_filters(building, unit, room_number, category, page, page_size)
            filtered = _filter_items(_items_for(user), filters)
            visible, total = _paginate(filtered, page, page_size)
            owners = repository.list_owners(user['tenant_id'], user['project_id']) if repository else service.list_owners(user, user['project_id'])
            return HTMLResponse(_render_targets(user, visible, message, filters, page, page_size, total, owners))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/owners/create')
    def create_owner_page(name: str = Form(...), phone: str = Form(''), owner_type: str = Form('业主'), user=Depends(current_user)):
        try:
            service._require(user, 'write')
            if repository:
                item = repository.create_owner(user['tenant_id'], user['project_id'], name, phone, owner_type)
                service._log(user, user['project_id'], 'owner.create', 'owner', item['id'], {'name': name, 'phone': phone, 'owner_type': owner_type})
            else:
                service.create_owner(user, user['project_id'], name, phone, owner_type)
            return RedirectResponse('/backoffice/charge-targets?message=业主已新增', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/charge-targets/create')
    def create_charge_target_page(building: str = Form(...), unit: str = Form(''), room_number: str = Form(...), category: str = Form('居民'), area: float = Form(...), owner_id: int = Form(0), unit_price_override: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'write')
            if repository:
                item = repository.create_charge_target(user['tenant_id'], user['project_id'], building, unit, room_number, category, area, owner_id, unit_price_override or None)
                service._log(user, user['project_id'], 'charge_target.create', 'charge_target', item['id'], {'building': building, 'room_number': room_number})
            else:
                service.create_charge_target(user, user['project_id'], building, unit, room_number, category, area, owner_id, unit_price_override or None)
            return RedirectResponse('/backoffice/charge-targets?message=收费对象已新增', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
