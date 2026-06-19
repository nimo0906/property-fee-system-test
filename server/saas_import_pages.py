#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML import review pages for SaaS backoffice."""

import csv
import io

from server.saas_import_activity import display_filename, render_import_activity
from server.saas_business_templates import CHARGE_TARGET_TEMPLATE_HEADERS, render_template_summary, template_csv
from server.saas_import_mapping import normalize_import_row
from server.saas_tenant_business_config import template_code_for_user
from server.saas_import_duplicates import split_new_and_duplicates
from server.saas_service import PermissionDenied
from server.saas_storage import SaasStorage
from server.saas_user_pages import _h, _page

STORAGE = SaasStorage(root_dir='/var/lib/property-saas')
TEMPLATE_CSV = ','.join(CHARGE_TARGET_TEMPLATE_HEADERS) + '\n示例业主,13800000000,业主,1栋,1单元,101,,,张租户,13900000000,居民,80,,monthly,模板示例\n# legacy aliases: 业主姓名,联系电话,楼栋/区域,单元/分区,房号/铺位号,面积\n'


def _parse_csv_rows(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text or ''))
    return [dict(row) for row in reader]


def _render_file_notice(item):
    if not item:
        return ''
    display_name = display_filename(item.get('original_name'))
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">文件已登记</div><div class="card-b"><p class="sub">原始文件：{_h(display_name)}</p><p class="sub">存储位置：{_h(item.get('storage_key'))}</p><div class="hint">文件登记只保存租户内存储元数据；后续预览仍需人工确认，不会自动写库。</div></div></section>'''


def _render_import_home(user, file_item=None, files=None, logs=None, batches=None):
    can_import = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    form = _preview_form() if can_import else '<div class="hint">当前角色不能导入，只能查看业务数据。</div>'
    upload = _upload_form() if can_import else '<div class="hint">当前角色不能登记上传文件。</div>'
    body = f'''
<section class="hero"><div><h1>数据导入</h1><div class="sub">先预览校验，不直接写库；确认后只导入有效行，错误行不会污染正式数据。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{_render_file_notice(file_item)}
<section class="grid"><div class="card"><div class="card-h">收费对象导入</div><div class="card-b">{form}</div></div>
<aside class="card"><div class="card-h">导入模板</div><div class="card-b"><p class="sub">先按模板准备收费对象数据，再复制 CSV 内容做预览。</p><div class="actions"><a class="ghost-link" href="/backoffice/imports/templates/charge-targets">字段说明</a><a class="ghost-link" href="/api/imports/templates/charge-targets.csv">下载 CSV 模板</a></div><div class="hint">模板不包含内部租户或项目编号，系统会按当前登录公司和项目写入。</div></div></aside>
<aside class="card"><div class="card-h">上传文件登记</div><div class="card-b">{upload}<p class="sub">客户上传文件进入当前租户目录，系统模板、配置、日志和备份保存在系统目录。</p><div class="hint">预览不会写库；确认导入才写入有效行，错误行不会污染正式数据。</div></div></aside></section>
{_render_import_batches(batches or [])}
{render_import_activity(files, logs)}'''
    return _page('数据导入', body)


def _upload_form():
    return '''<form method="post" action="/backoffice/imports/files/register"><label>文件名</label><input name="original_name" required placeholder="例如 业主房间.xlsx"><label>文件大小 Byte</label><input name="file_size" type="number" min="1" required value="1"><label>内容类型</label><input name="content_type" placeholder="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"><button class="primary">登记上传文件</button></form>'''


def _preview_form():
    sample = 'owner_name,owner_phone,building,unit,room_number,category,area\n张三,13800000000,1栋,1单元,101,居民,80'
    return f'''<form method="post" action="/backoffice/imports/charge-targets/preview"><label>CSV 内容</label><textarea name="csv_text" rows="10" style="width:100%;border:1px solid var(--line);border-radius:12px;padding:10px" placeholder="{_h(sample)}"></textarea><button class="primary">导入预览</button><div class="hint">预览阶段不会写入收费对象。</div></form>'''


