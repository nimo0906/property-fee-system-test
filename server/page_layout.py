#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Page layout and navigation helpers."""

import urllib.parse
from server.db import h
from server.csrf import csrf_token_for_handler

def _is_secondary_path(path):
    if path in ('/', '/login', '/logout', '/register'):
        return False
    if path.startswith('/api/') or path.startswith('/static/'):
        return False
    primary_paths = {
        '/rooms', '/owners', '/fee_types', '/batch_ops', '/meter_readings',
        '/billing', '/commercial_spaces', '/commercial_billing', '/merchant_contracts', '/auto_billing', '/shared_expenses', '/bills',
        '/payments', '/collections', '/reminders', '/alert_center',
        '/invoices', '/reports', '/closing', '/audit_logs', '/backups',
        '/system_health', '/system_update', '/trial_data_reset', '/users', '/delivery_center', '/import',
    }
    return path not in primary_paths


def _secondary_back_url(path):
    first_segment = '/' + path.strip('/').split('/', 1)[0]
    mapping = {
        '/fee_types': '/fee_types',
        '/rooms': '/rooms',
        '/owners': '/owners',
        '/bills': '/bills',
        '/payments': '/payments',
        '/invoices': '/invoices',
        '/reports': '/reports',
        '/meter_readings': '/meter_readings',
        '/merchant_contracts': '/merchant_contracts',
        '/import': '/import',
        '/backups': '/backups',
        '/users': '/users',
    }
    return mapping.get(first_segment, '/')


