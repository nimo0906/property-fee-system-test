#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant delivery acceptance record page."""

from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page

ITEMS = [
    '客户公司已创建', '项目已创建', '管理员已创建', '授权已绑定', '导入模板已确认',
    '收费项目已配置', '推荐收费项目已初始化', '收费项目单价已按客户标准复核',
    '计费方式已确认', '业务模板与收费项目匹配', '测试账单已生成', '测试收款已登记', '报表已核对',
    '租户隔离已验收', '备份恢复已演练',
]

FEE_REVIEW_ITEMS = [
    '推荐收费项目已初始化',
    '收费项目单价已按客户标准复核',
    '计费方式已确认',
    '业务模板与收费项目匹配',
]


def _risk_summary(record):
    checked = set(record.get('checked') or [])
    missing_fee = [item for item in FEE_REVIEW_ITEMS if item not in checked]
    missing_count = len(ITEMS) - len(checked)
    if not missing_fee and missing_count == 0:
        return {'status': '验收风险已解除', 'detail': '全部验收项已完成，可以进入客户签收。'}
    parts = []
    if missing_count:
        parts.append(f'完成项不足：仍有 {missing_count} 项未确认')
    if missing_fee:
        parts.append('金额配置复核未完成：' + '、'.join(missing_fee))
    return {'status': '验收风险', 'detail': '；'.join(parts) + '。上线前请勿签收。'}


def _risk_panel(record):
    risk = _risk_summary(record)
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">{_h(risk['status'])}</div><div class="card-b"><p class="sub">{_h(risk['detail'])}</p></div></section>'''


def _records(service, user):
    records = getattr(service, 'first_tenant_acceptance_records', None)
    if records is None:
        records = []
        setattr(service, 'first_tenant_acceptance_records', records)
    return [r for r in records if r.get('tenant_name') == user.get('tenant_name') and r.get('project_name') == user.get('project_name')]


def _append_record(service, user, checked, operator_name, customer_signer, notes):
    records = getattr(service, 'first_tenant_acceptance_records', None)
    if records is None:
        records = []
        setattr(service, 'first_tenant_acceptance_records', records)
    record = {
        'tenant_name': user.get('tenant_name'), 'project_name': user.get('project_name'),
        'operator_name': operator_name, 'customer_signer': customer_signer, 'notes': notes,
        'checked': list(checked), 'checked_count': len(checked), 'total_count': len(ITEMS),
    }
    records.append(record)
    return record


def _latest_record(service, user):
    rows = _records(service, user)
    return rows[-1] if rows else {
        'tenant_name': user.get('tenant_name'), 'project_name': user.get('project_name'),
        'operator_name': '', 'customer_signer': '', 'notes': '', 'checked': [],
        'checked_count': 0, 'total_count': len(ITEMS),
    }


def _item_inputs(selected=None):
    selected = set(selected or [])
    return ''.join(
        f'<label class="inline"><input type="checkbox" name="items" value="{_h(item)}" {"checked" if item in selected else ""}> {_h(item)}</label>'
        for item in ITEMS
    )


def _record_rows(records):
    rows = ''.join(
        f'<tr><td>{_h(row.get("operator_name"))}</td><td>{_h(row.get("customer_signer"))}</td><td>{_h(row.get("checked_count"))} / {len(ITEMS)}</td><td>{_h(row.get("notes"))}</td></tr>'
        for row in records
    )
    return rows or '<tr><td colspan="4">暂无验收记录</td></tr>'


def _print_item_rows(record):
    checked = set(record.get('checked') or [])
    return ''.join(
        f'<tr><td>{_h(item)}</td><td>{"已完成" if item in checked else "未确认"}</td></tr>'
        for item in ITEMS
    )


