#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS water/electric meter reading pages and API routes."""

import urllib.parse

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _money(value):
    return str(round(float(value or 0), 2))


def _target_label(item):
    tail = ' / '.join(x for x in [item.get('shop_name') or '', item.get('tenant_name') or ''] if x)
    return f"{item.get('building','')}-{item.get('unit','')}-{item.get('room_number','')}" + (f" ({tail})" if tail else '')


def _reading_row(row):
    target = _target_label(row)
    return f'''<tr><td>{_h(target)}</td><td>{_h(row.get('fee_name'))}</td><td>{_h(row.get('billing_period'))}</td><td>{_h(row.get('previous_reading'))}</td><td>{_h(row.get('current_reading'))}</td><td><strong>{_h(row.get('consumption'))}</strong></td><td>{_h(row.get('status'))}</td><td>{_h(row.get('reading_date'))}</td><td>{_h(row.get('bill_id') or '')}</td></tr>'''


def _render_meter_page(user, targets, fees, readings, message=''):
    target_options = ''.join(f'<option value="{_h(t.get("id"))}">{_h(_target_label(t))}</option>' for t in targets)
    fee_options = ''.join(f'<option value="{_h(f.get("id"))}">{_h(f.get("name"))}</option>' for f in fees if f.get('billing_mode') == 'meter')
    rows = ''.join(_reading_row(r) for r in readings) or '<tr><td colspan="9">暂无抄表记录</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    form = _form(target_options, fee_options) if can_write else '<div class="hint">当前角色只能查看水电表抄表，不能录入或确认。</div>'
    body = f'''
<section class="hero"><div><h1>水电表抄表</h1><div class="sub">统一抄表台账：按收费对象录入水费、电费上次读数、本次读数和用量；确认后生成待审核账单，金额=用量×水电单价。所有记录按当前租户和项目隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
<section class="metric-grid"><div class="metric"><div>抄表记录</div><strong>{len(readings)}</strong></div><div class="metric"><div>水电收费项目</div><strong>{len([f for f in fees if f.get('billing_mode') == 'meter'])}</strong></div><div class="metric"><div>已确认</div><strong>{len([r for r in readings if r.get('status') == 'confirmed'])}</strong></div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">模块说明</div><div class="card-b"><div class="actions"><span class="badge">统一抄表台账</span><span class="badge">上次读数</span><span class="badge">本次读数</span><span class="badge">用量</span><span class="badge">确认后生成待审核账单</span><a class="ghost-link" href="/backoffice/bills">查看出账审核</a></div><div class="hint">对照本地端抄表管理：先维护收费对象和水电收费项目，再录入读数；本次读数不能小于上次读数。</div></div></section>
<section class="grid"><div class="card"><div class="card-h">抄表列表</div><div class="card-b"><table><thead><tr><th>抄表对象</th><th>费用</th><th>账期</th><th>上次读数</th><th>本次读数</th><th>用量</th><th>状态</th><th>日期</th><th>账单</th></tr></thead><tbody>{rows}</tbody></table></div></div><aside class="card"><div class="card-h">录入水电表</div><div class="card-b">{form}</div></aside></section>'''
    return _page('水电表抄表', body)


def _form(target_options, fee_options):
    return f'''<form method="post" action="/backoffice/meter-readings/create"><label>抄表对象</label><select name="charge_target_id" required>{target_options}</select><label>水电收费项目</label><select name="fee_type_id" required>{fee_options}</select><label>账期</label><input name="billing_period" required placeholder="YYYY-MM"><label>上次读数</label><input name="previous_reading" type="number" step="0.01" required><label>本次读数</label><input name="current_reading" type="number" step="0.01" required><label>抄表日期</label><input name="reading_date" type="date" required><label>状态</label><select name="status"><option value="draft">草稿</option><option value="confirmed">已确认</option></select><label>备注</label><input name="notes" placeholder="可选"><button class="primary">保存抄表</button><div class="hint">已确认记录会自动生成 pending_review 待审核账单。</div></form>'''


def _items(service, repository, user):
    if repository:
        return (
            repository.list_charge_targets(user['tenant_id'], user['project_id']),
            repository.list_fee_types(user['tenant_id'], user['project_id']),
            repository.list_meter_readings(user['tenant_id'], user['project_id']),
        )
    return (
        service.list_charge_targets(user, user['project_id']),
        service.list_fee_types(user, user['project_id']),
        service.list_meter_readings(user, user['project_id']),
    )


def register_meter_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse
    from pydantic import BaseModel

    class MeterReadingIn(BaseModel):
        charge_target_id: int
        fee_type_id: int
        billing_period: str
        previous_reading: float
        current_reading: float
        reading_date: str
        status: str = 'draft'
        notes: str = ''

    def _create(user, data):
        service._require(user, 'write')
        if repository:
            return repository.create_meter_reading(user['tenant_id'], user['project_id'], data.charge_target_id, data.fee_type_id, data.billing_period, data.previous_reading, data.current_reading, data.reading_date, data.status, user['id'], data.notes)
        return service.create_meter_reading(user, user['project_id'], data.charge_target_id, data.fee_type_id, data.billing_period, data.previous_reading, data.current_reading, data.reading_date, data.status, data.notes)

    @app.get('/api/meter-readings')
    def list_meter_api(user=Depends(current_user)):
        try:
            service._require(user, 'read')
            items = repository.list_meter_readings(user['tenant_id'], user['project_id']) if repository else service.list_meter_readings(user, user['project_id'])
            return {'items': items}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/api/meter-readings')
    def create_meter_api(data: MeterReadingIn, user=Depends(current_user)):
        try:
            item = _create(user, data)
            return {'item': item}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/meter-readings', response_class=HTMLResponse)
    def meter_page(user=Depends(current_user), message: str = ''):
        try:
            service._require(user, 'read')
            targets, fees, readings = _items(service, repository, user)
            return HTMLResponse(_render_meter_page(user, targets, fees, readings, message))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/meter-readings/create')
    def create_meter_page(charge_target_id: int = Form(...), fee_type_id: int = Form(...), billing_period: str = Form(...), previous_reading: float = Form(...), current_reading: float = Form(...), reading_date: str = Form(...), status: str = Form('draft'), notes: str = Form(''), user=Depends(current_user)):
        try:
            data = MeterReadingIn(charge_target_id=charge_target_id, fee_type_id=fee_type_id, billing_period=billing_period, previous_reading=previous_reading, current_reading=current_reading, reading_date=reading_date, status=status, notes=notes)
            item = _create(user, data)
            bill = item.get('bill') or {}
            msg = f"抄表已保存，用量{_money(item.get('consumption'))}，账单金额{_money(bill.get('amount'))}，状态{bill.get('status', item.get('status'))}"
            return RedirectResponse('/backoffice/meter-readings?' + urllib.parse.urlencode({'message': msg}), status_code=303)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
