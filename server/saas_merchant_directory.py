#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant directory views backed by SaaS charge targets."""

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


MERCHANT_CATEGORIES = {'商户', '商业'}


def merchant_items_from_targets(targets):
    items = []
    for target in targets:
        if target.get('category') not in MERCHANT_CATEGORIES:
            continue
        items.append({
            'id': target.get('id'),
            'space_no': target.get('room_number') or '',
            'building': target.get('building') or '',
            'unit': target.get('unit') or '',
            'floor': target.get('floor'),
            'shop_name': target.get('shop_name') or '',
            'merchant_name': target.get('tenant_name') or target.get('owner_name') or '',
            'phone': target.get('tenant_phone') or target.get('owner_phone') or '',
            'category': target.get('category') or '',
            'area': target.get('area'),
            'unit_price_override': target.get('unit_price_override'),
            'payment_cycle': target.get('payment_cycle') or '',
            'notes': target.get('notes') or '',
        })
    return items


def _merchant_row(item):
    price = '-' if item.get('unit_price_override') in (None, '') else item.get('unit_price_override')
    return f'''<tr><td>{_h(item.get('space_no'))}</td><td>{_h(item.get('building'))}</td><td>{_h(item.get('unit'))}</td><td>{_h(item.get('floor') or '')}</td><td>{_h(item.get('shop_name'))}</td><td>{_h(item.get('merchant_name'))}</td><td>{_h(item.get('phone'))}</td><td>{_h(item.get('category'))}</td><td>{_h(item.get('area'))}</td><td>{_h(price)}</td><td>{_h(item.get('payment_cycle'))}</td><td>{_h(item.get('notes'))}</td></tr>'''


def _render_merchants(user, items):
    rows = ''.join(_merchant_row(item) for item in items) or '<tr><td colspan="12">暂无商户档案</td></tr>'
    body = f'''
<section class="hero"><div><h1>商户档案</h1><div class="sub">基于收费对象中的商户/商业铺位形成商户档案视图；不新增独立合同表，先用于维护铺位号、店名、承租人、电话、面积、独立单价和缴费周期。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><div class="actions"><a class="ghost-link" href="/backoffice/charge-targets?category=商户">维护商户收费对象</a><a class="ghost-link" href="/backoffice/imports/templates/charge-targets">下载导入模板</a></div><div class="hint">商户档案只读取当前租户和项目数据，不展示内部租户编号或项目编号。</div></div></section>
<section class="card"><div class="card-h">商户 / 铺位列表</div><div class="card-b"><table><thead><tr><th>铺位号</th><th>楼栋 / 区域</th><th>分区</th><th>楼层</th><th>店名</th><th>承租人</th><th>电话</th><th>类型</th><th>面积</th><th>独立单价</th><th>缴费周期</th><th>备注</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''
    return _page('商户档案', body)


def register_merchant_directory(app, service, repository, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    def _items(user):
        service._require(user, 'read')
        targets = repository.list_charge_targets(user['tenant_id'], user['project_id']) if repository else service.list_charge_targets(user, user['project_id'])
        return merchant_items_from_targets(targets)

    @app.get('/api/merchants')
    def merchant_api(user=Depends(current_user)):
        try:
            items = _items(user)
            return {'items': items, 'total': len(items)}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/merchants', response_class=HTMLResponse)
    def merchant_page(user=Depends(current_user)):
        try:
            return HTMLResponse(_render_merchants(user, _items(user)))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