def _printable_html(user, service):
    record = _latest_record(service, user)
    item_rows = _print_item_rows(record)
    risk = _risk_summary(record)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>首租户交付验收记录（打印版）</title><style>body{{font:14px/1.7 "Songti SC","SimSun",serif;color:#111;margin:32px}}h1{{text-align:center;font-size:24px}}table{{width:100%;border-collapse:collapse;margin:14px 0}}td,th{{border:1px solid #333;padding:8px;text-align:left}}.meta{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:18px 0}}.sign{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;margin-top:42px}}.line{{border-bottom:1px solid #111;height:34px}}.toolbar{{margin-bottom:16px}}button{{padding:8px 14px}}@media print{{.toolbar{{display:none}}body{{margin:18mm}}}}</style></head><body><div class="toolbar"><button onclick="window.print()">打印验收记录</button></div><h1>首租户交付验收记录（打印版）</h1><div class="meta"><div>客户公司：{_h(user.get('tenant_name'))}</div><div>项目名称：{_h(user.get('project_name'))}</div><div>实施人员：{_h(record.get('operator_name'))}</div><div>客户签收人：{_h(record.get('customer_signer'))}</div><div>完成项：{_h(record.get('checked_count'))} / {len(ITEMS)}</div><div>备注：{_h(record.get('notes'))}</div><div>风险状态：{_h(risk.get('status'))}</div><div>风险说明：{_h(risk.get('detail'))}</div></div><table><thead><tr><th>验收项</th><th>状态</th></tr></thead><tbody>{item_rows}</tbody></table><p>客户上传数据与系统自身数据隔离；业务数据不进入授权云服务；租户隔离、备份恢复和报表核对完成后签收。</p><div class="sign"><div>客户签字<div class="line"></div></div><div>实施人员签字<div class="line"></div></div><div>签收日期<div class="line"></div></div></div></body></html>'''


def _render(user, service, message=''):
    records = _records(service, user)
    latest = _latest_record(service, user)
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    body = f'''
<section class="hero"><div><h1>首租户交付验收记录</h1><div class="sub">用于正式商业版首租户上线签收：实施人员勾选核心交付项，留存客户签收人、备注和当前客户范围记录。客户上传数据与系统自身数据隔离，验收记录不展示内部编号或生产密钥。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>{notice}
{_risk_panel(latest)}
<section class="grid"><div class="card"><div class="card-h">验收表单</div><div class="card-b"><form method="post" action="/backoffice/first-tenant-acceptance"><div class="sub" style="margin-bottom:10px">请逐项确认首租户上线交付内容，金额配置复核必须覆盖推荐收费项目、单价、计费方式和业务模板匹配。</div>{_item_inputs(ITEMS)}<label>实施人员</label><input name="operator_name" required placeholder="例如 实施顾问A"><label>客户签收人</label><input name="customer_signer" required placeholder="例如 客户负责人B"><label>备注</label><input name="notes" placeholder="例如 首租户上线验收完成"><button class="primary">保存验收记录</button><div class="hint">记录只保存验收摘要，不保存密码、密钥、内部租户编号或客户上传文件内容。</div></form></div></div>
<aside class="card"><div class="card-h">验收边界</div><div class="card-b"><p class="sub">客户上传数据与系统自身数据隔离。</p><p class="sub">业务数据不进入授权云服务。</p><p class="sub">租户隔离、备份恢复和报表核对必须完成后再签收。</p><div class="actions"><a class="ghost-link" href="/backoffice/first-tenant-wizard">返回首租户向导</a><a class="ghost-link" href="/backoffice/first-tenant-acceptance/print">打印验收记录</a><a class="ghost-link" href="/backoffice/first-tenant-acceptance/export.html">导出 HTML 验收记录</a></div></div></aside></section>
<section class="card" style="margin-top:18px"><div class="card-h">已保存记录</div><div class="card-b"><table><thead><tr><th>实施人员</th><th>客户签收人</th><th>完成项</th><th>备注</th></tr></thead><tbody>{_record_rows(records)}</tbody></table></div></section>'''
    return _page('首租户交付验收记录', body)


def register_first_tenant_acceptance_pages(app, service, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse
    from typing import List
    import urllib.parse

    def _require_admin(user):
        if user.get('role_code') not in {'system_admin', 'platform_admin'}:
            raise PermissionDenied('admin only')

    @app.get('/backoffice/first-tenant-acceptance', response_class=HTMLResponse)
    def acceptance_record_page(user=Depends(current_user), message: str = ''):
        try:
            _require_admin(user)
            return HTMLResponse(_render(user, service, message))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/first-tenant-acceptance/print', response_class=HTMLResponse)
    def acceptance_record_print(user=Depends(current_user)):
        try:
            _require_admin(user)
            return HTMLResponse(_printable_html(user, service))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/first-tenant-acceptance/export.html')
    def acceptance_record_export(user=Depends(current_user)):
        try:
            _require_admin(user)
            response = HTMLResponse(_printable_html(user, service))
            response.headers['content-disposition'] = 'attachment; filename="first-tenant-acceptance.html"'
            return response
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/first-tenant-acceptance')
    def acceptance_record_submit(operator_name: str = Form(...), customer_signer: str = Form(...), notes: str = Form(''), items: List[str] = Form([]), user=Depends(current_user)):
        try:
            _require_admin(user)
            checked = [item for item in items if item in ITEMS]
            _append_record(service, user, checked, operator_name.strip(), customer_signer.strip(), notes.strip())
            query = urllib.parse.urlencode({'message': '验收记录已保存'})
            return RedirectResponse(f'/backoffice/first-tenant-acceptance?{query}', status_code=303)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
