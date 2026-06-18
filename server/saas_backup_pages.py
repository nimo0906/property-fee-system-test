#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML backup and restore drill pages for SaaS backoffice."""

from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page


def _backup_rows(records):
    rows = []
    for item in records:
        rows.append(f'''<tr><td>{_h(item.get('backup_id'))}</td><td>{_h(item.get('status'))}</td><td>{_h(item.get('created_at', ''))}</td></tr>''')
    return ''.join(rows) or '<tr><td colspan="3">暂无备份记录</td></tr>'


def _forms(can_manage, records):
    if not can_manage:
        return '<div class="hint">当前角色只能查看备份，不能执行备份或恢复演练操作。</div>'
    options = ''.join(f'<option value="{_h(r.get("backup_id"))}">{_h(r.get("backup_id"))}</option>' for r in records)
    drill = '<div class="hint">请先创建备份，再提交恢复演练。</div>'
    if options:
        drill = f'''<form method="post" action="/backoffice/backups/restore-drills"><label>备份ID</label><select name="backup_id" required>{options}</select><label>演练范围</label><select name="scope"><option value="database">database</option><option value="tenant-files">tenant-files</option><option value="system-files">system-files</option></select><button class="primary">提交恢复演练</button></form>'''
    return f'''<form method="post" action="/backoffice/backups/create"><button class="primary">创建备份</button></form><hr>{drill}'''


def _render(user, records):
    can_manage = user.get('role_code') in {'system_admin', 'platform_admin'}
    body = f'''
<section class="hero"><div><h1>备份记录</h1><div class="sub">记录当前租户和项目的备份与恢复演练。页面不展示真实存储密钥或服务器路径。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="grid"><div class="card"><div class="card-h">备份记录</div><div class="card-b"><table><thead><tr><th>备份ID</th><th>状态</th><th>创建时间</th></tr></thead><tbody>{_backup_rows(records)}</tbody></table></div></div>
<aside class="card"><div class="card-h">恢复演练</div><div class="card-b">{_forms(can_manage, records)}</div></aside></section>'''
    return _page('备份记录', body)


def register_backup_pages(app, service, repository, current_user):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _records(user):
        service._require(user, 'read')
        if repository:
            return repository.list_backup_records(user['tenant_id'], user['project_id'])
        return [r for r in service.backup_records.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == user['project_id']]

    @app.get('/backoffice/backups', response_class=HTMLResponse)
    def backup_page(user=Depends(current_user)):
        try:
            return HTMLResponse(_render(user, _records(user)))
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
