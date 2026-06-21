#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee type import preview/confirm routes for SaaS."""

import csv
import io

from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from server.saas_fee_rules import normalize_billing_mode
from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page

TEMPLATE_HEADERS = ['name', 'unit_price', 'billing_mode']
ALIASES = {
    'name': ('name', '收费项目', '项目名称', '费用名称'),
    'unit_price': ('unit_price', '单价', '金额', '标准'),
    'billing_mode': ('billing_mode', '计费方式', '计费模式'),
}


def _pick(row, key):
    for alias in ALIASES[key]:
        value = row.get(alias)
        if value not in (None, ''):
            return str(value).strip()
    return ''


def _normalize_row(raw):
    return {
        'name': _pick(raw, 'name'),
        'unit_price': _pick(raw, 'unit_price'),
        'billing_mode': normalize_billing_mode(_pick(raw, 'billing_mode') or 'area'),
    }


def _preview(service, user, rows):
    service._require(user, 'import')
    valid, errors = [], []
    for idx, raw in enumerate(rows, start=1):
        row = _normalize_row(raw)
        try:
            if not row['name']:
                raise ValueError('收费项目不能为空')
            price = float(row.get('unit_price') or 0)
            if price <= 0:
                raise ValueError('单价必须是数字且大于0')
            row['unit_price'] = price
            valid.append(row)
        except ValueError as exc:
            errors.append({'row': idx, 'error': str(exc), 'data': dict(raw)})
    import_id = service._id()
    service.imports[import_id] = {
        'id': import_id, 'kind': 'fee_types', 'tenant_id': user['tenant_id'],
        'project_id': user['project_id'], 'valid_rows': valid, 'errors': errors, 'confirmed': False,
    }
    service._log(user, user['project_id'], 'fee_type_import.preview', 'import', import_id, {'valid_count': len(valid), 'error_count': len(errors)})
    return {'import_id': import_id, 'valid_count': len(valid), 'error_count': len(errors), 'errors': errors}


def _review(service, user, import_id):
    service._require(user, 'import')
    item = service.imports.get(import_id)
    if not item or item.get('kind') != 'fee_types' or int(item.get('tenant_id')) != int(user['tenant_id']) or int(item.get('project_id')) != int(user['project_id']):
        raise PermissionDenied('cross tenant import')
    return {
        'import_id': import_id, 'valid_count': len(item.get('valid_rows') or []),
        'error_count': len(item.get('errors') or []), 'valid_rows': item.get('valid_rows') or [],
        'errors': item.get('errors') or [], 'confirmed': bool(item.get('confirmed')),
    }


def _confirm(service, repository, user, import_id):
    review = _review(service, user, import_id)
    if review['confirmed']:
        return {'created_count': 0, 'skipped_count': review['error_count']}
    created = 0
    for row in review['valid_rows']:
        if repository:
            item = repository.create_fee_type(user['tenant_id'], user['project_id'], row['name'], row['unit_price'], row['billing_mode'])
            service.fees[item['id']] = item
        else:
            service.create_fee_type(user, user['project_id'], row['name'], row['unit_price'], row['billing_mode'])
        created += 1
    service.imports[import_id]['confirmed'] = True
    result = {'created_count': created, 'skipped_count': review['error_count']}
    service._log(user, user['project_id'], 'fee_type_import.confirm', 'import', import_id, result)
    return result


def _template_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerow(['物业费', '2.5', 'area'])
    writer.writerow(['固定服务费', '80', 'fixed'])
    return output.getvalue()


def _template_page(user):
    body = f'''<section class="hero"><div><h1>收费项目导入模板</h1><div class="sub">导入预览不会写库；确认后才写入当前公司和项目的收费项目。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">字段说明</div><div class="card-b"><table><thead><tr><th>CSV 字段</th><th>业务名称</th><th>说明</th></tr></thead><tbody><tr><td>name</td><td>收费项目</td><td>必填，例如物业费、租金</td></tr><tr><td>unit_price</td><td>单价</td><td>必填，必须大于0</td></tr><tr><td>billing_mode</td><td>计费方式</td><td>area 按面积，fixed 固定金额</td></tr></tbody></table><div class="actions" style="margin-top:14px"><a class="ghost-link" href="/api/imports/templates/fee-types.csv">下载 CSV 模板</a><a class="ghost-link" href="/backoffice/imports">返回数据导入</a></div></div></section>'''
    return _page('收费项目导入模板', body)


def _list_fee_types(service, repository, user):
    service._require(user, 'read')
    if repository:
        return {'items': repository.list_fee_types(user['tenant_id'], user['project_id'])}
    return {'items': service.list_fee_types(user, user['project_id'])}


def register_fee_type_import_routes(app, service, repository, current_user):
    @app.get('/api/fee-types')
    def list_fee_types(user=Depends(current_user)):
        try:
            return _list_fee_types(service, repository, user)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/api/imports/fee-types/preview')
    def preview_fee_type_import(data: dict, user=Depends(current_user)):
        try:
            return _preview(service, user, data.get('rows') or [])
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/api/imports/fee-types/{import_id}/review')
    def review_fee_type_import(import_id: int, user=Depends(current_user)):
        try:
            return _review(service, user, import_id)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/api/imports/fee-types/confirm')
    def confirm_fee_type_import(data: dict, user=Depends(current_user)):
        try:
            return _confirm(service, repository, user, int(data.get('import_id') or 0))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/imports/templates/fee-types', response_class=HTMLResponse)
    def fee_type_import_template_page(user=Depends(current_user)):
        return HTMLResponse(_template_page(user))

    @app.get('/api/imports/templates/fee-types.csv')
    def fee_type_import_template_csv(user=Depends(current_user)):
        return PlainTextResponse(_template_csv(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="fee_types_template.csv"'})
