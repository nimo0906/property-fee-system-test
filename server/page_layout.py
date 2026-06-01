#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Page layout and navigation helpers."""

import urllib.parse
from server.db import h

def _is_secondary_path(path):
    if path in ('/', '/login', '/logout', '/register'):
        return False
    if path.startswith('/api/') or path.startswith('/static/'):
        return False
    primary_paths = {
        '/rooms', '/owners', '/fee_types', '/batch_ops', '/meter_readings',
        '/billing', '/commercial_billing', '/shared_expenses', '/bills',
        '/payments', '/collections', '/reminders',
        '/invoices', '/reports', '/closing', '/audit_logs', '/backups',
        '/system_health', '/system_update', '/users', '/import',
    }
    return path not in primary_paths

def render_page(handler, title, content, active='', top_actions=''):
    flash = handler._get_flash()
    if _is_secondary_path(urllib.parse.urlparse(handler.path).path):
        back_btn = '<button type="button" class="btn btn-outline-secondary btn-sm page-back-btn" data-back-button="1" onclick="if(history.length>1){history.back()}else{location.href=\'/\'}"><i class="bi bi-arrow-left"></i> 返回</button>'
        top_actions = (back_btn + top_actions) if top_actions else back_btn
    html = handler._load_template('base.html')
    cur_user = handler._get_current_user()
    role = cur_user.get("role") if cur_user else ""
    nav_groups = [
        ('工作台', [('index', '/', 'bi-speedometer2', '收费工作台')]),
        ('基础资料', [
            ('owners', '/owners', 'bi-people', '业主管理'),
            ('rooms', '/rooms', 'bi-door-open', '房间管理'),
            ('fee_types', '/fee_types', 'bi-tags', '收费项目'),
            ('batch_ops', '/batch_ops', 'bi-pencil-square', '批量更新'),
            ('meter', '/meter_readings', 'bi-clipboard-data', '抄表管理'),
            ('import', '/import', 'bi-upload', '数据导入'),
        ]),
        ('收费业务', [
            ('billing', '/billing', 'bi-cash-coin', '物业收费'),
            ('commercial_billing', '/commercial_billing', 'bi-building', '商业收费'),
            ('shared_expenses', '/shared_expenses', 'bi-diagram-3', '公摊分摊'),
            ('bills', '/bills', 'bi-receipt', '账单管理'),
            ('payments', '/payments', 'bi-credit-card', '缴费记录'),
            ('collections', '/collections', 'bi-telephone-outbound', '客服催费对象'),
            ('reminders', '/reminders', 'bi-bell', '催缴管理'),
        ]),
        ('财务核对', [
            ('invoices', '/invoices', 'bi-receipt-cutoff', '发票管理'),
            ('reports', '/reports', 'bi-graph-up', '对账报表'),
            ('closing', '/closing', 'bi-lock', '期末结账'),
        ]),
        ('系统维护', [
            ('audit_logs', '/audit_logs', 'bi-journal-check', '操作日志'),
            ('backups', '/backups', 'bi-cloud', '数据备份'),
        ]),
    ]
    if role == "readonly":
        allowed = {'index', 'owners', 'rooms', 'bills', 'collections', 'reminders', 'reports'}
    else:
        allowed = {'index', 'owners', 'rooms', 'fee_types', 'batch_ops', 'meter', 'billing',
                   'commercial_billing', 'bills', 'payments', 'invoices',
                   'reports', 'closing', 'backups', 'import', 'reminders', 'audit_logs', 'shared_expenses'}
    user_html = ''
    if cur_user:
        role_label = {"admin": "管理员", "operator": "财务收费", "readonly": "客服只读"}.get(cur_user["role"], cur_user["role"])
        user_html = f'''<div class="sidebar-user">
            <div class="d-flex align-items-center justify-content-between gap-2">
                <div><div class="name"><i class="bi bi-person-circle"></i> {h(cur_user["display_name"] or cur_user["username"])}</div>
                <div class="role">{role_label}</div></div>
                <a href="/logout" class="btn btn-sm btn-outline-light" title="退出"><i class="bi bi-box-arrow-right"></i></a>
            </div>
        </div>'''
    if cur_user and cur_user["role"] == "admin":
        nav_groups[-1][1].append(("users", "/users", "bi-people-fill", "操作员管理"))
        allowed.add('users')
        allowed.add('system_health')
        allowed.add('system_update')
    nav_parts = []
    for group_name, items in nav_groups:
        visible = [item for item in items if item[0] in allowed]
        if not visible:
            continue
        links = ''.join(
            f'<a class="nav-link{" active" if active == a[0] else ""}" href="{a[1]}"><i class="bi {a[2]}"></i><span>{a[3]}</span></a>'
            for a in visible
        )
        if group_name == '系统维护' and role == 'admin':
            tool_active = 'system_health' if active == 'system_health' else ('system_update' if active == 'system_update' else '')
            links += (
                '<div class="maintenance-tools">'
                f'<a class="system-tool-btn {"active" if tool_active == "system_health" else ""}" href="/system_health" title="系统健康"><i class="bi bi-shield-check"></i><span>健康</span></a>'
                f'<a class="system-tool-btn {"active" if tool_active == "system_update" else ""}" href="/system_update" title="系统更新"><i class="bi bi-arrow-repeat"></i><span>更新</span></a>'
                '</div>'
            )
        nav_parts.append(f'<div class="nav-section"><div class="nav-section-title">{group_name}</div>{links}</div>')
    nav_html = ''.join(nav_parts)
    icons = {'index': 'bi-speedometer2', 'rooms': 'bi-door-open', 'owners': 'bi-people',
             'fee_types': 'bi-tags', 'batch_ops': 'bi-pencil-square', 'meter': 'bi-clipboard-data', 'repairs': 'bi-tools',
             'parking': 'bi-car-front', 'invoices': 'bi-receipt-cutoff', 'deposits': 'bi-cash-stack',
             'reminders': 'bi-bell', 'billing': 'bi-cash-coin', 'commercial_billing': 'bi-building',
             'shared_expenses': 'bi-diagram-3',
             'bills': 'bi-receipt', 'payments': 'bi-credit-card', 'closing': 'bi-lock',
             'backups': 'bi-cloud', 'import': 'bi-upload', 'reports': 'bi-graph-up', 'system_health': 'bi-shield-check',
             'system_update': 'bi-arrow-repeat',
             'collections': 'bi-telephone-outbound', 'audit_logs': 'bi-journal-check'}
    icon = icons.get(active, 'bi-speedometer2')
    html = html.replace('{TITLE}', h(title))
    html = html.replace('{CONTENT}', content)
    html = html.replace('{NAV}', nav_html)
    html = html.replace('{USER_HTML}', user_html)
    html = html.replace('{ICON}', icon)
    html = html.replace('{TOP_ACTIONS}', top_actions)
    html = html.replace("{FLASH}", flash)
    return html