def _render_import_batches(batches):
    rows = ''.join(_batch_row(row) for row in batches[-8:]) or '<tr><td colspan="6">暂无导入批次</td></tr>'
    return f"""<section class="card" style="margin-top:18px"><div class="card-h">导入批次记录</div><div class="card-b"><table><thead><tr><th>批次</th><th>状态</th><th>有效</th><th>错误</th><th>错误行</th><th>入口</th></tr></thead><tbody>{rows}</tbody></table><div class="hint">批次记录来自当前租户和项目的预览缓存；客户上传文件记录与系统审计、系统模板分开展示。</div></div></section>"""


def _batch_row(row):
    import_id = row.get('import_id')
    status = '已确认' if row.get('confirmed') else '待确认'
    error_link = f'<a class="ghost-link" href="/api/imports/{_h(import_id)}/errors.csv">下载错误行</a>' if row.get('error_count') else '-'
    return f"""<tr><td>批次 {_h(import_id)}</td><td>{status}</td><td>有效 {_h(row.get('valid_count'))} 行</td><td>错误 {_h(row.get('error_count'))} 行</td><td>{error_link}</td><td><a class="ghost-link" href="/backoffice/imports/{_h(import_id)}/review">复核批次</a></td></tr>"""


def _tenant_import_batches(service, user):
    rows = []
    for import_id, item in sorted(service.imports.items()):
        if int(item.get('tenant_id')) != int(user.get('tenant_id')) or int(item.get('project_id')) != int(user.get('project_id')):
            continue
        rows.append({'import_id': import_id, 'valid_count': len(item.get('valid_rows') or []), 'error_count': len(item.get('errors') or []), 'confirmed': bool(item.get('confirmed'))})
    return rows


def _render_review_page(user, review):
    valid_rows = ''.join(_valid_row(row) for row in review['valid_rows']) or '<tr><td colspan="7">暂无有效行</td></tr>'
    error_rows = ''.join(f'<tr><td>{_h(err.get("row"))}</td><td>{_h((err.get("error") or "").replace("不能为空", "必填"))}</td></tr>' for err in review['errors']) or '<tr><td colspan="2">暂无错误</td></tr>'
    status = '已确认' if review.get('confirmed') else '待确认'
    action = '<p class="sub">该批次已确认过，本次不会重复写入。</p>' if review.get('confirmed') else f"""<form method="post" action="/backoffice/imports/charge-targets/confirm"><input type="hidden" name="import_id" value="{_h(review['import_id'])}"><button class="primary">确认导入</button></form>"""
    body = f"""
<section class="hero"><div><h1>导入批次复核</h1><div class="sub">批次 {review['import_id']} · 状态：{status}。复核有效行和错误行后再确认写入。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">批次 {review['import_id']}</div><div class="card-b"><p><strong>状态：{status}</strong></p><p>有效 {review['valid_count']} 行，错误 {review['error_count']} 行。</p>{_error_download_link(review)}{action}</div></section>
<section class="grid"><div class="card"><div class="card-h">有效行</div><div class="card-b"><table><thead><tr><th>业主</th><th>联系电话</th><th>楼栋/区域</th><th>单元/分区</th><th>房号/铺位号</th><th>类型</th><th>面积</th></tr></thead><tbody>{valid_rows}</tbody></table></div></div>
<aside class="card"><div class="card-h">错误行</div><div class="card-b"><table><thead><tr><th>行号</th><th>错误</th></tr></thead><tbody>{error_rows}</tbody></table></div></aside></section>"""
    return _page('导入批次复核', body)