def render_page(handler, title, content, active='', top_actions=''):
    flash = handler._get_flash()
    current_path = urllib.parse.urlparse(handler.path).path
    if _is_secondary_path(current_path):
        back_url = _secondary_back_url(current_path)
        back_btn = f'<a class="btn btn-outline-secondary btn-sm page-back-btn" data-back-button="1" href="{h(back_url)}"><i class="bi bi-arrow-left"></i> 返回</a>'
        top_actions = (back_btn + top_actions) if top_actions else back_btn
    html = handler._load_template('base.html')
    csrf_token = csrf_token_for_handler(handler)
    cur_user = handler._get_current_user()
    raw_role = cur_user.get("role") if cur_user else ""
    role = {"system_admin": "admin", "finance": "operator", "cashier": "operator", "executive": "readonly"}.get(raw_role, raw_role)
    nav_groups = [
        ('工作台', [
            ('index', '/', 'bi-speedometer2', '收费工作台'),
            ('billing', '/billing', 'bi-cash-coin', '物业收费'),
            ('commercial_billing', '/commercial_billing', 'bi-building', '商业收费'),
            ('alert_center', '/alert_center', 'bi-exclamation-triangle', '智能预警'),
            ('reminders', '/reminders', 'bi-bell', '催缴管理'),
            ('import', '/import', 'bi-upload', '数据导入'),
            ('merchant_contracts', '/merchant_contracts', 'bi-file-earmark-text', '合同档案'),
        ]),
        ('公共功能', [
            ('owners', '/owners', 'bi-people', '业主管理'),
            ('rooms', '/rooms', 'bi-door-open', '房间管理'),
            ('fee_types', '/fee_types', 'bi-tags', '收费项目'),
            ('meter', '/meter_readings', 'bi-clipboard-data', '抄表管理'),
            ('backups', '/backups', 'bi-cloud-check', '备份记录'),
            ('batch_ops', '/batch_ops', 'bi-pencil-square', '批量更新'),
            ('auto_billing', '/auto_billing', 'bi-calendar-check', '自动出账'),
            ('shared_expenses', '/shared_expenses', 'bi-diagram-3', '公摊分摊'),
        ]),
        ('财务核对', [
            ('bills', '/bills', 'bi-receipt', '账单管理'),
            ('payments', '/payments', 'bi-credit-card', '缴费记录'),
            ('collections', '/collections', 'bi-telephone-outbound', '客服催费对象'),
            ('invoices', '/invoices', 'bi-receipt-cutoff', '发票管理'),
            ('reports', '/reports', 'bi-graph-up', '对账报表'),
            ('closing', '/closing', 'bi-lock', '期末结账'),
        ]),
        ('系统维护', [
            ('audit_logs', '/audit_logs', 'bi-journal-check', '操作日志'),
        ]),
    ]
    if role == "readonly":
        allowed = {'index', 'owners', 'rooms', 'bills', 'collections', 'reminders', 'reports'}
    elif role == "frontdesk":
        allowed = {'index', 'owners', 'rooms', 'meter', 'merchant_contracts', 'import', 'bills', 'collections', 'reminders', 'reports'}
    else:
        allowed = {'index', 'owners', 'rooms', 'fee_types', 'batch_ops', 'meter', 'billing',
                   'commercial_spaces', 'commercial_billing', 'merchant_contracts', 'auto_billing', 'bills', 'payments', 'invoices',
                   'reports', 'closing', 'import', 'reminders', 'alert_center', 'shared_expenses'}
    user_html = ''
    if cur_user:
        role_label = {"admin": "管理员", "system_admin": "系统管理员", "manager": "业务管理员", "finance": "财务", "cashier": "收费员", "frontdesk": "客服业务编辑", "executive": "管理层只读", "operator": "旧版财务收费", "readonly": "旧版只读"}.get(cur_user["role"], cur_user["role"])
        user_html = f'''<div class="sidebar-user">
            <div class="d-flex align-items-center justify-content-between gap-2">
                <div><div class="name"><i class="bi bi-person-circle"></i> {h(cur_user["display_name"] or cur_user["username"])}</div>
                <div class="role">{role_label}</div></div>
                <a href="/logout" class="btn btn-sm btn-outline-light" title="退出"><i class="bi bi-box-arrow-right"></i></a>
            </div>
        </div>'''
    if cur_user and cur_user["role"] in ("admin", "manager"):
        nav_groups[-1][1].append(("users", "/users", "bi-people-fill", "操作员管理"))
        allowed.add('users')
    if cur_user and cur_user["role"] == "admin":
        allowed.add('backups')
        allowed.add('system_health')
        allowed.add('system_update')
        allowed.add('trial_data_reset')
        allowed.add('cloud_schema')
        nav_groups[-1][1].append(("cloud_schema", "/cloud_schema", "bi-cloud-check", "云端技术备查"))
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
            tool_active = 'system_health' if active == 'system_health' else ('system_update' if active == 'system_update' else ('trial_data_reset' if active == 'trial_data_reset' else ''))
            links += (
                '<div class="maintenance-tools">'
                f'<a class="system-tool-btn {"active" if tool_active == "system_health" else ""}" href="/system_health" title="系统健康"><i class="bi bi-shield-check"></i><span>健康</span></a>'
                f'<a class="system-tool-btn {"active" if tool_active == "system_update" else ""}" href="/system_update" title="系统更新"><i class="bi bi-arrow-repeat"></i><span>更新</span></a>'
                f'<a class="system-tool-btn {"active" if tool_active == "trial_data_reset" else ""}" href="/trial_data_reset" title="清空试用业务数据"><i class="bi bi-trash3"></i><span>清空</span></a>'
                '</div>'
            )
        nav_parts.append(f'<div class="nav-section"><div class="nav-section-title">{group_name}</div>{links}</div>')
    nav_html = ''.join(nav_parts)
    icons = {'index': 'bi-speedometer2', 'rooms': 'bi-door-open', 'owners': 'bi-people',
             'fee_types': 'bi-tags', 'batch_ops': 'bi-pencil-square', 'meter': 'bi-clipboard-data', 'repairs': 'bi-tools',
             'parking': 'bi-car-front', 'invoices': 'bi-receipt-cutoff', 'deposits': 'bi-cash-stack',
             'reminders': 'bi-bell', 'billing': 'bi-cash-coin', 'commercial_spaces': 'bi-shop',
             'commercial_billing': 'bi-building',
             'auto_billing': 'bi-calendar-check',
             'shared_expenses': 'bi-diagram-3',
             'bills': 'bi-receipt', 'payments': 'bi-credit-card', 'closing': 'bi-lock',
             'backups': 'bi-cloud-check', 'import': 'bi-upload', 'reports': 'bi-graph-up', 'system_health': 'bi-shield-check',
             'system_update': 'bi-arrow-repeat', 'trial_data_reset': 'bi-trash3',
             'collections': 'bi-telephone-outbound', 'alert_center': 'bi-exclamation-triangle', 'audit_logs': 'bi-journal-check',
             'delivery_center': 'bi-clipboard-check'}
    icons['merchant_contracts'] = 'bi-file-earmark-text'
    icons['cloud_schema'] = 'bi-cloud-check'
    icon = icons.get(active, 'bi-speedometer2')
    html = html.replace('{TITLE}', h(title))
    html = html.replace('{CONTENT}', content)
    html = html.replace('{PAGE_CLASS}', 'index-main-content' if active == 'index' else '')
    html = html.replace('{NAV}', nav_html)
    html = html.replace('{USER_HTML}', user_html)
    html = html.replace('{ICON}', icon)
    html = html.replace('{TOP_ACTIONS}', top_actions)
    html = html.replace('{CSRF_META}', f'<meta name="csrf-token" content="{h(csrf_token)}">' if csrf_token else '')
    html = html.replace("{FLASH}", flash)
    return html
