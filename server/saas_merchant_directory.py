#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant directory views backed by SaaS charge targets."""

import csv
import io
import urllib.parse

from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_fee_rules import calculate_bill_amount
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
    payment_link = f'<a class="ghost-link" href="/backoffice/payments?target_id={_h(item.get("id"))}">登记收款</a>' if float(item.get('arrears_amount_total') or 0) > 0 else '-'
    return f'''<tr><td>{_h(item.get('space_no'))}</td><td>{_h(item.get('building'))}</td><td>{_h(item.get('unit'))}</td><td>{_h(item.get('floor') or '')}</td><td>{_h(item.get('shop_name'))}</td><td>{_h(item.get('merchant_name'))}</td><td>{_h(item.get('phone'))}</td><td>{_h(item.get('category'))}</td><td>{_h(item.get('area'))}</td><td>{_h(price)}</td><td>{_h(item.get('payment_cycle'))}</td><td>{_h(item.get('bill_count', 0))}</td><td>{_h(item.get('bill_amount_total', 0.0))}</td><td>{_h(item.get('paid_amount_total', 0.0))}</td><td>{_h(item.get('arrears_amount_total', 0.0))}</td><td>{payment_link}</td><td>{_h(item.get('notes'))}</td></tr>'''

def _summary_metric(label, value):
    return f'<div class="metric"><div>{_h(label)}</div><strong>{_h(str(value))}</strong></div>'

def _merchant_summary(items):
    total = len(items or [])
    arrears = sum(1 for item in items if float(item.get('arrears_amount_total') or 0) > 0)
    due = round(sum(float(item.get('bill_amount_total') or 0) for item in items), 2)
    paid = round(sum(float(item.get('paid_amount_total') or 0) for item in items), 2)
    unpaid = round(sum(float(item.get('arrears_amount_total') or 0) for item in items), 2)
    metrics = [_summary_metric('商户总数', total), _summary_metric('欠费商户', arrears), _summary_metric('商户应收', due), _summary_metric('商户实收', paid), _summary_metric('商户欠费', unpaid)]
    return '<section class="metric-grid">' + ''.join(metrics) + '</section>'

def _merchant_flow_panel():
    return '''<section class="card" style="margin-bottom:18px"><div class="card-h">商户收费流程</div><div class="card-b"><div class="work-grid"><a class="work-card primary-work-card" href="/backoffice/merchants"><strong>维护商户档案</strong><span>维护铺位号、店名、承租人、面积和独立单价</span></a><a class="work-card" href="/backoffice/merchants"><strong>生成商户账单</strong><span>单户或批量生成商户应收账单</span></a><a class="work-card" href="/backoffice/payments?target_id="><strong>登记商户收款</strong><span>有欠费时从列表直接进入收款</span></a><a class="work-card" href="/backoffice/merchants?arrears=1"><strong>查看欠费商户</strong><span>只看欠费余额大于 0 的商户</span></a><a class="work-card" href="/api/merchants/export.csv"><strong>导出商户清单</strong><span>导出铺位、商户、应收、实收和欠费</span></a></div></div></section>'''

def _attach_bill_totals(items, bills):
    totals = {int(item['id']): {'bill_count': 0, 'bill_amount_total': 0.0, 'paid_amount_total': 0.0, 'arrears_amount_total': 0.0} for item in items}
    for bill in bills:
        target_id = int(bill.get('charge_target_id') or 0)
        if target_id not in totals:
            continue
        row = totals[target_id]
        row['bill_count'] += 1
        row['bill_amount_total'] = round(row['bill_amount_total'] + float(bill.get('amount') or 0), 2)
        row['paid_amount_total'] = round(row['paid_amount_total'] + float(bill.get('paid_amount') or 0), 2)
        row['arrears_amount_total'] = round(row['arrears_amount_total'] + float(bill.get('unpaid_amount') or 0), 2)
    return [{**item, **totals.get(int(item['id']), {})} for item in items]

