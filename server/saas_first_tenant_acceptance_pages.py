#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant delivery acceptance record page."""

from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page

ITEMS = [
    '客户公司已创建', '项目已创建', '管理员已创建', '授权已绑定', '导入模板已确认',
    '收费项目已配置', '测试账单已生成', '测试收款已登记', '报表已核对',
    '租户隔离已验收', '备份恢复已演练',
]


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
        'tenant_name': user.get('tenant_name'),
        'project_name': user.get('project_name'),
        'operator_name': operator_name,
        'customer_signer': customer_signer,
        'notes': notes,
        'checked': list(checked),
        'checked_count': len(checked),
        'total_count': len(ITEMS),
    }
    records.append(record)
    return record


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


def _render(user, service, message=''):
    records = _records(service, user)
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    body = f'''
<section class="hero"><div><h1>首租户交付验收记录</h1><div class="sub">用于正式商业版首租户上线签收：实施人员勾选核心交付项，留存客户签收人、备注和当前客户范围记录。客户上传数据与系统自身数据隔离，验收记录不展示内部编号或生产密钥。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>{notice}
<section class="grid"><div class="card"><div class="card-h">验收表单</div><div class="card-b"><form method="post" action="/backoffice/first-tenant-acceptance"><div class="sub" style="margin-bottom:10px">请逐项确认首租户上线交付内容。</div>{_item_inputs(ITEMS)}<label>实施人员</label><input name="operator_name" required placeholder="例如 实施顾问A"><label>客户签收人</label><input name="customer_signer" required placeholder="例如 客户负责人B"><label>备注</label><input name="notes" placeholder="例如 首租户上线验收完成"><button class="primary">保存验收记录</button><div class="hint">记录只保存验收摘要，不保存密码、密钥、内部租户编号或客户上传文件内容。</div></form></div></div>
<aside class="card"><div class="card-h">验收边界</div><div class="card-b"><p class="sub">客户上传数据与系统自身数据隔离。</p><p class="sub">业务数据不进入授权云服务。</p><p class="sub">租户隔离、备份恢复和报表核对必须完成后再签收。</p><a class="ghost-link" href="/backoffice/first-tenant-wizard">返回首租户向导</a></div></aside></section>
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
