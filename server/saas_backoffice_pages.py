#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML home pages for SaaS staff backoffice."""

from pathlib import Path

from server.saas_deploy import validate_deployment_assets
from server.saas_first_run_guide import render_first_run_guide
from server.saas_license_status import render_saas_license_status
from server.saas_user_pages import _h, _page, _role_name


def _module_card(title, desc, href=None, note=''):
    action = f'<a class="ghost-link" href="{_h(href)}">进入模块</a>' if href else f'<span class="hint">{_h(note)}</span>'
    return f'<div class="card"><div class="card-h">{_h(title)}</div><div class="card-b"><p class="sub">{_h(desc)}</p>{action}</div></div>'


def _platform_health_summary(user):
    if user.get('role_code') != 'platform_admin':
        return ''
    result = validate_deployment_assets(Path(__file__).resolve().parents[1])
    files = set(result.get('files', []))
    asset_status = 'PASS' if result.get('ok') else 'WARN'
    port_status = 'PASS' if result.get('port_binding', {}).get('localhost_only') else 'WARN'
    backup_status = 'PASS' if {'scripts/saas_backup.sh', 'scripts/saas_restore.sh'}.issubset(files) else 'WARN'
    https_status = result.get('nginx_tls', {}).get('status', 'unknown')
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">系统健康</div><div class="card-b"><div class="actions"><span class="badge">部署资产 {asset_status}</span><span class="badge">端口本机绑定 {port_status}</span><span class="badge">备份恢复脚本 {backup_status}</span><span class="badge">HTTPS {https_status}</span><a class="ghost-link" href="/backoffice/deploy-checklist">查看上线清单</a></div><div class="hint">平台运维摘要只展示检查结果，不展示生产密钥或 .env 内容。</div></div></section>'''


def _backoffice_home(user, license_service=None, service=None, repository=None):
    can_manage_users = user.get('role_code') in {'system_admin', 'platform_admin'}
    tenant_admin_card = _module_card('租户管理员', '本公司管理员控制台：账号列表、停用员工账号、重置临时密码，并提示客户数据隔离边界。', '/backoffice/tenant-admin' if user.get('role_code') == 'system_admin' else None, '租户管理员入口仅本公司管理员可用')
    user_card = _module_card('账号管理', '管理员维护员工账号、停用离职账号、重置临时密码，并保留审计记录。', '/backoffice/users' if can_manage_users else None, '账号管理仅管理员可用')
    onboarding_card = _module_card('客户开通', '平台管理员开通新客户公司、默认项目和首个租户管理员。', '/backoffice/tenant-onboarding' if user.get('role_code') == 'platform_admin' else None, '客户开通仅平台管理员可用')
    first_wizard_card = _module_card('首租户初始化', '正式交付向导：创建客户公司、默认项目、租户管理员、授权绑定，并进入导入、收费项目和验收闭环。', '/backoffice/first-tenant-wizard' if user.get('role_code') == 'platform_admin' else None, '首租户初始化仅平台管理员可用')
    delivery_package_card = _module_card('首租户交付包', '实施人员统一入口：登录、初始化、业务闭环、验收记录、打印导出、部署自检、备份恢复和授权绑定。', '/backoffice/first-tenant-delivery-package' if can_manage_users else None, '首租户交付包仅管理员可用')
    tenant_project_card = _module_card('租户项目', '维护本公司项目边界；平台管理员可只读查看租户和项目全局。', '/backoffice/tenant-projects' if can_manage_users else None, '租户项目仅管理员可用')
    business_config_card = _module_card('业务配置', '维护本公司业务模板，导入模板和收费项目建议按当前公司业务显示。', '/backoffice/tenant-business-config')
    cards = ''.join([
        tenant_admin_card, onboarding_card, first_wizard_card, delivery_package_card, tenant_project_card, business_config_card, user_card,
        _module_card('授权运维', '平台管理员查看租户授权状态、席位使用、到期时间和超限风险。', '/backoffice/license-ops' if user.get('role_code') == 'platform_admin' else None, '授权运维仅平台管理员可用'),
        _module_card('收费对象', '维护楼栋/区域、单元/分区、房号/铺位号等收费对象。', '/backoffice/charge-targets'),
        _module_card('商户档案', '维护商户/商业铺位的铺位号、店名、承租人、电话、面积、独立单价和缴费周期。', '/backoffice/merchants'),
        _module_card('收费项目', '配置物业费、水费、停车费等收费项目和价格规则。', '/backoffice/fee-types'),
        _module_card('出账收款 / 出账审核', '生成账单、审核账单、按账期和状态查询应收。', '/backoffice/bills'),
        _module_card('收款登记', '登记收款、查看收据号和收款流水。', '/backoffice/payments'),
        _module_card('对账报表', '按账期查看应收、实收和欠费。', '/backoffice/reports'),
        _module_card('数据导入', '导入收费对象，先预览校验再确认写入。', '/backoffice/imports'),
        _module_card('权限矩阵', '查看各角色可做、不可做和租户隔离边界。', '/backoffice/permissions'),
        _module_card('数据边界', '检查公司数据、客户上传数据、系统自身数据和备份恢复的隔离边界。', '/backoffice/data-boundaries'),
        _module_card('审计日志', '查看账号、导入、出账、审核、收款等关键操作。', '/backoffice/audit-logs'),
        _module_card('备份恢复', '创建备份记录，提交恢复演练。', '/backoffice/backups'),
        _module_card('生产交付总览', '现场实施统一入口：部署自检、生产验收、证据包、签收历史和备份恢复覆盖核验。', '/backoffice/production-delivery' if can_manage_users else None, '生产交付总览仅管理员可用'),
        _module_card('云端上线', 'VPS 部署、预检、备份恢复和验收脚本清单。', '/backoffice/deploy-checklist'),
        _module_card('迁移差距', '原桌面版业务能力到 SaaS 云端版迁移差距清单：收费核心、商户合同、水电表、停车费等后续迁移路线。', '/backoffice/acceptance#legacy-gap'),
        _module_card('商业验收', '按正式商业后台闭环逐项验收。', '/backoffice/acceptance'),
    ])
    health = _platform_health_summary(user)
    body = f'''
<section class="hero"><div><h1>SaaS 员工后台</h1><div class="sub">正式商业云端后台入口。当前租户、项目和角色会决定可见模块，避免不同公司数据混在一起。迁移检查：scripts/saas_legacy_gap_check.py，文档：docs/saas-legacy-business-migration-gap.md。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b" style="display:flex;justify-content:space-between;gap:12px;align-items:center"><div><strong>当前账号：</strong>{_h(user.get('username'))}<span class="hint"> · {_h(_role_name(user.get('role_code')))}</span></div><div class="actions"><a class="ghost-link" href="/backoffice/change-password">修改密码</a><form method="post" action="/api/auth/logout"><button class="danger">退出登录</button></form></div></div></section>
{health}{render_saas_license_status(user, license_service, service, repository)}{render_first_run_guide(user)}<section class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr))">{cards}</section>'''
    return _page('SaaS 员工后台', body)


def register_backoffice_pages(app, current_user, session_user=None):
    from fastapi import Depends
    from fastapi.responses import HTMLResponse, RedirectResponse

    @app.get('/backoffice', response_class=HTMLResponse)
    def backoffice_home(user=Depends(session_user or current_user)):
        if user.get('must_change_password'):
            return RedirectResponse('/backoffice/change-password', status_code=303)
        return HTMLResponse(_backoffice_home(user, getattr(app.state, 'license_service', None), app.state.saas_service, getattr(app.state, 'repository', None)))
