#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML home pages for SaaS staff backoffice."""

from server.saas_user_pages import _h, _page, _role_name


def _module_card(title, desc, href=None, note=''):
    action = f'<a class="ghost-link" href="{_h(href)}">进入模块</a>' if href else f'<span class="hint">{_h(note)}</span>'
    return f'<div class="card"><div class="card-h">{_h(title)}</div><div class="card-b"><p class="sub">{_h(desc)}</p>{action}</div></div>'


def _backoffice_home(user):
    can_manage_users = user.get('role_code') in {'system_admin', 'platform_admin'}
    user_card = _module_card(
        '账号管理',
        '管理员维护员工账号、停用离职账号、重置临时密码，并保留审计记录。',
        '/backoffice/users' if can_manage_users else None,
        '账号管理仅管理员可用',
    )
    cards = ''.join([
        user_card,
        _module_card('收费对象', '维护楼栋/区域、单元/分区、房号/铺位号等收费对象。', '/backoffice/charge-targets'),
        _module_card('收费项目', '配置物业费、水费、停车费等收费项目和价格规则。', '/backoffice/fee-types'),
        _module_card('出账收款 / 出账审核', '生成账单、审核账单、按账期和状态查询应收。', '/backoffice/bills'),
        _module_card('收款登记', '登记收款、查看收据号和收款流水。', '/backoffice/payments'),
        _module_card('对账报表', '按账期查看应收、实收和欠费。', '/backoffice/reports'),
    ])
    body = f'''
<section class="hero"><div><h1>SaaS 员工后台</h1><div class="sub">正式商业云端后台入口。当前租户、项目和角色会决定可见模块，避免不同公司数据混在一起。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><strong>当前账号：</strong>{_h(user.get('username'))}<span class="hint"> · {_h(_role_name(user.get('role_code')))}</span></div></section>
<section class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr))">{cards}</section>'''
    return _page('SaaS 员工后台', body)


def register_backoffice_pages(app, current_user):
    from fastapi import Depends
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice', response_class=HTMLResponse)
    def backoffice_home(user=Depends(current_user)):
        return HTMLResponse(_backoffice_home(user))
