#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Business workbench home page for SaaS staff backoffice."""

from datetime import datetime
from pathlib import Path

from server.saas_deploy import validate_deployment_assets

from server.saas_license_status import render_saas_license_status
from server.saas_user_pages import _h, _page, _role_name


LEGACY_GAP_SCRIPT = 'scripts/saas_legacy_gap_check.py'
LEGACY_GAP_DOC = 'docs/saas-legacy-business-migration-gap.md'


def _platform_health_summary(user):
    if user.get('role_code') != 'platform_admin':
        return ''
    result = validate_deployment_assets(Path(__file__).resolve().parents[1])
    files = set(result.get('files', []))
    asset_status = 'PASS' if result.get('ok') else 'WARN'
    port_status = 'PASS' if result.get('port_binding', {}).get('localhost_only') else 'WARN'
    backup_status = 'PASS' if {'scripts/saas_backup.sh', 'scripts/saas_restore.sh'}.issubset(files) else 'WARN'
    https_status = result.get('nginx_tls', {}).get('status', 'unknown')
    return f'<section class="card" style="margin-bottom:18px"><div class="card-h">系统健康</div><div class="card-b"><div class="actions"><span class="badge">部署资产 {asset_status}</span><span class="badge">端口本机绑定 {port_status}</span><span class="badge">备份恢复脚本 {backup_status}</span><span class="badge">HTTPS {https_status}</span><a class="ghost-link" href="/backoffice/deploy-checklist">查看上线清单</a></div><div class="hint">平台运维摘要只展示检查结果，不展示生产密钥或 .env 内容。</div></div></section>'

def _money(value):
    return str(round(float(value or 0), 2))


def _count(items):
    return len(items or [])


def _dashboard_stats(user, period, service=None, repository=None):
    if repository:
        tenant_id = user['tenant_id']
        project_id = user['project_id']
        targets = repository.list_charge_targets(tenant_id, project_id)
        fees = repository.list_fee_types(tenant_id, project_id)
        summary = repository.report_summary(tenant_id, project_id, period)
    else:
        targets = service.list_charge_targets(user, user['project_id']) if service else []
        fees = service.list_fee_types(user, user['project_id']) if service else []
        summary = service.report(user, user['project_id'], period) if service else {}
    return {
        'target_count': _count(targets),
        'fee_count': _count(fees),
        'bill_count': int(summary.get('bill_count') or 0),
        'bill_amount_total': summary.get('bill_amount_total') or 0,
        'payment_amount_total': summary.get('payment_amount_total') or 0,
        'unpaid_amount_total': summary.get('unpaid_amount_total') or 0,
    }


def _metric(label, value, money=False):
    display = _money(value) if money else str(value)
    return f'<div class="metric"><div>{_h(label)}</div><strong>{_h(display)}</strong></div>'


def _link_card(title, desc, href, primary=False):
    cls = 'work-card primary-work-card' if primary else 'work-card'
    return f'<a class="{cls}" href="{_h(href)}"><strong>{_h(title)}</strong><span>{_h(desc)}</span></a>'