def _csv_text(items):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['铺位号', '楼栋 / 区域', '分区', '楼层', '店名', '承租人', '电话', '类型', '面积', '独立单价', '缴费周期', '账单数', '应收合计', '已收合计', '欠费余额', '备注'])
    for item in items:
        price = '' if item.get('unit_price_override') in (None, '') else item.get('unit_price_override')
        writer.writerow([
            item.get('space_no') or '', item.get('building') or '', item.get('unit') or '',
            item.get('floor') or '', item.get('shop_name') or '', item.get('merchant_name') or '',
            item.get('phone') or '', item.get('category') or '', item.get('area') or '', price,
            item.get('payment_cycle') or '', item.get('bill_count', 0),
            item.get('bill_amount_total', 0.0), item.get('paid_amount_total', 0.0),
            item.get('arrears_amount_total', 0.0), item.get('notes') or '',
        ])
    return '\ufeff' + output.getvalue()

def _create_form():
    return '''<form method="post" action="/backoffice/merchants/create"><label>楼栋 / 区域</label><input name="building" required placeholder="例如 商场B区"><label>分区</label><input name="unit" placeholder="例如 二层"><label>铺位号</label><input name="space_no" required placeholder="例如 B-208"><label>楼层</label><input name="floor" type="number" step="1"><label>店名</label><input name="shop_name" placeholder="店铺名称"><label>承租人</label><input name="merchant_name" required placeholder="商户/承租人"><label>电话</label><input name="phone" placeholder="联系电话"><label>面积</label><input name="area" required type="number" step="0.01" min="0.01"><label>独立单价</label><input name="unit_price_override" type="number" step="0.01" min="0"><label>缴费周期</label><input name="payment_cycle" placeholder="monthly / quarterly"><label>备注</label><input name="notes" placeholder="备注"><button class="primary">新增商户</button><div class="hint">商户档案写入当前项目的收费对象，类型固定为商户。</div></form>'''

def _match_keyword(item, keyword):
    if not keyword:
        return True
    haystack = ' '.join(str(item.get(key) or '') for key in ['space_no', 'building', 'unit', 'shop_name', 'merchant_name', 'phone', 'category', 'notes'])
    return keyword.lower() in haystack.lower()

def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default

def _only_arrears(value):
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}

def _filtered_items(items, keyword='', arrears=False, building='', unit=''):
    keyword = str(keyword or '').strip()
    building = str(building or '').strip()
    unit = str(unit or '').strip()
    rows = [item for item in items if _match_keyword(item, keyword)]
    if building:
        rows = [item for item in rows if str(item.get('building') or '') == building]
    if unit:
        rows = [item for item in rows if str(item.get('unit') or '') == unit]
    if arrears:
        rows = [item for item in rows if float(item.get('arrears_amount_total') or 0) > 0]
    return rows, keyword, building, unit

def _paged_items(items, keyword='', page=1, page_size=20, arrears=False, building='', unit=''):
    page = max(_to_int(page, 1), 1)
    page_size = min(max(_to_int(page_size, 20), 1), 50)
    filtered, keyword, building, unit = _filtered_items(items, keyword, arrears, building, unit)
    start = (page - 1) * page_size
    return filtered[start:start + page_size], len(filtered), page, page_size, keyword, building, unit

def _query(keyword, page, page_size, arrears=False, building='', unit=''):
    return urllib.parse.urlencode({'keyword': keyword, 'page': page, 'page_size': page_size, 'arrears': '1' if arrears else '', 'building': building, 'unit': unit})

def _export_query(keyword='', arrears=False, building='', unit=''):
    params = {'keyword': keyword, 'arrears': '1' if arrears else '', 'building': building, 'unit': unit}
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value})
    return f'/api/merchants/export.csv?{query}' if query else '/api/merchants/export.csv'

