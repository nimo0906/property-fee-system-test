#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS merchant contract and amendment pages/API routes."""

import urllib.parse
from typing import Optional

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _money(value):
    return str(round(float(value or 0), 2))


def _target_label(t):
    return f"{t.get('building','')}-{t.get('unit','')}-{t.get('room_number','')}" + (f" ({t.get('shop_name') or t.get('tenant_name')})" if (t.get('shop_name') or t.get('tenant_name')) else '')


def _contract_row(c):
    return f'''<tr><td>{_h(c.get('contract_no'))}</td><td>{_h(c.get('space_no'))}</td><td>{_h(c.get('shop_name'))}</td><td>{_h(c.get('merchant_name'))}</td><td>{_h(c.get('start_date'))} 至 {_h(c.get('end_date'))}</td><td>{_h(c.get('contract_area'))}</td><td>{_h(c.get('rent_unit_price'))}</td><td>{_h(c.get('monthly_rent_amount'))}</td><td>{_h(c.get('property_rate'))}</td><td>{_h(c.get('monthly_property_fee_amount'))}</td><td>{_h(c.get('deposit_amount'))}</td><td>{_h(c.get('status'))}</td></tr>'''


def _amendment_row(a):
    return f'''<tr><td>{_h(a.get('amendment_no'))}</td><td>{_h(a.get('effective_date'))}</td><td>{_h(a.get('rent_unit_price') or '')}</td><td>{_h(a.get('property_rate') or '')}</td><td>{_h(a.get('contract_area') or '')}</td><td>{_h(a.get('status'))}</td><td>{_h(a.get('notes') or '')}</td></tr>'''


def _create_form(targets):
    opts = ''.join(f'<option value="{_h(t.get("id"))}">{_h(_target_label(t))}</option>' for t in targets if t.get('category') in {'商户', '商业'})
    return f'''<form method="post" action="/backoffice/merchant-contracts/create"><label>铺位/商户</label><select name="charge_target_id" required>{opts}</select><label>合同编号</label><input name="contract_no" required><label>承租人</label><input name="merchant_name" required><label>店铺名称</label><input name="shop_name"><label>开始日期</label><input name="start_date" type="date" required><label>结束日期</label><input name="end_date" type="date" required><label>合同面积</label><input name="contract_area" type="number" step="0.01" required><label>租金单价</label><input name="rent_unit_price" type="number" step="0.01" required><label>物业费单价</label><input name="property_rate" type="number" step="0.0001" required><label>租金周期</label><input name="rent_cycle" value="monthly"><label>物业费周期</label><input name="property_cycle" value="monthly"><label>押金</label><input name="deposit_amount" type="number" step="0.01" value="0"><label>状态</label><input name="status" value="active"><label>备注</label><input name="notes"><button class="primary">保存商户合同</button></form>'''


def _contract_options(contracts):
    return ''.join(f'<option value="{_h(c.get("id"))}">{_h(c.get("contract_no"))} · {_h(c.get("merchant_name"))}</option>' for c in contracts)


def _bill_form(contracts):
    if not contracts:
        return '<div class="hint">请先新增商户合同。</div>'
    return f'''<form method="post" action="/backoffice/merchant-contracts/{_h(contracts[0].get('id'))}/generate-bill" onsubmit="this.action='/backoffice/merchant-contracts/'+this.contract_id.value+'/generate-bill'"><label>合同</label><select name="contract_id">{_contract_options(contracts)}</select><label>账期</label><input name="billing_period" required placeholder="2028-05"><label>服务开始</label><input name="service_start" type="date" required><label>服务结束</label><input name="service_end" type="date" required><button class="primary">生成合同账单</button><div class="hint">金额=合同面积×租金单价 + 合同面积×物业费单价；生效日之前使用原合同，之后使用已确认合同变更。</div></form>'''


def _amend_form(contracts):
    if not contracts:
        return '<div class="hint">暂无可变更合同。</div>'
    return f'''<form method="post" action="/backoffice/merchant-contracts/{_h(contracts[0].get('id'))}/amend" onsubmit="this.action='/backoffice/merchant-contracts/'+this.contract_id.value+'/amend'"><label>合同</label><select name="contract_id">{_contract_options(contracts)}</select><label>变更编号</label><input name="amendment_no" required><label>生效日期</label><input name="effective_date" type="date" required><label>新租金单价</label><input name="rent_unit_price" type="number" step="0.01"><label>新物业费单价</label><input name="property_rate" type="number" step="0.0001"><label>新合同面积</label><input name="contract_area" type="number" step="0.01"><label>备注</label><input name="notes"><button class="primary">确认合同变更</button></form>'''


