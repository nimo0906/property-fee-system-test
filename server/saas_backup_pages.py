#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML backup and restore drill pages for SaaS backoffice."""

from urllib.parse import urlencode

from server.saas_backup_activity import _render_boundary_card
from server.saas_backup_view import backup_items, restore_drill_items
from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _backup_rows(records):
    rows = []
    for item in records:
        backup_id = item.get('backup_id')
        rows.append(f'''<tr><td>{_h(backup_id)}</td><td>{_h(item.get('status'))}</td><td>{_h(item.get('created_at', ''))}</td><td>{_h(item.get('created_by_username', ''))}</td><td><a class="ghost-link" href="/backoffice/backups/{_h(backup_id)}">备份详情</a></td></tr>''')
    return ''.join(rows) or '<tr><td colspan="5">暂无备份记录</td></tr>'


def _drill_rows(drills):
    rows = []
    for item in drills:
        rows.append(f'''<tr><td>{_h(item.get('backup_id'))}</td><td>{_h(item.get('scope'))}</td><td>{_h(item.get('status'))}</td><td>{_h(item.get('created_at', ''))}</td><td>{_h(item.get('created_by_username', ''))}</td><td><a class="ghost-link" href="/backoffice/backups/restore-drills/{_h(item.get('id'))}">恢复演练详情</a></td></tr>''')
    return ''.join(rows) or '<tr><td colspan="6">暂无恢复演练记录</td></tr>'


def _forms(can_manage, records):
    if not can_manage:
        return '<div class="hint">当前角色只能查看备份，不能执行备份或恢复演练操作。</div>'
    options = ''.join(f'<option value="{_h(r.get("backup_id"))}">{_h(r.get("backup_id"))}</option>' for r in records)
    drill = '<div class="hint">请先创建备份，再提交恢复演练。</div>'
    if options:
        drill = f'''<form method="post" action="/backoffice/backups/restore-drills"><label>备份ID</label><select name="backup_id" required>{options}</select><label>演练范围</label><select name="scope"><option value="database">database</option><option value="tenant-files">tenant-files</option><option value="system-files">system-files</option></select><button class="primary">提交恢复演练</button></form>'''
    return f'''<form method="post" action="/backoffice/backups/create"><button class="primary">创建备份</button></form><hr>{drill}'''



def _acceptance_backup_notice():
    return '''<section class="card" style="margin-top:18px"><div class="card-h">系统侧验收材料备份范围</div><div class="card-b"><p class="sub">system-files 包含首租户验收记录和系统侧签收证据；恢复演练选择 system-files 时应核对 <code>first_tenant_acceptance/records.json</code> 已随系统侧文件归档。</p><p class="sub">system-files 也必须覆盖生产验收签收历史和当前验收留档：<code>production_acceptance_signoffs/history.json</code>、<code>saas-production-acceptance-result.md</code>。恢复演练选择 system-files 后，应核对生产验收签收历史仍可查看和下载。</p></div></section>'''

def _filter_records(records, drills, params):
    keyword = str(params.get('keyword') or '').strip().lower()
    status = str(params.get('status') or '').strip().lower()
    scope = str(params.get('scope') or '').strip().lower()
    scope_backup_ids = {d.get('backup_id') for d in drills if not scope or scope == str(d.get('scope') or '').lower()}
    rows = []
    for item in records:
        if keyword and keyword not in str(item.get('backup_id') or '').lower():
            continue
        if status and status != str(item.get('status') or '').lower():
            continue
        if scope and item.get('backup_id') not in scope_backup_ids:
            continue
        rows.append(item)
    return rows


def _filter_drills(drills, params):
    keyword = str(params.get('keyword') or '').strip().lower()
    scope = str(params.get('scope') or '').strip().lower()
    rows = []
    for item in drills:
        if keyword and keyword not in str(item.get('backup_id') or '').lower():
            continue
        if scope and scope != str(item.get('scope') or '').lower():
            continue
        rows.append(item)
    return rows


def _paginate(items, page, page_size):
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 20), 100), 1)
    start = (page - 1) * page_size
    return {'total': len(items), 'page': page, 'page_size': page_size, 'items': items[start:start + page_size]}


def _query(params, **changes):
    data = {k: v for k, v in params.items() if v not in ('', None)}
    data.update({k: v for k, v in changes.items() if v not in ('', None)})
    return urlencode(data)


