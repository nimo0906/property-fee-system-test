#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML acceptance checklist page for SaaS backoffice."""

from server.saas_password_policy import password_policy_summary
from server.saas_service import PermissionDenied
from server.saas_user_pages import _h, _page, _role_name

STEPS = [
    ('创建项目', '/backoffice', '登录后确认当前租户、项目、角色显示正确。'),
    ('导入/录入收费对象', '/backoffice/imports', '先导入预览，不写库；确认后只写有效行。'),
    ('录入收费对象', '/backoffice/charge-targets', '手工新增楼栋/区域、单元/分区、房号/铺位号。'),
    ('配置收费项目', '/backoffice/fee-types', '配置物业费、水费、停车费等收费项目和单价。'),
    ('生成账单', '/backoffice/bills', '收费对象和收费项目生成 pending_review 账单。'),
    ('审核账单', '/backoffice/bills', '待审核账单审核通过后变为 unpaid。'),
    ('登记收款', '/backoffice/payments', '未收/部分收款账单登记收款，生成收据号。'),
    ('对账报表', '/backoffice/reports', '按账期核对账单数量、应收、实收、欠费。'),
    ('审计日志', '/backoffice/audit-logs', '核对关键操作可追溯且不泄露密码。'),
    ('备份恢复', '/backoffice/backups', '创建备份记录并提交恢复演练。'),
]


def _step_rows():
    return ''.join(f'<tr><td>{_h(name)}</td><td><a class="ghost-link" href="{_h(href)}">进入模块</a></td><td>{_h(desc)}</td></tr>' for name, href, desc in STEPS)


def _policy_items():
    return ''.join(f'<li>{_h(text)}</li>' for text in password_policy_summary())


def _count_import_batches(service, user):
    return len([row for row in service.imports.values() if int(row.get('tenant_id')) == int(user['tenant_id']) and int(row.get('project_id')) == int(user['project_id'])])


def _status_rows(status):
    rows = [
        ('收费对象', status['target_count'], '/backoffice/charge-targets'),
        ('收费项目', status['fee_type_count'], '/backoffice/fee-types'),
        ('账单', status['bill_count'], '/backoffice/bills'),
        ('已审核账单', status['approved_bill_count'], '/backoffice/bills'),
        ('收款记录', status['payment_count'], '/backoffice/payments'),
        ('导入批次', status['import_batch_count'], '/backoffice/imports'),
        ('审计日志', status['audit_count'], '/backoffice/audit-logs'),
        ('备份记录', status['backup_count'], '/backoffice/backups'),
        ('恢复演练', status['restore_drill_count'], '/backoffice/backups'),
    ]
    return ''.join(f'<tr><td>{_h(name)}</td><td>{_h(value)}</td><td><a class="ghost-link" href="{_h(href)}">检查</a></td></tr>' for name, value, href in rows)


def _next_action(status):
    checks = [
        (status['target_count'], '下一步建议：先录入或导入收费对象', '/backoffice/imports'),
        (status['fee_type_count'], '下一步建议：配置收费项目', '/backoffice/fee-types'),
        (status['bill_count'], '下一步建议：生成账单', '/backoffice/bills'),
        (status['approved_bill_count'], '下一步建议：审核账单', '/backoffice/bills'),
        (status['payment_count'], '下一步建议：登记收款', '/backoffice/payments'),
        (status['backup_count'], '下一步建议：创建备份记录', '/backoffice/backups'),
        (status['restore_drill_count'], '下一步建议：提交恢复演练', '/backoffice/backups'),
    ]
    for count, text, href in checks:
        if not count:
            return text, href
    return '全部核心步骤已有数据', '/backoffice/reports'


def _render_status(status, period):
    next_text, next_href = _next_action(status)
    summary = status['report']
    return f'''
<section class="card" style="margin-bottom:18px"><div class="card-h">闭环状态总览</div><div class="card-b"><div class="actions" style="margin-bottom:12px"><span class="badge">当前账期：{_h(period)}</span><a class="ghost-link" href="/backoffice/reports?period={_h(period)}">查看账期报表</a></div><table><thead><tr><th>检查项</th><th>当前数量</th><th>入口</th></tr></thead><tbody>{_status_rows(status)}</tbody></table><div class="hint" style="margin-top:12px">下一步建议：{_h(next_text).replace('下一步建议：', '')} · <a class="ghost-link" href="{_h(next_href)}">进入处理</a></div></div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">对账摘要</div><div class="card-b"><table><tbody><tr><th>账单数</th><td>{_h(summary.get('bill_count', 0))}</td></tr><tr><th>应收</th><td>{_h(summary.get('bill_amount_total', 0.0))}</td></tr><tr><th>实收</th><td>{_h(summary.get('payment_amount_total', 0.0))}</td></tr><tr><th>欠费</th><td>{_h(summary.get('unpaid_amount_total', 0.0))}</td></tr></tbody></table></div></section>'''