def _render(user, targets, contracts, amendments, bills, message=''):
    rows = ''.join(_contract_row(c) for c in contracts) or '<tr><td colspan="12">暂无商户合同</td></tr>'
    amendment_rows = ''.join(_amendment_row(a) for a in amendments) or '<tr><td colspan="7">暂无合同变更</td></tr>'
    bill_rows = ''.join(f'''<tr><td>{_h(b.get('bill_number'))}</td><td>{_h(b.get('billing_period'))}</td><td>{_h(b.get('amount'))}</td><td>{_h(b.get('status'))}</td></tr>''' for b in bills if b.get('source') == 'merchant_contract') or '<tr><td colspan="4">暂无合同账单</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance'}
    forms = f'''<aside class="card"><div class="card-h">新增商户合同</div><div class="card-b">{_create_form(targets)}</div></aside><aside class="card"><div class="card-h">合同变更</div><div class="card-b">{_amend_form(contracts)}</div></aside><aside class="card"><div class="card-h">生成合同账单</div><div class="card-b">{_bill_form(contracts)}</div></aside>''' if can_write else '<aside class="card"><div class="card-b hint">当前角色只读商户合同和合同变更。</div></aside>'
    body = f'''<section class="hero"><div><h1>商户合同</h1><div class="sub">独立模块闭环：维护商户合同、合同周期、租金单价、物业费单价、押金和合同变更；生成合同账单前自动按生效日期取最新变更。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>{notice}<section class="metric-grid"><div class="metric"><div>合同数</div><strong>{len(contracts)}</strong></div><div class="metric"><div>合同变更</div><strong>{len(amendments)}</strong></div><div class="metric"><div>合同账单</div><strong>{len([b for b in bills if b.get('source') == 'merchant_contract'])}</strong></div></section><section class="card" style="margin-bottom:18px"><div class="card-b"><div class="actions"><span class="badge">合同周期</span><span class="badge">租金单价</span><span class="badge">物业费单价</span><span class="badge">合同变更</span><span class="badge">生成合同账单</span></div><div class="hint">页面不展示内部租户编号、项目编号或密钥内容。</div></div></section><section class="grid"><div class="card"><div class="card-h">商户合同列表</div><div class="card-b"><table><thead><tr><th>合同编号</th><th>铺位号</th><th>店名</th><th>承租人</th><th>合同周期</th><th>面积</th><th>租金单价</th><th>月租金</th><th>物业费单价</th><th>月物业费</th><th>押金</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table></div></div>{forms}<div class="card"><div class="card-h">合同变更记录</div><div class="card-b"><table><thead><tr><th>编号</th><th>生效日期</th><th>租金单价</th><th>物业费单价</th><th>面积</th><th>状态</th><th>备注</th></tr></thead><tbody>{amendment_rows}</tbody></table></div></div><div class="card"><div class="card-h">合同账单</div><div class="card-b"><table><thead><tr><th>账单号</th><th>账期</th><th>金额</th><th>状态</th></tr></thead><tbody>{bill_rows}</tbody></table></div></div></section>'''
    return _page('商户合同', body)