def _filter_form(keyword, page_size, arrears=False, building='', unit=''):
    options = ''.join(f'<option value="{n}"{" selected" if page_size == n else ""}>{n}</option>' for n in [10, 20, 50])
    checked = ' checked' if arrears else ''
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">商户检索</div><div class="card-b"><form method="get" action="/backoffice/merchants" class="filters"><input type="hidden" name="page" value="1"><div><label>关键词</label><input name="keyword" value="{_h(keyword)}" placeholder="铺位号 / 店名 / 承租人 / 电话"></div><div><label>楼栋 / 区域</label><input name="building" value="{_h(building)}" placeholder="例如 商场A区"></div><div><label>分区</label><input name="unit" value="{_h(unit)}" placeholder="例如 二层"></div><div><label>每页数量</label><select name="page_size">{options}</select></div><div><label><input type="checkbox" name="arrears" value="1"{checked}> 仅看欠费商户</label></div><div><button class="primary">检索</button></div></form></div></section>'''

def _pager(keyword, page, page_size, total, arrears=False, building='', unit=''):
    prev_link = f'<a class="ghost-link" href="/backoffice/merchants?{_query(keyword, page - 1, page_size, arrears, building, unit)}">上一页</a>' if page > 1 else '<span class="ghost-link disabled">上一页</span>'
    next_link = f'<a class="ghost-link" href="/backoffice/merchants?{_query(keyword, page + 1, page_size, arrears, building, unit)}">下一页</a>' if page * page_size < total else '<span class="ghost-link disabled">下一页</span>'
    return f'<div class="pager"><span>共 {total} 个商户 · 第 {page} 页</span><span>{prev_link} {next_link}</span></div>'

def _fee_options(fees):
    return ''.join(f'<option value="{_h(fee.get("id"))}">{_h(fee.get("name"))} · {_h(fee.get("billing_mode", "area"))} · {_h(fee.get("unit_price"))}</option>' for fee in fees)

def _target_options(items):
    return ''.join(f'<option value="{_h(item.get("id"))}">{_h(item.get("space_no"))} · {_h(item.get("shop_name") or item.get("merchant_name"))}</option>' for item in items)

def _bill_number(tenant_id, project_id, period, target_id, fee_type_id):
    return f'SaaS-{tenant_id}-{project_id}-{period}-{target_id}-{fee_type_id}'

def _repository_bill_exists(repository, tenant_id, project_id, period, target_id, fee_type_id):
    return repository._bill_exists(tenant_id, project_id, _bill_number(tenant_id, project_id, period, target_id, fee_type_id))

def _service_bill_exists(service, user, project_id, period, target_id, fee_type_id):
    bill_number = _bill_number(user['tenant_id'], project_id, period, target_id, fee_type_id)
    return any(bill.get('bill_number') == bill_number for bill in service.bills.values())

def _batch_bill_form(fees):
    if not fees:
        return '<div class="hint">请先维护收费项目后再批量出账。</div>'
    return f'''<form method="post" action="/backoffice/merchants/batch-generate-bills"><label>收费项目</label><select name="fee_type_id">{_fee_options(fees)}</select><label>楼栋 / 区域范围</label><input name="building" placeholder="选填，精确匹配楼栋/区域"><label>分区范围</label><input name="unit" placeholder="选填，精确匹配单元/分区"><label>账期</label><input name="billing_period" required placeholder="例如 2027-03"><label>服务开始</label><input name="service_start" required placeholder="2027-03-01"><label>服务结束</label><input name="service_end" required placeholder="2027-03-31"><button class="primary">批量生成商户账单</button><div class="hint">仅为商户/商业收费对象出账；重复账期会自动跳过。</div></form>'''

def _bill_form(items, fees):
    if not items or not fees:
        return '<div class="hint">请先维护商户档案和收费项目后再生成账单。</div>'
    return f'''<form method="post" action="/backoffice/merchants/generate-bill"><label>商户 / 铺位</label><select name="target_id">{_target_options(items)}</select><label>收费项目</label><select name="fee_type_id">{_fee_options(fees)}</select><label>账期</label><input name="billing_period" required placeholder="例如 2027-01"><label>服务开始</label><input name="service_start" required placeholder="2027-01-01"><label>服务结束</label><input name="service_end" required placeholder="2027-01-31"><button class="primary">生成商户账单</button><div class="hint">金额按收费项目规则计算；商户独立单价优先于收费项目单价。</div></form>'''