def _business_nav(user):
    can_manage = user.get('role_code') in {'system_admin', 'platform_admin'}
    platform = user.get('role_code') == 'platform_admin'
    admin_links = ''.join([
        '<a href="/backoffice/tenant-admin">租户管理员</a>' if user.get('role_code') == 'system_admin' else '',
        '<a href="/backoffice/tenant-projects">租户项目</a>' if can_manage else '',
        '<a href="/backoffice/users">账号管理</a>' if can_manage else '',
        '<a href="/backoffice/permissions">权限矩阵</a>',
        '<a href="/backoffice/audit-logs">审计日志</a>',
        '<a href="/backoffice/data-boundaries">数据边界</a>',
        '<a href="/backoffice/backups">备份恢复</a>' if can_manage else '',
        '<a href="/backoffice/tenant-business-config">业务配置</a>',
        '<a href="/backoffice/acceptance">商业验收</a>' if can_manage else '',
        '<a href="/backoffice/deploy-checklist">云端上线</a>' if can_manage else '',
    ])
    platform_links = ''.join([
        '<a href="/backoffice/tenant-onboarding">客户开通</a>',
        '<a href="/backoffice/license-ops">授权运维</a>',
        '<a href="/backoffice/production-delivery">生产交付总览</a>',
        '<a href="/backoffice/first-tenant-delivery-package">首租户交付包</a>',
        '<a href="/backoffice/deploy-checklist">云端上线</a>',
    ]) if platform else ''
    platform_section = f'<div class="nav-group"><b>平台运维</b>{platform_links}</div>' if platform_links else ''
    return f'''<aside class="business-nav"><div class="brand">物业收费系统</div>
<div class="nav-group"><b>日常业务</b><a href="/backoffice">工作台</a><a href="/backoffice/charge-targets">收费对象</a><a href="/backoffice/fee-types">收费项目</a><a href="/backoffice/bills">出账审核</a><a href="/backoffice/payments">收款登记</a><a href="/backoffice/reports">欠费报表</a></div>
<div class="nav-group"><b>数据维护</b><a href="/backoffice/owners">业主档案</a><a href="/backoffice/charge-targets">房间/铺位</a><a href="/backoffice/merchants">商户档案</a><a href="/backoffice/imports/templates/charge-targets">导入模板</a><a href="/backoffice/imports">Excel 导入</a></div>
<div class="nav-group"><b>查询报表</b><a href="/backoffice/bills">账单查询</a><a href="/backoffice/payments">收款流水</a><a href="/backoffice/reports">项目报表</a><a href="/api/exports/reports/breakdown.csv">导出</a></div>
<div class="nav-group"><b>系统管理</b>{admin_links}</div>{platform_section}</aside>'''


def _workbench(user, period, stats):
    metrics = ''.join([
        _metric('收费对象数', stats['target_count']),
        _metric('收费项目数', stats['fee_count']),
        _metric('账单数', stats['bill_count']),
        _metric('应收', stats['bill_amount_total'], True),
        _metric('实收', stats['payment_amount_total'], True),
        _metric('欠费', stats['unpaid_amount_total'], True),
    ])
    flow = ''.join([
        _link_card('业主档案', '维护业主、住户、商户联系人', '/backoffice/owners', True),
        _link_card('收费对象', '维护楼栋、房号、铺位、业主和商户资料', '/backoffice/charge-targets', True),
        _link_card('收费项目', '配置物业费、水费、停车费和固定金额规则', '/backoffice/fee-types', True),
        _link_card('批量出账', '出账收款：按项目、楼栋、分类批量生成账单', '/backoffice/bills', True),
        _link_card('账单审核', '审核账单后进入正式应收和收款', '/backoffice/bills'),
        _link_card('收款登记', '登记现金、转账和线下微信/支付宝收款', '/backoffice/payments', True),
        _link_card('欠费查询', '按账期核对应收、实收和欠费', '/backoffice/reports'),
        _link_card('收据打印', '从收款流水进入收据详情和打印页', '/backoffice/payments'),
        _link_card('报表导出', '导出账单、流水、分组汇总和欠费明细', '/backoffice/reports'),
        _link_card('数据导入', 'CSV / Excel 预览确认后导入收费对象', '/backoffice/imports', True),
    ])
    return f'''<section class="business-top"><div><h1>物业收费工作台</h1><p>按正式收费流程处理资料、出账、审核、收款、欠费和报表。</p></div><div class="tenant-chip">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="account-bar"><div><strong>当前账号：</strong>{_h(user.get('username'))}<span class="hint"> · {_h(_role_name(user.get('role_code')))}</span></div><form method="get" action="/backoffice"><label>账期</label><input name="period" value="{_h(period)}" placeholder="YYYY-MM"><button class="primary">查看</button></form><div class="actions"><a class="ghost-link" href="/backoffice/change-password">修改密码</a><form method="post" action="/api/auth/logout"><button class="danger">退出登录</button></form></div></section>
<section class="metric-grid">{metrics}</section>
<section class="card"><div class="card-h">收费业务流程</div><div class="card-b"><div class="work-grid">{flow}</div></div></section>'''


