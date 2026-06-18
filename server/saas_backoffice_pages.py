#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML home pages for SaaS staff backoffice."""

from server.saas_user_pages import _h, _page, _role_name


def _module_card(title, desc, href=None, note=''):
    action = f'<a class="ghost-link" href="{_h(href)}">进入模块</a>' if href else f'<span class="hint">{_h(note)}</span>'
    return f'<div class="card"><div class="card-h">{_h(title)}</div><div class="card-b"><p class="sub">{_h(desc)}</p>{action}</div></div>'


def _backoffice_home(user):
    can_manage_users = user.get('role_code') in {'system_admin', 'platform_admin'}
    tenant_admin_card = _module_card(
        '租户管理员',
        '本公司管理员控制台：账号列表、停用员工账号、重置临时密码，并提示客户数据隔离边界。',
        '/backoffice/tenant-admin' if user.get('role_code') == 'system_admin' else None,
        '租户管理员入口仅本公司管理员可用',
    )
    user_card = _module_card(
        '账号管理',
        '管理员维护员工账号、停用离职账号、重置临时密码，并保留审计记录。',
        '/backoffice/users' if can_manage_users else None,
        '账号管理仅管理员可用',
    )
    tenant_project_card = _module_card(
        '租户项目',
        '维护本公司项目边界；平台管理员可只读查看租户和项目全局。',
        '/backoffice/tenant-projects' if can_manage_users else None,
        '租户项目仅管理员可用',
    )
    cards = ''.join([
        tenant_admin_card,
        tenant_project_card,
        user_card,
        _module_card('收费对象', '维护楼栋/区域、单元/分区、房号/铺位号等收费对象。', '/backoffice/charge-targets'),
        _module_card('收费项目', '配置物业费、水费、停车费等收费项目和价格规则。', '/backoffice/fee-types'),
        _module_card('出账收款 / 出账审核', '生成账单、审核账单、按账期和状态查询应收。', '/backoffice/bills'),
        _module_card('收款登记', '登记收款、查看收据号和收款流水。', '/backoffice/payments'),
        _module_card('对账报表', '按账期查看应收、实收和欠费。', '/backoffice/reports'),
        _module_card('数据导入', '导入收费对象，先预览校验再确认写入。', '/backoffice/imports'),
        _module_card('审计日志', '查看账号、导入、出账、审核、收款等关键操作。', '/backoffice/audit-logs'),
        _module_card('备份恢复', '创建备份记录，提交恢复演练。', '/backoffice/backups'),
        _module_card('云端上线', 'VPS 部署、预检、备份恢复和验收脚本清单。', '/backoffice/deploy-checklist'),
        _module_card('商业验收', '按正式商业后台闭环逐项验收。', '/backoffice/acceptance'),
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