def _collect_status(user, service, repository, period):
    service._require(user, 'read')
    if repository:
        targets = repository.list_charge_targets(user['tenant_id'], user['project_id'])
        fees = repository.list_fee_types(user['tenant_id'], user['project_id'])
        bills = repository.list_bills(user['tenant_id'], user['project_id'], period)
        payments = repository.search_payments(user['tenant_id'], user['project_id'], '', period, 1, 10000)['items']
        audits = repository.list_audit_logs(user['tenant_id'], user['project_id'])
        backups = repository.list_backup_records(user['tenant_id'], user['project_id'])
        drills = repository.list_restore_drills(user['tenant_id'], user['project_id'])
        report = repository.report_summary(user['tenant_id'], user['project_id'], period)
    else:
        targets = service.list_charge_targets(user, user['project_id'])
        fees = service.list_fee_types(user, user['project_id'])
        bills = service.list_bills(user, user['project_id'], period)
        payments = service.search_payments(user, user['project_id'], '', period, 1, 10000)['items']
        audits = service.list_audit_logs(user, user['project_id'])
        backups = [r for r in service.backup_records.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == user['project_id']]
        drills = [r for r in service.restore_drills.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == user['project_id']]
        report = service.report(user, user['project_id'], period)
    return {
        'target_count': len(targets), 'fee_type_count': len(fees), 'bill_count': len(bills),
        'approved_bill_count': len([b for b in bills if b.get('status') != 'pending_review']),
        'payment_count': len(payments), 'import_batch_count': _count_import_batches(service, user),
        'audit_count': len(audits), 'backup_count': len(backups), 'restore_drill_count': len(drills), 'report': report,
    }


def _render(user, status, period):
    role_label = _role_name(user.get('role_code'))
    readonly = '<span class="badge">只读验收清单</span>' if user.get('role_code') not in {'system_admin', 'platform_admin'} else '<span class="badge">管理员验收</span>'
    body = f'''
<section class="hero"><div><h1>SaaS 商业后台验收</h1><div class="sub">用于正式商业版上线前，把员工后台完整闭环逐项走通：创建项目、导入/录入收费对象、配置收费项目、生成账单、审核账单、登记收款、对账报表、审计日志、备份恢复和租户隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><strong>当前角色：</strong>{_h(role_label)} {readonly}<div class="hint">自动验收命令：<code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_acceptance_check.py</code></div><div class="hint">第一阶段收口：<code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_phase1_closure_check.py</code> · 文档 <code>docs/saas-phase-1-closure-report.md</code></div><div class="hint">样例客户验收演练：<code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_demo_tenant_drill.py</code> · 文档 <code>docs/saas-demo-tenant-drill.md</code></div><div class="hint">商业上线总门禁：<code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_release_gate.py</code></div><div class="hint">上线证据报告：<code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_release_evidence.py</code></div></div></section>
{_render_status(status, period)}
<section class="card"><div class="card-h">验收步骤</div><div class="card-b"><table><thead><tr><th>验收项</th><th>入口</th><th>通过标准</th></tr></thead><tbody>{_step_rows()}</tbody></table></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">密码策略</div><div class="card-b"><ul>{_policy_items()}</ul></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">租户隔离检查</div><div class="card-b"><p class="sub">租户隔离：A 公司创建的收费对象、账单、收款、报表、审计日志、备份记录，B 公司不能读取或操作；客户上传数据与系统自身数据分目录保存。</p></div></section>'''
    return _page('SaaS 商业后台验收', body)


def register_acceptance_pages(app, current_user, service=None, repository=None):
    from fastapi import Depends, HTTPException
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/acceptance', response_class=HTMLResponse)
    def acceptance_page(period: str = '2026-12', user=Depends(current_user)):
        try:
            status = _collect_status(user, service, repository, period) if service else {'report': {}}
            return HTMLResponse(_render(user, status, period))
        except PermissionDenied:
            raise HTTPException(status_code=403, detail='forbidden')
