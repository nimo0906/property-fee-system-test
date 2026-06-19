#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First-run guide for new SaaS tenants."""

from server.saas_user_pages import _h

STEPS = [
    ('第 1 步：确认项目', '/backoffice/tenant-projects', '确认当前公司和项目边界。'),
    ('第 2 步：导入/录入收费对象', '/backoffice/imports', '可先上传登记并预览，也可手工录入。'),
    ('第 2 步补充：手工录入收费对象', '/backoffice/charge-targets', '维护楼栋/区域、单元/分区、房号/铺位号。'),
    ('第 3 步：配置收费项目', '/backoffice/fee-types', '配置物业费、水费、停车费等项目。'),
    ('第 4 步：生成并审核账单', '/backoffice/bills', '生成账单后先审核，再进入收款。'),
    ('第 5 步：登记收款', '/backoffice/payments', '登记现金、转账或线下微信/支付宝收款。'),
    ('第 6 步：查看报表和导出', '/backoffice/reports', '核对应收、实收、欠费并导出。'),
]


def render_first_run_guide(user):
    rows = ''.join(_step_row(user, title, href, desc) for title, href, desc in STEPS)
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">首次使用向导</div><div class="card-b"><div class="badge">空库启动</div><p class="sub" style="margin-top:10px">当前租户和项目隔离：先按下面顺序完成初始化，再开始正式收费。</p><table><thead><tr><th>步骤</th><th>入口</th><th>说明</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''


def _step_row(user, title, href, desc):
    if href == '/backoffice/tenant-projects' and user.get('role_code') not in {'system_admin', 'platform_admin'}:
        action = '<span class="hint">请管理员确认项目</span>'
    else:
        action = f'<a class="ghost-link" href="{_h(href)}">进入</a>'
    return f'''<tr><td>{_h(title)}</td><td>{action}</td><td>{_h(desc)}</td></tr>'''
