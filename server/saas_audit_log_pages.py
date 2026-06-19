#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML audit log pages for SaaS backoffice."""

from urllib.parse import urlencode

from server.saas_audit_summary import render_audit_summary
from server.saas_audit_tools import detail_text as _detail_text, filter_audit_items, risk_level
from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page, _role_name


def _is_risk(item):
    return risk_level(item) == 'high'


def _filter_items(items, params):
    return filter_audit_items(items, params.get('action'), params.get('entity_type'), params.get('keyword'), params.get('risk'))

def _paginate(items, page, page_size):
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 20), 100), 1)
    start = (page - 1) * page_size
    return {'total': len(items), 'page': page, 'page_size': page_size, 'items': items[start:start + page_size]}


def _query(params, **changes):
    data = {k: v for k, v in params.items() if v not in ('', None)}
    data.update({k: v for k, v in changes.items() if v not in ('', None)})
    return urlencode(data)


def _rows(items):
    rows = []
    for item in items:
        detail = _detail_text(item.get('detail'))
        href = f"/backoffice/audit-logs/{_h(item.get('id'))}"
        risk = '<span class="badge danger">高风险</span>' if _is_risk(item) else ''
        rows.append(f'''<tr><td>{_h(item.get('id'))}</td><td>{_h(item.get('action'))} {risk}</td><td>{_h(item.get('entity_type'))}</td><td>{_h(item.get('entity_id'))}</td><td>{_h(item.get('user_id'))}</td><td><pre class="hint">{_h(detail)}</pre></td><td><a class="ghost-link" href="{href}">查看详情</a></td></tr>''')
    return ''.join(rows) or '<tr><td colspan="7">暂无审计日志</td></tr>'


def _filter_card(params):
    checked = ' checked' if params.get('risk') == 'high' else ''
    size = str(params.get('page_size') or 20)
    selected = lambda value: ' selected' if size == str(value) else ''
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">高级筛选</div><div class="card-b"><form method="get" action="/backoffice/audit-logs" class="filters"><div><label>动作</label><input name="action" value="{_h(params.get('action'))}" placeholder="payment.record"></div><div><label>对象类型</label><input name="entity_type" value="{_h(params.get('entity_type'))}" placeholder="payment / bill / user"></div><div><label>关键字</label><input name="keyword" value="{_h(params.get('keyword'))}" placeholder="收据号 / 幂等键 / 账号"></div><div><label>风险</label><select name="risk"><option value="">全部</option><option value="high"{' selected' if params.get('risk') == 'high' else ''}>高风险</option></select></div><div><label>每页</label><select name="page_size"><option value="10"{selected(10)}>10</option><option value="20"{selected(20)}>20</option><option value="50"{selected(50)}>50</option></select></div><div><button class="primary">筛选</button></div></form></div></section>'''


def _pager(result, params):
    page = result['page']
    size = result['page_size']
    total = result['total']
    prev_cls = 'ghost-link disabled' if page <= 1 else 'ghost-link'
    next_cls = 'ghost-link disabled' if page * size >= total else 'ghost-link'
    prev_href = '/backoffice/audit-logs?' + _query(params, page=max(page - 1, 1), page_size=size)
    next_href = '/backoffice/audit-logs?' + _query(params, page=page + 1, page_size=size)
    return f'''<div class="pager"><span>共 {_h(total)} 条 · 第 {_h(page)} 页 · 每页 {_h(size)} 条</span><span class="actions"><a class="{prev_cls}" href="{_h(prev_href)}">上一页</a><a class="{next_cls}" href="{_h(next_href)}">下一页</a></span></div>'''


def _render(user, all_items, result, params):
    readonly = '<span class="badge">只读</span>' if user.get('role_code') == 'executive' else ''
    body = f'''
<section class="hero"><div><h1>审计日志</h1><div class="sub">查看当前租户和项目内的账号、导入、出账、审核、收款等关键操作记录。审计日志只读展示，不提供页面删除。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><strong>当前角色：</strong>{_h(_role_name(user.get('role_code')))} {readonly}</div></section>
{render_audit_summary(all_items)}
{_filter_card(params)}
<section class="card"><div class="card-h">操作记录</div><div class="card-b">{_pager(result, params)}<table><thead><tr><th>ID</th><th>动作</th><th>对象类型</th><th>对象ID</th><th>用户ID</th><th>详情</th><th>入口</th></tr></thead><tbody>{_rows(result['items'])}</tbody></table>{_pager(result, params)}</div></section>'''
    return _page('审计日志', body)


def _render_detail(user, item):
    risk = '<span class="badge danger">高风险</span>' if _is_risk(item) else '<span class="badge">普通</span>'
    body = f'''
<section class="hero"><div><h1>审计详情</h1><div class="sub">只展示当前公司、当前项目内的审计记录，敏感字段已隐藏。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card"><div class="card-h">审计详情 {risk}</div><div class="card-b"><table><tbody>
<tr><th>ID</th><td>{_h(item.get('id'))}</td></tr>
<tr><th>动作</th><td>{_h(item.get('action'))}</td></tr>
<tr><th>对象类型</th><td>{_h(item.get('entity_type'))}</td></tr>
<tr><th>对象ID</th><td>{_h(item.get('entity_id'))}</td></tr>
<tr><th>用户ID</th><td>{_h(item.get('user_id'))}</td></tr>
<tr><th>详情</th><td><pre class="hint">{_h(_detail_text(item.get('detail')))}</pre></td></tr>
</tbody></table><div class="actions" style="margin-top:16px"><a class="ghost-link" href="/backoffice/audit-logs">返回审计日志</a></div></div></section>'''
    return _page('审计详情', body)


def register_audit_log_pages(app, service, repository, current_user):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    def _items(user):
        if repository:
            return repository.list_audit_logs(user['tenant_id'], user['project_id'])
        return service.list_audit_logs(user, user['project_id'])

    @app.get('/backoffice/audit-logs', response_class=HTMLResponse)
    def audit_log_page(action: str = '', entity_type: str = '', keyword: str = '', risk: str = '', page: int = 1, page_size: int = 20, user=Depends(current_user)):
        try:
            service._require(user, 'read')
            items = _items(user)
            params = {'action': action, 'entity_type': entity_type, 'keyword': keyword, 'risk': risk, 'page': page, 'page_size': page_size}
            result = _paginate(_filter_items(items, params), page, page_size)
            return HTMLResponse(_render(user, items, result, params))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')

    @app.get('/backoffice/audit-logs/{log_id}', response_class=HTMLResponse)
    def audit_log_detail(log_id: int, user=Depends(current_user)):
        try:
            service._require(user, 'read')
            item = next((row for row in _items(user) if int(row.get('id')) == int(log_id)), None)
            if not item:
                raise HTTPException(status_code=404, detail='audit log not found')
            return HTMLResponse(_render_detail(user, item))
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail='forbidden')