def register_contract_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse
    from pydantic import BaseModel

    class ContractIn(BaseModel):
        charge_target_id: int; contract_no: str; merchant_name: str; shop_name: str = ''
        start_date: str; end_date: str; contract_area: float; rent_unit_price: float; property_rate: float
        rent_cycle: str = 'monthly'; property_cycle: str = 'monthly'; deposit_amount: float = 0
        status: str = 'active'; notes: str = ''

    class AmendmentIn(BaseModel):
        amendment_no: str; effective_date: str; rent_unit_price: Optional[float] = None; property_rate: Optional[float] = None; contract_area: Optional[float] = None; notes: str = ''

    class BillIn(BaseModel):
        billing_period: str; service_start: str; service_end: str

    def _items(user):
        if repository:
            contracts = repository.list_merchant_contracts(user['tenant_id'], user['project_id'])
            amendments = []
            for c in contracts:
                amendments.extend(repository.list_contract_amendments(user['tenant_id'], user['project_id'], c['id']))
            return repository.list_charge_targets(user['tenant_id'], user['project_id']), contracts, amendments, repository.list_bills(user['tenant_id'], user['project_id'])
        contracts = service.list_merchant_contracts(user, user['project_id'])
        amendments = []
        for c in contracts:
            amendments.extend(service.list_contract_amendments(user, user['project_id'], c['id']))
        return service.list_charge_targets(user, user['project_id']), contracts, amendments, service.list_bills(user, user['project_id'])

    def _create(user, data):
        service._require(user, 'write')
        if repository:
            return repository.create_merchant_contract(user['tenant_id'], user['project_id'], data.charge_target_id, data.contract_no, data.merchant_name, data.shop_name, data.start_date, data.end_date, data.contract_area, data.rent_unit_price, data.property_rate, data.rent_cycle, data.property_cycle, data.deposit_amount, data.status, user['id'], data.notes)
        return service.create_merchant_contract(user, user['project_id'], data.charge_target_id, data.contract_no, data.merchant_name, data.shop_name, data.start_date, data.end_date, data.contract_area, data.rent_unit_price, data.property_rate, data.rent_cycle, data.property_cycle, data.deposit_amount, data.status, data.notes)

    @app.get('/api/merchant-contracts')
    def list_api(user=Depends(current_user)):
        try:
            _, contracts, _, _ = _items(user)
            return {'items': contracts, 'total': len(contracts)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/api/merchant-contracts')
    def create_api(data: ContractIn, user=Depends(current_user)):
        try:
            return {'item': _create(user, data)}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post('/api/merchant-contracts/{contract_id}/amend')
    def amend_api(contract_id: int, data: AmendmentIn, user=Depends(current_user)):
        try:
            service._require(user, 'write')
            item = repository.create_contract_amendment(user['tenant_id'], user['project_id'], contract_id, data.amendment_no, data.effective_date, data.rent_unit_price, data.property_rate, data.contract_area, actor_user_id=user['id'], notes=data.notes) if repository else service.create_contract_amendment(user, user['project_id'], contract_id, data.amendment_no, data.effective_date, data.rent_unit_price, data.property_rate, data.contract_area, notes=data.notes)
            return {'item': item}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/api/merchant-contracts/{contract_id}/generate-bill')
    def bill_api(contract_id: int, data: BillIn, user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            item = repository.generate_contract_bill(user['tenant_id'], user['project_id'], contract_id, data.billing_period, data.service_start, data.service_end, user['id']) if repository else service.generate_contract_bill(user, user['project_id'], contract_id, data.billing_period, data.service_start, data.service_end)
            return {'item': item}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get('/backoffice/merchant-contracts', response_class=HTMLResponse)
    def page(message: str = '', user=Depends(current_user)):
        targets, contracts, amendments, bills = _items(user)
        return HTMLResponse(_render(user, targets, contracts, amendments, bills, message))

    @app.post('/backoffice/merchant-contracts/create')
    def create_page(charge_target_id: int = Form(...), contract_no: str = Form(...), merchant_name: str = Form(...), shop_name: str = Form(''), start_date: str = Form(...), end_date: str = Form(...), contract_area: float = Form(...), rent_unit_price: float = Form(...), property_rate: float = Form(...), rent_cycle: str = Form('monthly'), property_cycle: str = Form('monthly'), deposit_amount: float = Form(0), status: str = Form('active'), notes: str = Form(''), user=Depends(current_user)):
        try:
            _create(user, ContractIn(charge_target_id=charge_target_id, contract_no=contract_no, merchant_name=merchant_name, shop_name=shop_name, start_date=start_date, end_date=end_date, contract_area=contract_area, rent_unit_price=rent_unit_price, property_rate=property_rate, rent_cycle=rent_cycle, property_cycle=property_cycle, deposit_amount=deposit_amount, status=status, notes=notes))
            return RedirectResponse('/backoffice/merchant-contracts?message=' + urllib.parse.quote('合同已新增'), status_code=303)
        except Exception as exc:
            return RedirectResponse('/backoffice/merchant-contracts?message=' + urllib.parse.quote(str(exc)), status_code=303)

    @app.post('/backoffice/merchant-contracts/{contract_id}/amend')
    def amend_page(contract_id: int, amendment_no: str = Form(...), effective_date: str = Form(...), rent_unit_price: str = Form(''), property_rate: str = Form(''), contract_area: str = Form(''), notes: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'write')
            rent = float(rent_unit_price) if rent_unit_price else None; prop = float(property_rate) if property_rate else None; area = float(contract_area) if contract_area else None
            if repository:
                repository.create_contract_amendment(user['tenant_id'], user['project_id'], contract_id, amendment_no, effective_date, rent, prop, area, actor_user_id=user['id'], notes=notes)
            else:
                service.create_contract_amendment(user, user['project_id'], contract_id, amendment_no, effective_date, rent, prop, area, notes=notes)
            return RedirectResponse('/backoffice/merchant-contracts?message=' + urllib.parse.quote('合同变更已确认'), status_code=303)
        except Exception as exc:
            return RedirectResponse('/backoffice/merchant-contracts?message=' + urllib.parse.quote(str(exc)), status_code=303)

    @app.post('/backoffice/merchant-contracts/{contract_id}/generate-bill')
    def bill_page(contract_id: int, billing_period: str = Form(...), service_start: str = Form(...), service_end: str = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            if repository:
                repository.generate_contract_bill(user['tenant_id'], user['project_id'], contract_id, billing_period, service_start, service_end, user['id'])
            else:
                service.generate_contract_bill(user, user['project_id'], contract_id, billing_period, service_start, service_end)
            return RedirectResponse('/backoffice/merchant-contracts?message=' + urllib.parse.quote('合同账单已生成'), status_code=303)
        except Exception as exc:
            return RedirectResponse('/backoffice/merchant-contracts?message=' + urllib.parse.quote(str(exc)), status_code=303)
