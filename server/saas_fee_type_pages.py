#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML fee type management pages for SaaS backoffice."""

import urllib.parse

from server.saas_business_closure import render_business_closure
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _render_fee_types(user, items, message='', filters=None, page=1, page_size=20, total=0):
    filters = filters or {}
    rows = ''.join(_row(item) for item in items) or '<tr><td colspan="5">暂无收费项目</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    form = _create_form() if can_write else '<div class="hint">当前角色只能查看收费项目，不能新增或修改价格规则。</div>'
    pager = _pager(filters, page, page_size, total)
    body = f'''
<section class="hero"><div><h1>收费项目管理</h1><div class="sub">配置物业费、水费、停车费等通用收费项目和单价。所有价格规则按当前租户和项目隔离保存。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{render_business_closure('fee_types')}
{_filter_form(filters, page_size)}
<section class="grid"><div class="card"><div class="card-h">收费项目列表</div><div class="card-b">{pager}<table><thead><tr><th>ID</th><th>收费项目</th><th>单价</th><th>计费方式</th><th>价格配置</th></tr></thead><tbody>{rows}</tbody></table>{pager}</div></div>
<aside class="card"><div class="card-h">新增收费项目</div><div class="card-b">{form}</div></aside></section>'''
    return _page('收费项目管理', body)


def _money(value):
    try:
        return f'¥{float(value):.2f}'
    except Exception:
        return '¥0.00'


def _billing_mode_label(mode):
    return '固定金额' if mode == 'fixed' else '按面积'


def _row(item):
    label = _billing_mode_label(item.get('billing_mode'))
    hint = '每个房间/铺位按固定金额出账' if item.get('billing_mode') == 'fixed' else '按面积 × 单价出账'
    return f'''<tr><td>{_h(item.get('id'))}</td><td><strong>{_h(item.get('name'))}</strong></td><td>{_h(_money(item.get('unit_price')))}</td><td>{_h(label)}</td><td><span class="badge">{_h(label)}</span><div class="hint">{_h(hint)}</div></td></tr>'''


def _filter_form(filters, page_size):
    page_size_options = ''.join(
        f'<option value="{n}"{" selected" if int(page_size) == n else ""}>{n}</option>'
        for n in [10, 20, 50]
    )
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">筛选收费项目</div><div class="card-b"><form method="get" action="/backoffice/fee-types" class="filters"><input type="hidden" name="page" value="1"><div><label>项目关键词</label><input name="keyword" value="{_h(filters.get('keyword'))}" placeholder="物业费 / 水费 / 停车费"></div><div><label>最低单价</label><input name="price_min" type="number" step="0.01" min="0" value="{_h(filters.get('price_min'))}"></div><div><label>最高单价</label><input name="price_max" type="number" step="0.01" min="0" value="{_h(filters.get('price_max'))}"></div><div><label>每页数量</label><select name="page_size">{page_size_options}</select></div><div><button class="primary">筛选</button></div></form></div></section>'''


def _create_form():
    return '''<form method="post" action="/backoffice/fee-types/create"><label>收费项目名称</label><input name="name" required placeholder="例如 物业费 / 水费 / 停车费"><label>单价 / 固定金额</label><input name="unit_price" required type="number" step="0.01" min="0" placeholder="例如 2.50"><label>计费方式</label><select name="billing_mode"><option value="area">按面积</option><option value="fixed">固定金额</option></select><button class="primary">新增收费项目</button><div class="hint">基础单价支持两种计费方式：按面积表示 面积 × 单价；固定金额表示每个房间/铺位直接按该金额出账。</div></form>'''


def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _normalize_filters(keyword='', price_min='', price_max='', page=1, page_size=20):
    filters = {
        'keyword': str(keyword or '').strip(),
        'price_min': str(price_min or '').strip(),
        'price_max': str(price_max or '').strip(),
    }
    page = max(_to_int(page, 1), 1)
    page_size = min(max(_to_int(page_size, 20), 1), 50)
    return filters, page, page_size


def _as_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _filter_items(items, filters):
    price_min = _as_float(filters.get('price_min'))
    price_max = _as_float(filters.get('price_max'))
    keyword = filters.get('keyword', '').lower()
    rows = []
    for item in items:
        price = float(item.get('unit_price') or 0)
        if keyword and keyword not in str(item.get('name', '')).lower():
            continue
        if price_min is not None and price < price_min:
            continue
        if price_max is not None and price > price_max:
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
    prev_link = f'<a class="ghost-link" href="/backoffice/fee-types?{_query(filters, page - 1, page_size)}">上一页</a>' if page > 1 else '<span class="ghost-link disabled">上一页</span>'
    next_link = f'<a class="ghost-link" href="/backoffice/fee-types?{_query(filters, page + 1, page_size)}">下一页</a>' if page * page_size < total else '<span class="ghost-link disabled">下一页</span>'
    return f'<div class="pager"><span>共 {total} 个收费项目 · 第 {page} 页</span><span>{prev_link} {next_link}</span></div>'


def register_fee_type_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _items_for(user):
        service._require(user, 'read')
        if repository:
            return repository.list_fee_types(user['tenant_id'], user['project_id'])
        return service.list_fee_types(user, user['project_id'])

    @app.get('/backoffice/fee-types', response_class=HTMLResponse)
    def fee_type_page(user=Depends(current_user), message: str = '', keyword: str = '', price_min: str = '', price_max: str = '', page: int = 1, page_size: int = 20):
        try:
            filters, page, page_size = _normalize_filters(keyword, price_min, price_max, page, page_size)
            filtered = _filter_items(_items_for(user), filters)
            visible, total = _paginate(filtered, page, page_size)
            return HTMLResponse(_render_fee_types(user, visible, message, filters, page, page_size, total))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/fee-types/create')
    def create_fee_type_page(name: str = Form(...), unit_price: float = Form(...), billing_mode: str = Form('area'), user=Depends(current_user)):
        try:
            service._require(user, 'write')
            if repository:
                item = repository.create_fee_type(user['tenant_id'], user['project_id'], name, unit_price, billing_mode)
                service._log(user, user['project_id'], 'fee_type.create', 'fee_type', item['id'], {'name': name, 'unit_price': float(unit_price), 'billing_mode': item.get('billing_mode')})
            else:
                service.create_fee_type(user, user['project_id'], name, unit_price, billing_mode)
            return RedirectResponse('/backoffice/fee-types?message=收费项目已新增', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
