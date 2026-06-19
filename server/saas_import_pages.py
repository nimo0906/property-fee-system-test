#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML import review pages for SaaS backoffice."""

import csv
import io

from server.saas_import_activity import display_filename, render_import_activity
from server.saas_service import PermissionDenied
from server.saas_storage import SaasStorage
from server.saas_user_pages import _h, _page

STORAGE = SaasStorage(root_dir='/var/lib/property-saas')
TEMPLATE_CSV = 'building,unit,room_number,category,area\n1栋,1单元,101,居民,80\n商场,一层,A-001,商户,56.5\n'


def _parse_csv_rows(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text or ''))
    return [dict(row) for row in reader]


def _render_file_notice(item):
    if not item:
        return ''
    display_name = display_filename(item.get('original_name'))
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">文件已登记</div><div class="card-b"><p class="sub">原始文件：{_h(display_name)}</p><p class="sub">存储位置：{_h(item.get('storage_key'))}</p><div class="hint">文件登记只保存租户内存储元数据；后续预览仍需人工确认，不会自动写库。</div></div></section>'''


def _render_import_home(user, file_item=None, files=None, logs=None):
    can_import = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    form = _preview_form() if can_import else '<div class="hint">当前角色不能导入，只能查看业务数据。</div>'
    upload = _upload_form() if can_import else '<div class="hint">当前角色不能登记上传文件。</div>'
    body = f'''
<section class="hero"><div><h1>数据导入</h1><div class="sub">先预览校验，不直接写库；确认后只导入有效行，错误行不会污染正式数据。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{_render_file_notice(file_item)}
<section class="grid"><div class="card"><div class="card-h">收费对象导入</div><div class="card-b">{form}</div></div>
<aside class="card"><div class="card-h">导入模板</div><div class="card-b"><p class="sub">先按模板准备收费对象数据，再复制 CSV 内容做预览。</p><div class="actions"><a class="ghost-link" href="/backoffice/imports/templates/charge-targets">字段说明</a><a class="ghost-link" href="/api/imports/templates/charge-targets.csv">下载 CSV 模板</a></div><div class="hint">模板不包含 tenant_id 或 project_id，系统会按当前登录租户和项目写入。</div></div></aside>
<aside class="card"><div class="card-h">上传文件登记</div><div class="card-b">{upload}<p class="sub">客户上传文件进入当前租户目录，系统模板、配置、日志和备份保存在系统目录。</p><div class="hint">预览不会写库；确认导入才写入有效行，错误行不会污染正式数据。</div></div></aside></section>
{render_import_activity(files, logs)}'''
    return _page('数据导入', body)


def _upload_form():
    return '''<form method="post" action="/backoffice/imports/files/register"><label>文件名</label><input name="original_name" required placeholder="例如 业主房间.xlsx"><label>文件大小 Byte</label><input name="file_size" type="number" min="1" required value="1"><label>内容类型</label><input name="content_type" placeholder="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"><button class="primary">登记上传文件</button></form>'''


def _preview_form():
    sample = 'building,unit,room_number,category,area\n1栋,1单元,101,居民,80'
    return f'''<form method="post" action="/backoffice/imports/charge-targets/preview"><label>CSV 内容</label><textarea name="csv_text" rows="10" style="width:100%;border:1px solid var(--line);border-radius:12px;padding:10px" placeholder="{_h(sample)}"></textarea><button class="primary">导入预览</button><div class="hint">预览阶段不会写入收费对象。</div></form>'''


def _template_rows():
    fields = [
        ('building', '楼栋 / 区域', '必填', '例如 1栋、商场、A区'),
        ('unit', '单元 / 分区', '选填', '例如 1单元、二层、东区'),
        ('room_number', '房号 / 铺位号', '必填', '例如 101、A-001'),
        ('category', '类型', '必填', '例如 居民、商户、车位'),
        ('area', '面积', '必填', '数字，单位平方米'),
    ]
    return ''.join(
        '<tr>'
        f'<td>{_h(code)}</td><td>{_h(label)}</td><td>{_h(required)}</td><td>{_h(note)}</td>'
        '</tr>'
        for code, label, required, note in fields
    )


