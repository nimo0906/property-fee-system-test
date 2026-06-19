#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial readiness rendering for SaaS acceptance page."""

from server.saas_user_pages import _h

ITEMS = [
    ('P0-1 业主与收费对象', '业主档案、收费对象、导入映射已接入。', '/backoffice/charge-targets'),
    ('P0-2 计费规则', '面积计费、固定金额、独立单价、服务期折算已接入。', '/backoffice/fee-types'),
    ('P0-3 批量出账', '按当前租户项目批量生成账单，重复账单跳过。', '/backoffice/bills'),
    ('P0-4 收款欠费', '部分收款、已收、欠费和报表联动。', '/backoffice/payments'),
    ('P0-5 收据导出', '账单/收款导出和收据详情含业务字段，不含内部字段。', '/backoffice/payments'),
    ('P0-6 导入复核', '预览不写库、错误行下载、重复对象跳过。', '/backoffice/imports'),
    ('P0-7 高风险审计', '审计风险分级、详情脱敏、租户隔离查询。', '/backoffice/audit-logs'),
    ('P0-8 备份恢复', '备份和恢复演练显示操作人、审计链路、隐藏系统路径。', '/backoffice/backups'),
]
GATES = [
    ('租户隔离证据', 'scripts/saas_isolation_evidence.py'),
    ('商业上线总门禁', 'scripts/saas_release_gate.py'),
    ('上线证据报告', 'scripts/saas_release_evidence.py'),
    ('商业验收总览检查', 'scripts/saas_commercial_readiness_check.py'),
]


def render_commercial_readiness():
    item_rows = ''.join(
        f'<tr><td>{_h(name)}</td><td>{_h(desc)}</td><td><a class="ghost-link" href="{_h(href)}">检查</a></td></tr>'
        for name, desc, href in ITEMS
    )
    gate_rows = ''.join(
        f'<tr><td>{_h(name)}</td><td><code>{_h(command)}</code></td></tr>'
        for name, command in GATES
    )
    return f'''
<section class="card" style="margin-bottom:18px"><div class="card-h">商业上线总览</div><div class="card-b"><table><thead><tr><th>阶段</th><th>完成口径</th><th>入口</th></tr></thead><tbody>{item_rows}</tbody></table><div class="hint">本总览只展示业务验收项和脚本路径，不展示生产密钥、数据库密码或内部租户编号。</div></div></section>
<section class="card" style="margin-bottom:18px"><div class="card-h">上线门禁与证据</div><div class="card-b"><table><thead><tr><th>检查项</th><th>命令/资产</th></tr></thead><tbody>{gate_rows}</tbody></table></div></section>'''