def _template_rows():
    fields = [
        ('owner_name', '业主姓名', '选填', '例如 张三、某某商户'),
        ('owner_phone', '联系电话', '选填', '例如 13800000000'),
        ('owner_type', '业主类型', '选填', '例如 业主、住户、商户'),
        ('building', '楼栋 / 区域', '必填', '例如 1栋、商场、A区'),
        ('unit', '单元 / 分区', '选填', '例如 1单元、二层、东区'),
        ('room_number', '房号 / 铺位号', '必填', '例如 101、A-001'),
        ('floor', '楼层', '选填', '整数，例如 3'),
        ('shop_name', '店名', '选填', '商户或铺位店名'),
        ('tenant_name', '承租人', '选填', '承租人姓名'),
        ('tenant_phone', '承租电话', '选填', '承租人联系电话'),
        ('category', '类型', '必填', '例如 居民、商户、车位'),
        ('area', '面积', '必填', '数字，单位平方米'),
        ('unit_price_override', '独立单价', '选填', '商户/铺位差异化收费单价'),
        ('payment_cycle', '缴费周期', '选填', '例如 monthly、quarterly'),
        ('notes', '备注', '选填', '补充说明'),
    ]
    return ''.join(
        '<tr>'
        f'<td>{_h(code)}</td><td>{_h(label)}</td><td>{_h(required)}</td><td>{_h(note)}</td>'
        '</tr>'
        for code, label, required, note in fields
    )


def _render_template_page(user, business_template='residential'):
    body = f'''
<section class="hero"><div><h1>收费对象导入模板</h1><div class="sub">不同公司业务可以不同，但第一版 SaaS 收费对象导入统一使用楼栋 / 区域、单元 / 分区、房号 / 铺位号、类型、面积七个字段。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">字段说明</div><div class="card-b"><table><thead><tr><th>CSV 字段</th><th>业务名称</th><th>是否必填</th><th>填写说明</th></tr></thead><tbody>{_template_rows()}</tbody></table><div class="actions" style="margin-top:14px"><a class="ghost-link" href="/api/imports/templates/charge-targets.csv?business_template={_h(business_template)}">下载 CSV 模板</a><a class="ghost-link" href="/backoffice/imports">返回数据导入</a></div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">导入规则</div><div class="card-b"><p class="sub">导入预览不会写库；确认导入才写入有效行，错误行不会污染正确行。</p><p class="sub">旧表头兼容：业主姓名、联系电话、楼栋/区域、单元/分区、房号/铺位号、面积等桌面旧模板字段可以继续预览导入。</p><p class="sub">客户上传文件只进入当前租户目录；系统会自动使用当前登录公司和项目，不允许客户在模板里填写或覆盖内部编号。</p></div></section>{render_template_summary(business_template)}'''
    return _page('收费对象导入模板', body)


def _error_download_link(review):
    if not review.get('error_count'):
        return ''
    import_id = _h(review.get('import_id'))
    return f'<div class="actions" style="margin-bottom:12px"><a class="ghost-link" href="/api/imports/{import_id}/errors.csv">下载错误行 CSV</a></div><div class="hint">修正后可重新复制到导入预览；错误行下载不包含内部租户或项目编号。</div>'


def _error_csv(review):
    output = io.StringIO()
    fieldnames = ['row', 'error'] + CHARGE_TARGET_TEMPLATE_HEADERS
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for err in review.get('errors', []):
        data = normalize_import_row(err.get('data') or {})
        writer.writerow({'row': err.get('row'), 'error': err.get('error'), **{key: data.get(key, '') for key in CHARGE_TARGET_TEMPLATE_HEADERS}})
    return output.getvalue()