def _render_template_page(user):
    body = f'''
<section class="hero"><div><h1>收费对象导入模板</h1><div class="sub">不同公司业务可以不同，但第一版 SaaS 收费对象导入统一使用楼栋 / 区域、单元 / 分区、房号 / 铺位号、类型、面积五个字段。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">字段说明</div><div class="card-b"><table><thead><tr><th>CSV 字段</th><th>业务名称</th><th>是否必填</th><th>填写说明</th></tr></thead><tbody>{_template_rows()}</tbody></table><div class="actions" style="margin-top:14px"><a class="ghost-link" href="/api/imports/templates/charge-targets.csv">下载 CSV 模板</a><a class="ghost-link" href="/backoffice/imports">返回数据导入</a></div></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">导入规则</div><div class="card-b"><p class="sub">导入预览不会写库；确认导入才写入有效行，错误行不会污染正确行。</p><p class="sub">客户上传文件只进入当前租户目录；系统会自动使用当前登录账号的 tenant_id 和 project_id，不允许客户在模板里填写或覆盖。</p></div></section>'''
    return _page('收费对象导入模板', body)


def _render_preview(user, review):
    valid_rows = ''.join(_valid_row(row) for row in review['valid_rows']) or '<tr><td colspan="5">暂无有效行</td></tr>'
    error_rows = ''.join(f'<tr><td>{_h(err.get("row"))}</td><td>{_h(err.get("error"))}</td></tr>' for err in review['errors']) or '<tr><td colspan="2">暂无错误</td></tr>'
    body = f'''
<section class="hero"><div><h1>导入预览</h1><div class="sub">有效 {review['valid_count']} 行，错误 {review['error_count']} 行。确认导入只会写入有效行。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="grid"><div class="card"><div class="card-h">有效行</div><div class="card-b"><table><thead><tr><th>楼栋/区域</th><th>单元/分区</th><th>房号/铺位号</th><th>类型</th><th>面积</th></tr></thead><tbody>{valid_rows}</tbody></table><form method="post" action="/backoffice/imports/charge-targets/confirm"><input type="hidden" name="import_id" value="{_h(review['import_id'])}"><button class="primary">确认导入</button></form></div></div>
<aside class="card"><div class="card-h">错误行</div><div class="card-b"><table><thead><tr><th>行号</th><th>错误</th></tr></thead><tbody>{error_rows}</tbody></table></div></aside></section>'''
    return _page('导入预览', body)


def _valid_row(row):
    return f'''<tr><td>{_h(row.get('building'))}</td><td>{_h(row.get('unit'))}</td><td>{_h(row.get('room_number'))}</td><td>{_h(row.get('category'))}</td><td>{_h(row.get('area'))}</td></tr>'''


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
        return HTMLResponse(_render_import_home(user, files=files, logs=logs))

    @app.get('/backoffice/imports/templates/charge-targets', response_class=HTMLResponse)
    def import_template_page(user=Depends(current_user)):
        return HTMLResponse(_render_template_page(user))

    @app.get('/api/imports/templates/charge-targets.csv')
    def import_template_csv(user=Depends(current_user)):
        return PlainTextResponse(TEMPLATE_CSV, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="charge_targets_template.csv"'})

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
            return HTMLResponse(_render_import_home(user, item, files, logs))
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

    @app.post('/backoffice/imports/charge-targets/confirm')
    def confirm_import_page(import_id: int = Form(...), user=Depends(current_user)):
        try:
            if repository:
                service._require(user, 'import')
                review = service.get_import_review(user, user['project_id'], import_id)
                if not review['confirmed']:
                    for row in review['valid_rows']:
                        item = repository.create_charge_target(user['tenant_id'], user['project_id'], row['building'], row.get('unit', ''), row['room_number'], row.get('category', '居民'), row['area'])
                        service.targets[item['id']] = item
                    service.imports[import_id]['confirmed'] = True
                    repository.create_audit_log(user['tenant_id'], user['project_id'], user['id'], 'import.confirm', 'import', import_id, {'created_count': review['valid_count'], 'skipped_count': review['error_count']})
            else:
                service.confirm_charge_target_import(user, user['project_id'], import_id)
            return RedirectResponse('/backoffice/charge-targets?message=导入已确认', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