def _system_panel(user, license_service=None, service=None, repository=None):
    can_manage = user.get('role_code') in {'system_admin', 'platform_admin'}
    if not can_manage:
        return ''
    license_block = render_saas_license_status(user, license_service, service, repository)
    platform = user.get('role_code') == 'platform_admin'
    ops = ''.join([
        _link_card('租户管理员', '本公司管理员控制台和账号边界', '/backoffice/tenant-admin') if user.get('role_code') == 'system_admin' else '',
        _link_card('租户项目', '维护本公司项目边界', '/backoffice/tenant-projects'),
        _link_card('账号管理', '管理员工账号、停用、重置密码', '/backoffice/users'),
        _link_card('权限矩阵', '查看各角色可做和不可做', '/backoffice/permissions'),
        _link_card('审计日志', '查看导入、出账、审核、收款操作', '/backoffice/audit-logs'),
        _link_card('数据边界', '检查公司数据、上传数据和备份隔离边界', '/backoffice/data-boundaries'),
        _link_card('备份恢复', '创建备份记录和恢复演练', '/backoffice/backups'),
        _link_card('业务配置', '维护当前公司业务模板', '/backoffice/tenant-business-config'),
        _link_card('云端上线', 'VPS 部署、预检和备份恢复清单', '/backoffice/deploy-checklist'),
        _link_card('迁移差距', f'桌面业务迁移清单：{LEGACY_GAP_SCRIPT}，{LEGACY_GAP_DOC}', '/backoffice/acceptance#legacy-gap'),
        _link_card('商业验收', '按正式商业后台闭环逐项验收', '/backoffice/acceptance'),
        _link_card('生产交付总览', '部署验收和交付证据入口', '/backoffice/production-delivery'),
    ])
    if platform:
        ops += ''.join([
            _link_card('客户开通', '平台管理员开通新客户公司', '/backoffice/tenant-onboarding'),
            _link_card('首租户交付包', '实施初始化、业务闭环和验收入口', '/backoffice/first-tenant-delivery-package'),
            _link_card('授权运维', '查看授权状态和席位风险', '/backoffice/license-ops'),
            _link_card('生产交付总览', '部署验收和交付证据入口', '/backoffice/production-delivery'),
        ])
    return f'{license_block}<section class="card" style="margin-top:18px"><div class="card-h">系统管理</div><div class="card-b"><div class="work-grid">{ops}</div></div></section>'


def _backoffice_home(user, period='', license_service=None, service=None, repository=None):
    selected_period = period or datetime.now().strftime('%Y-%m')
    stats = _dashboard_stats(user, selected_period, service, repository)
    body = f'<div class="business-layout">{_business_nav(user)}<div class="business-main">{_platform_health_summary(user)}{_workbench(user, selected_period, stats)}{_system_panel(user, license_service, service, repository)}</div></div>'
    return _page('物业收费工作台', body)


def register_backoffice_pages(app, current_user, session_user=None):
    from fastapi import Depends
    from fastapi.responses import HTMLResponse, RedirectResponse

    @app.get('/backoffice', response_class=HTMLResponse)
    def backoffice_home(period: str = '', user=Depends(session_user or current_user)):
        if user.get('must_change_password'):
            return RedirectResponse('/backoffice/change-password', status_code=303)
        return HTMLResponse(_backoffice_home(user, period, getattr(app.state, 'license_service', None), app.state.saas_service, getattr(app.state, 'repository', None)))
