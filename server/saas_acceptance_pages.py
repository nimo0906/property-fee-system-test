#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML acceptance checklist page for SaaS backoffice."""

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


def _render(user):
    role_label = _role_name(user.get('role_code'))
    readonly = '<span class="badge">只读验收清单</span>' if user.get('role_code') not in {'system_admin', 'platform_admin'} else '<span class="badge">管理员验收</span>'
    body = f'''
<section class="hero"><div><h1>SaaS 商业后台验收</h1><div class="sub">用于正式商业版上线前，把员工后台完整闭环逐项走通：创建项目、导入/录入收费对象、配置收费项目、生成账单、审核账单、登记收款、对账报表、审计日志、备份恢复和租户隔离。</div></div><div class="badge tenant-scope">{_h(user.get('tenant_name'))} · {_h(user.get('project_name'))}</div></section>
<section class="card" style="margin-bottom:18px"><div class="card-b"><strong>当前角色：</strong>{_h(role_label)} {readonly}<div class="hint">自动验收命令：<code>PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_acceptance_check.py</code></div></div></section>
<section class="card"><div class="card-h">验收步骤</div><div class="card-b"><table><thead><tr><th>验收项</th><th>入口</th><th>通过标准</th></tr></thead><tbody>{_step_rows()}</tbody></table></div></section>
<section class="card" style="margin-top:18px"><div class="card-h">租户隔离检查</div><div class="card-b"><p class="sub">租户隔离：A 公司创建的收费对象、账单、收款、报表、审计日志、备份记录，B 公司不能读取或操作；客户上传数据与系统自身数据分目录保存。</p></div></section>'''
    return _page('SaaS 商业后台验收', body)


def register_acceptance_pages(app, current_user):
    from fastapi import Depends
    from fastapi.responses import HTMLResponse

    @app.get('/backoffice/acceptance', response_class=HTMLResponse)
    def acceptance_page(user=Depends(current_user)):
        return HTMLResponse(_render(user))