def _filter_card(params):
    size = str(params.get('page_size') or 20)
    selected = lambda value: ' selected' if size == str(value) else ''
    scope_selected = lambda value: ' selected' if params.get('scope') == value else ''
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">高级筛选</div><div class="card-b"><form method="get" action="/backoffice/backups" class="filters"><div><label>关键字</label><input name="keyword" value="{_h(params.get('keyword'))}" placeholder="备份ID"></div><div><label>状态</label><input name="status" value="{_h(params.get('status'))}" placeholder="created / recorded"></div><div><label>演练范围</label><select name="scope"><option value="">全部</option><option value="database"{scope_selected('database')}>database</option><option value="tenant-files"{scope_selected('tenant-files')}>tenant-files</option><option value="system-files"{scope_selected('system-files')}>system-files</option></select></div><div><label>每页</label><select name="page_size"><option value="10"{selected(10)}>10</option><option value="20"{selected(20)}>20</option><option value="50"{selected(50)}>50</option></select></div><div><button class="primary">筛选</button></div></form></div></section>'''


def _pager(result, params):
    page = result['page']
    size = result['page_size']
    total = result['total']
    prev_cls = 'ghost-link disabled' if page <= 1 else 'ghost-link'
    next_cls = 'ghost-link disabled' if page * size >= total else 'ghost-link'
    prev_href = '/backoffice/backups?' + _query(params, page=max(page - 1, 1), page_size=size)
    next_href = '/backoffice/backups?' + _query(params, page=page + 1, page_size=size)
    return f'''<div class="pager"><span>共 {_h(total)} 条 · 第 {_h(page)} 页 · 每页 {_h(size)} 条</span><span class="actions"><a class="{prev_cls}" href="{_h(prev_href)}">上一页</a><a class="{next_cls}" href="{_h(next_href)}">下一页</a></span></div>'''


def _render(user, records, drills=None, params=None):
    params = params or {}
    drills = drills or []
    can_manage = user.get('role_code') in {'system_admin', 'platform_admin'}
    backup_result = _paginate(_filter_records(records, drills, params), params.get('page', 1), params.get('page_size', 20))
    drill_result = _paginate(_filter_drills(drills, params), params.get('page', 1), params.get('page_size', 20))
    body = f'''
<section class="hero"><div><h1>备份记录</h1><div class="sub">记录当前租户和项目的备份与恢复演练。页面不展示真实存储密钥或服务器路径。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
{_filter_card(params)}
<section class="grid"><div class="card"><div class="card-h">备份记录</div><div class="card-b">{_pager(backup_result, params)}<table><thead><tr><th>备份ID</th><th>状态</th><th>创建时间</th><th>操作人</th><th>入口</th></tr></thead><tbody>{_backup_rows(backup_result['items'])}</tbody></table></div></div>
<aside class="card"><div class="card-h">恢复演练</div><div class="card-b">{_forms(can_manage, records)}</div></aside></section>
<section class="card" style="margin-top:18px"><div class="card-h">恢复演练记录</div><div class="card-b">{_pager(drill_result, params)}<table><thead><tr><th>备份ID</th><th>范围</th><th>状态</th><th>创建时间</th><th>操作人</th><th>入口</th></tr></thead><tbody>{_drill_rows(drill_result['items'])}</tbody></table></div></section>
{_acceptance_backup_notice()}
{_render_boundary_card(can_manage)}'''
    return _page('备份记录', body)


def _render_backup_detail(user, record, drills):
    related_rows = _drill_rows([d for d in drills if d.get('backup_id') == record.get('backup_id')])
    body = f'''
<section class="hero"><div><h1>备份详情</h1><div class="sub">只展示备份编号、状态和恢复演练结果，不展示真实服务器路径或密钥。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">备份详情</div><div class="card-b"><table><tbody><tr><th>备份ID</th><td>{_h(record.get('backup_id'))}</td></tr><tr><th>状态</th><td>{_h(record.get('status'))}</td></tr><tr><th>创建时间</th><td>{_h(record.get('created_at', ''))}</td></tr><tr><th>操作人</th><td>{_h(record.get('created_by_username', ''))}</td></tr><tr><th>审计日志</th><td><a class="ghost-link" href="/backoffice/audit-logs/{_h(record.get('audit_log_id'))}">查看审计日志</a></td></tr></tbody></table></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">恢复演练记录</div><div class="card-b"><table><thead><tr><th>备份ID</th><th>范围</th><th>状态</th><th>创建时间</th><th>操作人</th><th>入口</th></tr></thead><tbody>{related_rows}</tbody></table><div class="actions" style="margin-top:16px"><a class="ghost-link" href="/backoffice/backups">返回备份记录</a></div></div></section>
{_acceptance_backup_notice()}'''
    return _page('备份详情', body)


