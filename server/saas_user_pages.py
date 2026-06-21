#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML user management pages for SaaS backoffice."""

import html
import urllib.parse

from server.passwords import verify_password
from server.saas_password_policy import password_length_error, password_meets_policy, password_reset_error
from server.saas_repository_errors import TenantScopeError
from server.saas_service import PermissionDenied


def _h(value):
    return html.escape(str(value or ''), quote=True)


def _role_name(code):
    return {
        'platform_admin': '平台管理员',
        'system_admin': '租户管理员',
        'finance': '财务',
        'cashier': '收费员',
        'frontdesk': '客服业务编辑',
        'executive': '管理层只读',
    }.get(code, code)


def _page(title, body):
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_h(title)} · 物业收费管理系统 SaaS</title>
<style>
:root{{--ink:#172033;--muted:#667085;--line:#d9e2ec;--panel:#ffffff;--bg:#eef3f8;--brand:#1355d8;--danger:#b42318;--ok:#087443;}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#eef3f8,#f9fbfd);color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
.shell{{max-width:1280px;margin:0 auto;padding:24px 20px 44px}}.hero{{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:22px}}
.business-layout{{display:grid;grid-template-columns:230px 1fr;gap:20px;align-items:start}}.business-nav{{position:sticky;top:20px;background:#0f172a;color:#dbeafe;border-radius:18px;padding:18px;box-shadow:0 20px 52px rgba(15,23,42,.18)}}.business-nav .brand{{font-size:18px;font-weight:900;color:#fff;margin-bottom:18px}}.nav-group{{border-top:1px solid rgba(255,255,255,.12);padding-top:12px;margin-top:12px;display:grid;gap:6px}}.nav-group b{{font-size:12px;color:#93c5fd}}.nav-group a{{color:#eef6ff;text-decoration:none;padding:7px 9px;border-radius:10px}}.nav-group a:hover{{background:rgba(255,255,255,.12)}}.business-main{{min-width:0}}.business-top{{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:16px}}.business-top h1{{font-size:32px;margin:0 0 6px}}.business-top p{{margin:0;color:var(--muted)}}.tenant-chip{{background:#e0f2fe;color:#075985;border:1px solid #bae6fd;border-radius:999px;padding:8px 14px;font-weight:900;white-space:nowrap}}.account-bar{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px 14px;display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:16px}}.account-bar form{{display:flex;gap:8px;align-items:end}}.account-bar label{{font-size:12px}}.account-bar input{{width:120px;margin:0}}.metric-grid{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:18px}}.metric{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px}}.metric div{{font-size:12px;color:var(--muted);font-weight:800}}.metric strong{{display:block;font-size:24px;margin-top:6px}}.work-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.work-card{{display:grid;gap:6px;text-decoration:none;color:var(--ink);border:1px solid var(--line);border-radius:14px;padding:14px;background:#fff}}.work-card strong{{font-size:16px}}.work-card span{{color:var(--muted);font-size:12px}}.primary-work-card{{border-color:#bfdbfe;background:#eff6ff}}
h1{{font-size:30px;margin:0 0 8px;letter-spacing:-.02em}}.sub{{color:var(--muted);max-width:760px}}.badge{{display:inline-flex;align-items:center;border:1px solid #b8c7dc;border-radius:999px;padding:6px 12px;background:#fff;color:#344054;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 340px;gap:18px}}.card{{background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:18px;box-shadow:0 18px 48px rgba(21,42,74,.08)}}.card-h{{padding:18px 20px;border-bottom:1px solid var(--line);font-weight:800}}.card-b{{padding:20px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:12px 10px;border-bottom:1px solid #edf1f5;text-align:left;vertical-align:middle}}th{{font-size:12px;color:#667085;text-transform:uppercase;letter-spacing:.04em}}tr:last-child td{{border-bottom:0}}
.status{{border-radius:999px;padding:4px 9px;font-weight:700;font-size:12px}}.on{{background:#ecfdf3;color:var(--ok)}}.off{{background:#f2f4f7;color:#667085}}.tenant-scope{{background:#eff6ff;color:#1849a9;border:1px solid #b2ccff}}
.actions{{display:flex;gap:8px;flex-wrap:wrap}}button{{border:0;border-radius:10px;padding:8px 11px;font-weight:800;cursor:pointer}}.primary{{background:var(--brand);color:white}}.ghost{{background:#eef4ff;color:#1849a9}}.danger{{background:#fff1f3;color:var(--danger);border:1px solid #fecdd6}}
input,select{{width:100%;border:1px solid var(--line);border-radius:12px;padding:10px 11px;background:#fff;margin:6px 0 12px}}label{{font-weight:800;color:#344054}}.hint{{font-size:12px;color:#667085;margin-top:8px}}.inline{{display:flex;gap:8px;align-items:center}}.inline input{{margin:0;min-width:160px}}.filters{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;align-items:end;margin-bottom:12px}}.pager{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:12px 0;font-size:12px;color:var(--muted)}}.ghost-link{{display:inline-flex;align-items:center;padding:6px 10px;border:1px solid var(--line);border-radius:999px;color:#1849a9;text-decoration:none;background:#fff}}.ghost-link.disabled{{opacity:.45;pointer-events:none}}
@media(max-width:900px){{.grid,.business-layout,.metric-grid,.work-grid{{grid-template-columns:1fr}}.hero,.business-top,.account-bar{{display:block}}.business-nav{{position:static;margin-bottom:16px}}}}
</style></head><body><main class="shell">{body}</main></body></html>'''


def _render_users(user, items, message='', filters=None, total=0, page=1, page_size=10):
    filters = filters or {}
    scope_label = '平台全局视图' if user.get('role_code') == 'platform_admin' else '本租户视图'
    current_user_id = user.get('id')
    rows = ''.join(_render_user_row(row, current_user_id) for row in items) or '<tr><td colspan="7">暂无账号</td></tr>'
    notice = f'<div class="badge">{_h(message)}</div>' if message else ''
    tenant_filter = _render_tenant_filter(user, filters)
    side_panel = _render_side_panel(user)
    role_options = ''.join(
        f'<option value="{_h(code)}"{" selected" if filters.get("role_code") == code else ""}>{_h(name)}</option>'
        for code, name in [('', '全部角色'), ('platform_admin', '平台管理员'), ('system_admin', '租户管理员'), ('finance', '财务'), ('cashier', '收费员'), ('frontdesk', '客服业务编辑'), ('executive', '管理层只读')]
    )
    active_options = ''.join(
        f'<option value="{val}"{" selected" if filters.get("is_active") == val else ""}>{label}</option>'
        for val, label in [('', '全部状态'), ('1', '仅启用'), ('0', '仅停用')]
    )
    page_size_options = ''.join(
        f'<option value="{n}"{" selected" if int(filters.get("page_size", 10)) == n else ""}>{n}</option>'
        for n in [5, 10, 20, 50]
    )
    prev_link = f'<a class="ghost-link" href="/backoffice/users?{_build_query(filters, page - 1, page_size)}">上一页</a>' if page > 1 else '<span class="ghost-link disabled">上一页</span>'
    next_link = f'<a class="ghost-link" href="/backoffice/users?{_build_query(filters, page + 1, page_size)}">下一页</a>' if page * page_size < total else '<span class="ghost-link disabled">下一页</span>'
    pager = f'<div class="pager"><span>共 {total} 个账号 · 第 {page} 页</span><span>{prev_link} {next_link}</span></div>'
    body = f'''
<section class="hero"><div><h1>账号管理</h1><div class="sub">正式商业后台账号控制台。租户管理员只能管理本公司员工；平台管理员可跨租户处理账号，但操作会写入目标租户审计。</div></div><div class="badge tenant-scope">{_h(scope_label)}</div></section>
{notice}
<section class="grid"><div class="card"><div class="card-h">员工账号列表</div><div class="card-b"><form method="get" action="/backoffice/users" class="filters"><input type="hidden" name="page" value="1"><div><label>关键字</label><input name="q" value="{_h(filters.get('q', ''))}" placeholder="账号关键词"></div>{tenant_filter}<div><label>角色</label><select name="role_code">{role_options}</select></div><div><label>状态</label><select name="is_active">{active_options}</select></div><div><label>每页数量</label><select name="page_size">{page_size_options}</select></div><div><button class="primary">筛选</button></div></form>{pager}<table><thead><tr><th>ID</th><th>租户</th><th>账号</th><th>角色</th><th>状态</th><th>重置密码</th><th>账号状态</th></tr></thead><tbody>{rows}</tbody></table>{pager}</div></div>
{side_panel}</section>'''
    return _page('账号管理', body)


def _render_side_panel(user):
    if user.get('role_code') == 'platform_admin':
        return '''<aside class="card"><div class="card-h">客户开通</div><div class="card-b"><p class="sub">平台账号不承载客户业务数据，不能把客户上传数据放入平台租户。</p><p class="sub">客户员工必须归属具体客户公司；平台管理员不在这里直接新建客户员工，避免把客户员工建到平台租户。</p><p class="sub">跨租户账号操作写入目标租户审计；请通过客户开通创建客户公司、默认项目和首个租户管理员，再由租户管理员维护本公司员工。</p><a class="ghost-link" href="/backoffice/tenant-onboarding">进入客户开通</a></div></aside>'''
    return '''<aside class="card"><div class="card-h">新建员工账号</div><div class="card-b"><form method="post" action="/backoffice/users/create"><label>登录账号</label><input name="username" required placeholder="例如 cashier_01"><label>角色</label><select name="role_code"><option value="cashier">收费员</option><option value="finance">财务</option><option value="frontdesk">客服业务编辑</option><option value="executive">管理层只读</option><option value="system_admin">租户管理员</option></select><button class="primary">创建账号</button><div class="hint">创建后请立即通过左侧“重置密码”设置临时密码，并要求员工首次登录后修改。</div></form></div></aside>'''


def _render_tenant_filter(user, filters):
    if user.get('role_code') != 'platform_admin':
        return ''
    value = _h(filters.get('tenant_name', ''))
    return f'<div><label>客户公司筛选</label><input name="tenant_name" value="{value}" placeholder="输入客户公司名"></div>'


def _tenant_display(row):
    name = row.get('tenant_name')
    tenant_id = row.get('tenant_id')
    if name:
        return f'{name}（ID {tenant_id}）'
    return tenant_id

def _render_user_row(row, current_user_id=None):
    active = int(row.get('is_active', 1) or 0) == 1
    status = '<span class="status on">启用</span>' if active else '<span class="status off">停用</span>'
    next_active = '0' if active else '1'
    action_label = '停用账号' if active else '启用账号'
    btn_class = 'danger' if active else 'ghost'
    if current_user_id is not None and int(row.get('id')) == int(current_user_id):
        reset_cell = '<span class="hint">当前账号：请使用个人改密入口</span>'
        active_cell = '<span class="hint">当前账号不可停用</span>'
    else:
        row_id = _h(row.get('id'))
        reset_cell = f'<form method="post" action="/backoffice/users/{row_id}/reset-password" class="inline"><input type="password" name="new_password" required minlength="8" placeholder="临时密码"><button class="primary">重置密码</button></form>'
        active_cell = f'<form method="post" action="/backoffice/users/{row_id}/active"><input type="hidden" name="is_active" value="{next_active}"><button class="{btn_class}">{action_label}</button></form>'
    return f'''<tr><td>{_h(row.get('id'))}</td><td>{_h(_tenant_display(row))}</td><td><strong>{_h(row.get('username'))}</strong></td><td>{_h(_role_name(row.get('role_code')))}</td><td>{status}</td>
<td>{reset_cell}</td>
<td>{active_cell}</td></tr>'''


def _build_query(filters, page=None, page_size=None):
    params = {}
    for key in ('q', 'role_code', 'is_active', 'tenant_name'):
        value = (filters or {}).get(key, '')
        if value:
            params[key] = str(value)
    if page is not None:
        params['page'] = str(page)
    if page_size is not None:
        params['page_size'] = str(page_size)
    return urllib.parse.urlencode(params)


def _parse_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _normalize_filters(q, role_code, is_active, page, page_size, tenant_name=''):
    page = max(_parse_int(page, 1), 1)
    page_size = min(max(_parse_int(page_size, 10), 1), 50)
    q = (q or '').strip()
    role_code = (role_code or '').strip()
    is_active = (is_active or '').strip()
    tenant_name = (tenant_name or '').strip()
    if is_active not in {'', '1', '0'}:
        is_active = ''
    return q, role_code, is_active, page, page_size, tenant_name


def _filter_users(items, q='', role_code='', is_active='', tenant_name=''):
    rows = []
    for row in items:
        if q and q.lower() not in str(row.get('username', '')).lower():
            continue
        if role_code and row.get('role_code') != role_code:
            continue
        if tenant_name and tenant_name.lower() not in str(row.get('tenant_name', '')).lower():
            continue
        if is_active in {'0', '1'} and int(row.get('is_active', 1) or 0) != int(is_active):
            continue
        rows.append(row)
    return rows


def _paginate(items, page, page_size):
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


def register_user_pages(app, service, repository, current_user, sessions):
    from fastapi import Depends, Form, HTTPException
    from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

    def _items_for(user):
        service._require(user, 'manage_users')
        return repository.list_users_for_actor(user) if repository else service.list_staff_users(user, user['project_id'])

    @app.get('/backoffice/users', response_class=HTMLResponse)
    def user_page(user=Depends(current_user), q: str = '', role_code: str = '', is_active: str = '', tenant_name: str = '', page: int = 1, page_size: int = 10, message: str = ''):
        try:
            q, role_code, is_active, page, page_size, tenant_name = _normalize_filters(q, role_code, is_active, page, page_size, tenant_name)
            all_items = _filter_users(_items_for(user), q=q, role_code=role_code, is_active=is_active, tenant_name=tenant_name)
            visible, total = _paginate(all_items, page, page_size)
            filters = {'q': q, 'role_code': role_code, 'is_active': is_active, 'page_size': page_size, 'tenant_name': tenant_name}
            return HTMLResponse(_render_users(user, visible, message, filters=filters, total=total, page=page, page_size=page_size))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/users/create')
    def create_user_page(username: str = Form(...), role_code: str = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'manage_users')
            if user.get('role_code') == 'platform_admin':
                raise PermissionDenied('use tenant onboarding for customer staff')
            if repository:
                repository.create_staff_user(user['tenant_id'], user['project_id'], username, role_code)
            else:
                service.create_staff_user(user, user['project_id'], username, role_code)
            return RedirectResponse('/backoffice/users?message=账号已创建', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/users/{user_id}/active')
    def active_page(user_id: int, is_active: int = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'manage_users')
            enabled = bool(int(is_active))
            if int(user_id) == int(user.get('id')) and not enabled:
                raise PermissionDenied('cannot disable own account')
            item = repository.set_user_active_for_actor(user, user_id, enabled) if repository else service.set_user_active(user, user['project_id'], user_id, enabled)
            if not enabled:
                for sid, session_user in list(sessions.items()):
                    if session_user.get('id') == user_id:
                        sessions.pop(sid, None)
            return RedirectResponse(f"/backoffice/users?message=账号已{'启用' if item['is_active'] else '停用'}", status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.post('/backoffice/users/{user_id}/reset-password')
    def reset_page(user_id: int, new_password: str = Form(...), user=Depends(current_user)):
        try:
            service._require(user, 'manage_users')
            if int(user_id) == int(user.get('id')):
                raise PermissionDenied('use change-password for own account')
            if not password_meets_policy(new_password):
                return PlainTextResponse(password_length_error('临时密码'), status_code=400)
            target = repository.get_user(user_id) if repository else service.users.get(user_id, {})
            reset_error = password_reset_error(bool(target and verify_password(new_password, target.get('password_hash'))))
            if reset_error:
                return PlainTextResponse(reset_error, status_code=400)
            if repository:
                repository.reset_user_password_for_actor(user, user_id, new_password)
            else:
                service.reset_user_password(user, user_id, new_password)
            return RedirectResponse('/backoffice/users?message=密码已重置', status_code=303)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