def _render_preview(user, review):
    valid_rows = ''.join(_valid_row(row) for row in review['valid_rows']) or '<tr><td colspan="7">暂无有效行</td></tr>'
    error_rows = ''.join(f'<tr><td>{_h(err.get("row"))}</td><td>{_h((err.get("error") or "").replace("不能为空", "必填"))}</td></tr>' for err in review['errors']) or '<tr><td colspan="2">暂无错误</td></tr>'
    body = f'''
<section class="hero"><div><h1>导入预览</h1><div class="sub">有效 {review['valid_count']} 行，错误 {review['error_count']} 行。确认导入只会写入有效行。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="grid"><div class="card"><div class="card-h">有效行</div><div class="card-b"><table><thead><tr><th>业主</th><th>联系电话</th><th>楼栋/区域</th><th>单元/分区</th><th>房号/铺位号</th><th>类型</th><th>面积</th></tr></thead><tbody>{valid_rows}</tbody></table><form method="post" action="/backoffice/imports/charge-targets/confirm"><input type="hidden" name="import_id" value="{_h(review['import_id'])}"><button class="primary">确认导入</button></form></div></div>
<aside class="card"><div class="card-h">错误行</div><div class="card-b">{_error_download_link(review)}<table><thead><tr><th>行号</th><th>错误</th></tr></thead><tbody>{error_rows}</tbody></table></div></aside></section>'''
    return _page('导入预览', body)


def _render_confirm_result(user, import_id, result, already_confirmed=False):
    note = '<p class="sub">该批次已确认过，本次不会重复写入。</p>' if already_confirmed else '<p class="sub">只写入有效行；错误行未污染正式数据。</p>'
    body = (f'<section class="hero"><div><h1>导入结果</h1>'
            f'<div class="sub">导入批次摘要：确认导入后请核对成功和跳过数量，再进入收费对象列表检查。</div></div>'
            f'<div class="badge tenant-scope">{_h(user.get("tenant_name"))} · {_h(user.get("project_name"))}</div></section>'
            f'<section class="card"><div class="card-h">导入批次摘要</div><div class="card-b">'
            f'<p><strong>批次 ID：{_h(import_id)}</strong></p>'
            f'<p>成功导入：{str(result.get("created_count", 0))}</p>'
            f'<p>跳过错误：{str(result.get("skipped_count", 0))}</p>'
            f'<p>重复跳过：{str(result.get("duplicate_skipped_count", 0))}</p>{note}'
            f'<div class="actions"><a class="ghost-link" href="/backoffice/charge-targets">查看收费对象</a>'
            f'<a class="ghost-link" href="/backoffice/imports">继续导入</a></div></div></section>')
    return _page('导入结果', body)


def _valid_row(row):
    return f'''<tr><td>{_h(row.get('owner_name'))}</td><td>{_h(row.get('owner_phone'))}</td><td>{_h(row.get('building'))}</td><td>{_h(row.get('unit'))}</td><td>{_h(row.get('room_number'))}</td><td>{_h(row.get('category'))}</td><td>{_h(row.get('area'))}</td></tr>'''


