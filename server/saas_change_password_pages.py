#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Personal password change pages for SaaS backoffice."""

from server.passwords import verify_password
from server.saas_password_policy import password_change_error, password_length_error, password_meets_policy
from server.saas_user_pages import _h, _page, _role_name


def _render_change_password(user, message='', is_error=False):
    notice_class = 'danger' if is_error else 'badge'
    notice = f'<div class="{notice_class}" style="margin-bottom:14px">{_h(message)}</div>' if message else ''
    body = f'''
<section class="hero"><div><h1>修改个人密码</h1><div class="sub">当前账号只能在这里修改自己的密码；管理员重置密码用于其他员工账号，并会写入审计。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="grid"><div class="card"><div class="card-h">个人改密</div><div class="card-b">{notice}<p class="sub"><strong>当前账号：</strong>{_h(user.get('username'))} · {_h(_role_name(user.get('role_code')))}</p><form method="post" action="/backoffice/change-password"><label>原密码</label><input type="password" name="old_password" required><label>新密码</label><input type="password" name="new_password" required minlength="8"><button class="primary">修改密码</button></form><div class="hint">新密码不会显示在页面、日志或审计明细中。</div></div></div>
<aside class="card"><div class="card-h">账号安全边界</div><div class="card-b"><p class="sub">如果你是首次登录或密码已被管理员重置，必须先完成个人改密，才能进入其他业务模块。</p><p class="sub">请不要把自己的账号密码交给其他公司或其他员工使用。</p></div></aside></section>'''
    return _page('修改个人密码', body)


def register_change_password_pages(app, service, repository, session_user):
    from fastapi import Depends, Form
    from fastapi.responses import HTMLResponse, RedirectResponse

    @app.get('/backoffice/change-password', response_class=HTMLResponse)
    def change_password_page(user=Depends(session_user)):
        return HTMLResponse(_render_change_password(user))

    @app.post('/backoffice/change-password', response_class=HTMLResponse)
    def change_password_submit(old_password: str = Form(...), new_password: str = Form(...), user=Depends(session_user)):
        if not password_meets_policy(new_password):
            return HTMLResponse(_render_change_password(user, password_length_error('新密码'), is_error=True), status_code=400)
        same_password_error = password_change_error(old_password, new_password)
        if same_password_error:
            return HTMLResponse(_render_change_password(user, same_password_error, is_error=True), status_code=400)
        if repository:
            stored = repository.get_user(user['id'])
            if not stored or not verify_password(old_password, stored.get('password_hash')):
                return HTMLResponse(_render_change_password(user, '原密码不正确', is_error=True), status_code=401)
            repository.change_own_password(user, new_password)
        else:
            stored = service.users.get(user['id'], {})
            if stored.get('password_hash') and not verify_password(old_password, stored.get('password_hash')):
                return HTMLResponse(_render_change_password(user, '原密码不正确', is_error=True), status_code=401)
            service.reset_user_password(user, user['id'], new_password)
        user['must_change_password'] = False
        return RedirectResponse('/backoffice?message=密码已修改', status_code=303)