def _render_drill_detail(user, drill):
    body = f'''
<section class="hero"><div><h1>恢复演练详情</h1><div class="sub">恢复演练只记录范围、状态和备份编号，不执行真实恢复，不展示服务器路径或密钥。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">恢复演练详情</div><div class="card-b"><table><tbody><tr><th>备份ID</th><td>{_h(drill.get('backup_id'))}</td></tr><tr><th>范围</th><td>{_h(drill.get('scope'))}</td></tr><tr><th>状态</th><td>{_h(drill.get('status'))}</td></tr><tr><th>创建时间</th><td>{_h(drill.get('created_at', ''))}</td></tr><tr><th>操作人</th><td>{_h(drill.get('created_by_username', ''))}</td></tr><tr><th>审计日志</th><td><a class="ghost-link" href="/backoffice/audit-logs/{_h(drill.get('audit_log_id'))}">查看审计日志</a></td></tr></tbody></table><div class="actions" style="margin-top:16px"><a class="ghost-link" href="/backoffice/backups">返回备份记录</a></div></div></section>
{_acceptance_backup_notice()}'''
    return _page('恢复演练详情', body)


def register_backup_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _ops_context(user):
        if repository:
            return repository.list_users(user['tenant_id']), repository.list_audit_logs(user['tenant_id'], user['project_id'])
        users = [u for u in service.users.values() if u['tenant_id'] == user['tenant_id']]
        return users, service.list_audit_logs(user, user['project_id'])

    def _records(user):
        service._require(user, 'read')
        if repository:
            records = repository.list_backup_records(user['tenant_id'], user['project_id'])
        else:
            records = [r for r in service.backup_records.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == user['project_id']]
        users, audits = _ops_context(user)
        return backup_items(records, users, audits)

    def _drills(user):
        service._require(user, 'read')
        if repository:
            drills = repository.list_restore_drills(user['tenant_id'], user['project_id'])
        else:
            drills = [r for r in service.restore_drills.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == user['project_id']]
        users, audits = _ops_context(user)
        return restore_drill_items(drills, users, audits)

    @app.get('/backoffice/backups', response_class=HTMLResponse)
    def backup_page(keyword: str = '', status: str = '', scope: str = '', page: int = 1, page_size: int = 20, user=Depends(current_user)):
        try:
            params = {'keyword': keyword, 'status': status, 'scope': scope, 'page': page, 'page_size': page_size}
            return HTMLResponse(_render(user, _records(user), _drills(user), params))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/backups/{backup_id}', response_class=HTMLResponse)
    def backup_detail_page(backup_id: str, user=Depends(current_user)):
        try:
            record = next((r for r in _records(user) if r.get('backup_id') == backup_id), None)
            if not record:
                raise HTTPException(status_code=404, detail='backup not found')
            return HTMLResponse(_render_backup_detail(user, record, _drills(user)))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/backups/restore-drills/{drill_id}', response_class=HTMLResponse)
    def restore_drill_detail_page(drill_id: str, user=Depends(current_user)):
        try:
            drill = next((r for r in _drills(user) if str(r.get('id')) == str(drill_id)), None)
            if not drill:
                raise HTTPException(status_code=404, detail='restore drill not found')
            return HTMLResponse(_render_drill_detail(user, drill))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/backups/create')
    def create_backup_page(user=Depends(current_user)):
        try:
            service._require(user, 'backup')
            if repository:
                repository.create_backup_record(user['tenant_id'], user['project_id'], user['id'])
            else:
                service.create_backup_marker(user, user['project_id'])
            return RedirectResponse('/backoffice/backups?message=备份已创建', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/backups/restore-drills')
    def restore_drill_page(backup_id: str = Form(...), scope: str = Form('database'), user=Depends(current_user)):
        try:
            service._require(user, 'backup')
            if backup_id not in {r.get('backup_id') for r in _records(user)}:
                raise PermissionDenied('backup does not belong to tenant')
            if repository:
                repository.create_restore_drill(user['tenant_id'], user['project_id'], user['id'], backup_id, scope)
            else:
                service.record_restore_drill(user, user['project_id'], backup_id, scope)
            return RedirectResponse('/backoffice/backups?message=恢复演练已记录', status_code=303)
        except (PermissionDenied, TenantScopeError, ValueError):
            raise HTTPException(status_code=403, detail='forbidden')
