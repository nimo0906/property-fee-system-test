#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML owner directory pages for SaaS backoffice."""

from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _room_label(target):
    parts = [target.get('building'), target.get('unit'), target.get('room_number')]
    return '-'.join(str(part) for part in parts if part)


def _owner_rows(owners, targets):
    rooms_by_owner = {}
    for target in targets:
        owner_id = target.get('owner_id')
        if owner_id:
            rooms_by_owner.setdefault(owner_id, []).append(_room_label(target))
    rows = []
    for owner in owners:
        bound = rooms_by_owner.get(owner.get('id'), [])
        room_text = '、'.join(bound) if bound else '未绑定'
        rows.append(
            f'''<tr><td>{_h(owner.get('id'))}</td><td><strong>{_h(owner.get('name'))}</strong></td>'''
            f'''<td>{_h(owner.get('phone'))}</td><td>{_h(owner.get('owner_type'))}</td>'''
            f'''<td>{_h(room_text)}</td></tr>'''
        )
    return ''.join(rows) or '<tr><td colspan="5">暂无业主档案</td></tr>'


def _create_form(can_write):
    if not can_write:
        return '<div class="hint">当前角色只能查看业主档案，不能新增。</div>'
    return '''<form method="post" action="/backoffice/owners/create"><label>业主姓名</label><input name="name" required placeholder="例如 张三"><label>联系电话</label><input name="phone" placeholder="手机号"><label>类型</label><select name="owner_type"><option value="业主">业主</option><option value="住户">住户</option><option value="商户">商户</option></select><button class="primary">新增业主</button><div class="hint">新增后到收费对象页面绑定房间 / 铺位。</div></form>'''


def _summary(owners, targets):
    bound_owner_ids = {t.get('owner_id') for t in targets if t.get('owner_id')}
    merchant_count = sum(1 for o in owners if o.get('owner_type') == '商户')
    metrics = [
        ('业主总数', len(owners)),
        ('已绑定业主', len(bound_owner_ids)),
        ('商户档案', merchant_count),
        ('绑定房间/铺位', len([t for t in targets if t.get('owner_id')])),
    ]
    return '<section class="metric-grid">' + ''.join(
        f'<div class="metric"><div>{_h(label)}</div><strong>{_h(value)}</strong></div>' for label, value in metrics
    ) + '</section>'


def _render_owner_page(user, owners, targets, message=''):
    can_write = user.get('role_code') in {'platform_admin', 'system_admin', 'finance', 'frontdesk'}
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    body = f'''
<section class="hero"><div><h1>业主档案</h1><div class="sub">维护业主、住户、商户联系人，并核对已绑定房间 / 铺位；所有数据按当前租户和项目隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{notice}
{_summary(owners, targets)}
<section class="card" style="margin-bottom:18px"><div class="card-h">快速操作</div><div class="card-b"><div class="actions"><a class="ghost-link" href="/backoffice/charge-targets">绑定房间/铺位</a><a class="ghost-link" href="/backoffice/imports/templates/charge-targets">下载导入模板</a><a class="ghost-link" href="/backoffice/imports">Excel 导入</a></div><div class="hint">第 4 模块只维护收费对象、业主、房间 / 铺位，不进入后续模块。</div></div></section>
<section class="grid"><div class="card"><div class="card-h">业主档案列表</div><div class="card-b"><table><thead><tr><th>ID</th><th>业主</th><th>联系电话</th><th>类型</th><th>绑定房间/铺位</th></tr></thead><tbody>{_owner_rows(owners, targets)}</tbody></table></div></div><aside class="card"><div class="card-h">新增业主</div><div class="card-b">{_create_form(can_write)}</div></aside></section>'''
    return _page('业主档案', body)


def register_owner_pages(app, service, repository, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    def _items_for(user):
        service._require(user, 'read')
        if repository:
            return (
                repository.list_owners(user['tenant_id'], user['project_id']),
                repository.list_charge_targets(user['tenant_id'], user['project_id']),
            )
        return service.list_owners(user, user['project_id']), service.list_charge_targets(user, user['project_id'])

    @app.get('/backoffice/owners', response_class=HTMLResponse)
    def owner_page(user=Depends(current_user), message: str = ''):
        try:
            owners, targets = _items_for(user)
            return HTMLResponse(_render_owner_page(user, owners, targets, message))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