def _render_merchants(user, items, message='', keyword='', page=1, page_size=20, total=0, fees=None, arrears=False, building='', unit=''):
    rows = ''.join(_merchant_row(item) for item in items) or '<tr><td colspan="12">暂无商户档案</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    body = f'''
<section class="hero"><div><h1>商户收费工作台</h1><div class="sub">商户档案：基于收费对象中的商户/商业铺位形成商户收费工作台；维护铺位号、店名、承租人、电话、面积、独立单价和缴费周期。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{_merchant_summary(items)}
{_merchant_flow_panel()}
<section class="card" style="margin-bottom:18px"><div class="card-b"><div class="actions"><a class="ghost-link" href="/backoffice/charge-targets?category=商户">维护商户收费对象</a><a class="ghost-link" href="/backoffice/imports/templates/charge-targets">下载导入模板</a><a class="ghost-link" href="{_h(_export_query(keyword, arrears, building, unit))}">导出商户CSV</a></div><div class="hint">商户档案只读取当前租户和项目数据，不展示内部租户编号或项目编号。</div></div></section>
{_filter_form(keyword, page_size, arrears, building, unit)}
<section class="grid"><div class="card"><div class="card-h">商户 / 铺位列表</div><div class="card-b">{_pager(keyword, page, page_size, total, arrears, building, unit)}<table><thead><tr><th>铺位号</th><th>楼栋 / 区域</th><th>分区</th><th>楼层</th><th>店名</th><th>承租人</th><th>电话</th><th>类型</th><th>面积</th><th>独立单价</th><th>缴费周期</th><th>账单数</th><th>应收合计</th><th>已收合计</th><th>欠费余额</th><th>收款</th><th>备注</th></tr></thead><tbody>{rows}</tbody></table>{_pager(keyword, page, page_size, total, arrears, building, unit)}</div></div><aside class="card"><div class="card-h">批量生成商户账单</div><div class="card-b">{_batch_bill_form(fees or [])}</div></aside><aside class="card"><div class="card-h">生成商户账单</div><div class="card-b">{_bill_form(items, fees or [])}</div></aside><aside class="card"><div class="card-h">新增商户</div><div class="card-b">{_create_form()}</div></aside></section>'''
    return _page('商户档案', body)

def register_merchant_directory(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

    def _items(user):
        service._require(user, 'read')
        targets = repository.list_charge_targets(user['tenant_id'], user['project_id']) if repository else service.list_charge_targets(user, user['project_id'])
        items = merchant_items_from_targets(targets)
        bills = repository.list_bills(user['tenant_id'], user['project_id']) if repository else service.list_bills(user, user['project_id'])
        return _attach_bill_totals(items, bills)

    def _fees(user):
        service._require(user, 'read')
        return repository.list_fee_types(user['tenant_id'], user['project_id']) if repository else service.list_fee_types(user, user['project_id'])

    @app.get('/api/merchants')
    def merchant_api(keyword: str = '', page: int = 1, page_size: int = 20, arrears: str = '', building: str = '', unit: str = '', user=Depends(current_user)):
        try:
            visible, total, page, page_size, keyword, building, unit = _paged_items(_items(user), keyword, page, page_size, _only_arrears(arrears), building, unit)
            return {'items': visible, 'total': total, 'page': page, 'page_size': page_size}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')


    @app.get('/api/merchants/export.csv')
    def merchant_export_csv(keyword: str = '', arrears: str = '', building: str = '', unit: str = '', user=Depends(current_user)):
        try:
            items, _, _, _ = _filtered_items(_items(user), keyword, _only_arrears(arrears), building, unit)
            return PlainTextResponse(
                _csv_text(items),
                media_type='text/csv; charset=utf-8',
                headers={'Content-Disposition': 'attachment; filename="merchants.csv"'},
            )
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/merchants', response_class=HTMLResponse)
    def merchant_page(user=Depends(current_user), message: str = '', keyword: str = '', page: int = 1, page_size: int = 20, arrears: str = '', building: str = '', unit: str = ''):
        try:
            arrears_only = _only_arrears(arrears)
            visible, total, page, page_size, keyword, building, unit = _paged_items(_items(user), keyword, page, page_size, arrears_only, building, unit)
            return HTMLResponse(_render_merchants(user, visible, message, keyword, page, page_size, total, _fees(user), arrears_only, building, unit))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/merchants/batch-generate-bills')
    def batch_generate_merchant_bills_page(fee_type_id: int = Form(...), billing_period: str = Form(...), service_start: str = Form(...), service_end: str = Form(...), building: str = Form(''), unit: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            if repository:
                result = repository.batch_generate_bills(user['tenant_id'], user['project_id'], fee_type_id, billing_period, service_start, service_end, category='商户', building=building, unit=unit, actor_user_id=user['id'])
                extra = repository.batch_generate_bills(user['tenant_id'], user['project_id'], fee_type_id, billing_period, service_start, service_end, category='商业', building=building, unit=unit, actor_user_id=user['id'])
            else:
                result = service.batch_generate_bills(user, user['project_id'], fee_type_id, billing_period, service_start, service_end, category='商户', building=building, unit=unit)
                extra = service.batch_generate_bills(user, user['project_id'], fee_type_id, billing_period, service_start, service_end, category='商业', building=building, unit=unit)
            created = int(result.get('created_count', 0)) + int(extra.get('created_count', 0))
            skipped = int(result.get('skipped_count', 0)) + int(extra.get('skipped_count', 0))
            return RedirectResponse(f'/backoffice/merchants?message=商户批量出账：新增 {created} 笔，跳过 {skipped} 笔', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/merchants/generate-bill')
    def generate_merchant_bill_page(target_id: int = Form(...), fee_type_id: int = Form(...), billing_period: str = Form(...), service_start: str = Form(...), service_end: str = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'billing')
            if repository:
                target = repository.get_charge_target(user['tenant_id'], user['project_id'], target_id)
                fee = repository.get_fee_type(user['tenant_id'], user['project_id'], fee_type_id)
                if not target or target.get('category') not in MERCHANT_CATEGORIES or not fee:
                    raise TenantScopeError('merchant target or fee type not found')
                if _repository_bill_exists(repository, user['tenant_id'], user['project_id'], billing_period, target_id, fee_type_id):
                    return RedirectResponse('/backoffice/merchants?message=商户账单已存在，已跳过', status_code=303)
                repository.create_bill(user['tenant_id'], user['project_id'], target_id, fee_type_id, billing_period, service_start, service_end, calculate_bill_amount(target, fee, service_start, service_end), actor_user_id=user['id'])
            else:
                target = service.targets.get(target_id)
                fee = service.fees.get(fee_type_id)
                if not target or target.get('category') not in MERCHANT_CATEGORIES or not fee:
                    raise PermissionDenied('merchant target or fee type not found')
                if _service_bill_exists(service, user, user['project_id'], billing_period, target_id, fee_type_id):
                    return RedirectResponse('/backoffice/merchants?message=商户账单已存在，已跳过', status_code=303)
                service.generate_bill(user, user['project_id'], target, fee, billing_period, service_start, service_end)
            return RedirectResponse('/backoffice/merchants?message=商户账单已生成', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/merchants/create')
    def create_merchant_page(building: str = Form(...), unit: str = Form(''), space_no: str = Form(...), floor: str = Form(''), shop_name: str = Form(''), merchant_name: str = Form(...), phone: str = Form(''), area: float = Form(...), unit_price_override: str = Form(''), payment_cycle: str = Form(''), notes: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'write')
            floor_value = int(floor) if str(floor or '').strip() else None
            if repository:
                repository.create_charge_target(user['tenant_id'], user['project_id'], building, unit, space_no, '商户', area, 0, unit_price_override or None, floor=floor_value, shop_name=shop_name, tenant_name=merchant_name, tenant_phone=phone, payment_cycle=payment_cycle, notes=notes)
            else:
                service.create_charge_target(user, user['project_id'], building, unit, space_no, '商户', area, 0, unit_price_override or None, floor=floor_value, shop_name=shop_name, tenant_name=merchant_name, tenant_phone=phone, payment_cycle=payment_cycle, notes=notes)
            return RedirectResponse('/backoffice/merchants?message=商户已新增', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