def register_import_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

    def _activity(user):
        if repository:
            files = repository.list_import_files(user['tenant_id'], user['project_id'])
            logs = repository.list_audit_logs(user['tenant_id'], user['project_id'])
        else:
            files = []
            logs = service.list_audit_logs(user, user['project_id'])
        return files, logs

    @app.get('/backoffice/imports', response_class=HTMLResponse)
    def import_page(user=Depends(current_user)):
        files, logs = _activity(user)
        return HTMLResponse(_render_import_home(user, files=files, logs=logs, batches=_tenant_import_batches(service, user)))

    @app.get('/backoffice/imports/{import_id}/review', response_class=HTMLResponse)
    def import_batch_review_page(import_id: int, user=Depends(current_user)):
        try:
            review = service.get_import_review(user, user['project_id'], import_id)
            return HTMLResponse(_render_review_page(user, review))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/imports/templates/charge-targets', response_class=HTMLResponse)
    def import_template_page(user=Depends(current_user), business_template: str = ''):
        selected = business_template or template_code_for_user(service, repository, user)
        return HTMLResponse(_render_template_page(user, selected))

    @app.get('/api/imports/templates/charge-targets.csv')
    def import_template_csv(user=Depends(current_user), business_template: str = '', current_tenant: str = ''):
        selected = template_code_for_user(service, repository, user) if current_tenant else business_template
        csv_text = template_csv(selected) if selected else TEMPLATE_CSV
        return PlainTextResponse(csv_text, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="charge_targets_template.csv"'})


    @app.get('/api/imports/{import_id}/errors.csv')
    def import_errors_csv(import_id: int, user=Depends(current_user)):
        try:
            review = service.get_import_review(user, user['project_id'], import_id)
            return PlainTextResponse(
                _error_csv(review),
                media_type='text/csv; charset=utf-8',
                headers={'Content-Disposition': 'attachment; filename="charge_targets_errors.csv"'},
            )
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/imports/files/register', response_class=HTMLResponse)
    def register_import_file_page(original_name: str = Form(...), file_size: int = Form(...), content_type: str = Form(''), user=Depends(current_user)):
        try:
            service._require(user, 'import')
            storage_key = STORAGE.upload_path(user['tenant_id'], user['project_id'], 1_000_000 + user['id'], 'imports', original_name)
            if repository:
                item = repository.create_import_file(user['tenant_id'], user['project_id'], 'charge_targets', original_name, storage_key, file_size, content_type)
            else:
                item = {'id': 1_000_000 + user['id'], 'original_name': original_name, 'storage_key': storage_key}
            files, logs = _activity(user)
            return HTMLResponse(_render_import_home(user, item, files, logs, _tenant_import_batches(service, user)))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/imports/charge-targets/preview', response_class=HTMLResponse)
    def preview_import_page(csv_text: str = Form(''), user=Depends(current_user)):
        try:
            rows = _parse_csv_rows(csv_text)
            preview = service.preview_charge_target_import(user, user['project_id'], rows)
            review = service.get_import_review(user, user['project_id'], preview['import_id'])
            return HTMLResponse(_render_preview(user, review))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/imports/charge-targets/confirm', response_class=HTMLResponse)
    def confirm_import_page(import_id: int = Form(...), user=Depends(current_user)):
        try:
            already_confirmed = False
            if repository:
                service._require(user, 'import')
                review = service.get_import_review(user, user['project_id'], import_id)
                already_confirmed = bool(review['confirmed'])
                if already_confirmed:
                    result = {'created_count': 0, 'skipped_count': review['error_count'], 'duplicate_skipped_count': 0}
                else:
                    rows_to_create, duplicate_rows = split_new_and_duplicates(
                        review['valid_rows'], repository.list_charge_targets(user['tenant_id'], user['project_id'])
                    )
                    duplicate_skipped = len(duplicate_rows)
                    created = owner_created = 0
                    for row in rows_to_create:
                        owner_id = int(row.get('owner_id') or 0)
                        if row.get('owner_name'):
                            owner = repository.create_owner(user['tenant_id'], user['project_id'], row['owner_name'], row.get('owner_phone', ''), row.get('owner_type', '业主'))
                            owner_id = owner['id']
                        item = repository.create_charge_target(user['tenant_id'], user['project_id'], row['building'], row.get('unit', ''), row['room_number'], row.get('category', '居民'), row['area'], owner_id, row.get('unit_price_override'), floor=row.get('floor'), shop_name=row.get('shop_name', ''), tenant_name=row.get('tenant_name', ''), tenant_phone=row.get('tenant_phone', ''), payment_cycle=row.get('payment_cycle', ''), notes=row.get('notes', ''))
                        service.targets[item['id']] = item
                        created += 1
                    service.imports[import_id]['confirmed'] = True
                    skipped_total = review['error_count'] + duplicate_skipped
                    repository.create_audit_log(user['tenant_id'], user['project_id'], user['id'], 'import.confirm', 'import', import_id, {'created_count': created, 'skipped_count': skipped_total, 'duplicate_skipped_count': duplicate_skipped})
                    result = {'created_count': created, 'skipped_count': skipped_total, 'duplicate_skipped_count': duplicate_skipped}
            else:
                before = service.get_import_review(user, user['project_id'], import_id)
                already_confirmed = bool(before['confirmed'])
                result = service.confirm_charge_target_import(user, user['project_id'], import_id)
            return HTMLResponse(_render_confirm_result(user, import_id, result, already_confirmed))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
