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
    ('P0-11 商业交付演示', '新租户从空库开始，完成创建项目、收费对象、收费项目、出账、审核、收款、报表、导出、备份恢复演练。', '/backoffice/acceptance'),
    ('P0-12 最小上线包', '整理部署配置、验收演示、运维备份、上线证据；不提交真实 .env，客户上传数据与系统自身数据隔离。', '/backoffice/deploy-checklist'),
    ('P0-13 客户交付签收', '上线前人工验收，覆盖部署完成确认、数据不混用确认、客户签收和实施人员签收。', '/backoffice/acceptance'),
    ('P0-14 上线总报告', 'SaaS 云端商业版上线总报告，汇总 P0-1 到 P0-13、验证命令、部署资产、演示路径和签收路径。', '/backoffice/acceptance'),
    ('P0-15 正式报告文件', '正式 DOCX/PDF 交付版：release/saas-commercial-launch-report.docx 与 release/saas-commercial-launch-report.pdf。', '/backoffice/acceptance'),
    ('P0-16 一页式上线指引', '实施人员按执行顺序完成服务器、环境、门禁、演示、备份恢复、隔离、签收和报告留存。', '/backoffice/acceptance'),
    ('P0-17 首日巡检清单', '上线后按 T+0、T+2、T+24 巡检服务健康、权限、隔离、收费抽查、备份、日志、审计和回退观察点。', '/backoffice/acceptance'),
    ('P0-18 七日稳定复盘', '上线后第 7 日复盘业务数据、金额报表、租户隔离、权限审计、备份恢复、客户反馈，并判断是否进入下一阶段。', '/backoffice/acceptance'),
    ('P0-19 下一阶段立项决策', '7 日稳定后评估业主端 H5、微信/支付宝真实支付、授权云服务后台、更多桌面业务迁移的进入条件和边界。', '/backoffice/acceptance'),
    ('P0-20 下一阶段工单清单', '把业主端 H5 工单包、支付工单包、授权云服务后台工单包和桌面版存量业务迁移工单包拆成可执行项。', '/backoffice/acceptance'),
    ('P0-21 授权云服务边界', '建立授权云服务后台的独立服务、独立数据库、独立表结构和授权校验边界，不与 SaaS 业务主库混用。', '/backoffice/acceptance'),
    ('P0-22 授权管理后台', '授权云服务支持客户、产品、授权、授权审计的 API 和管理页面；只展示授权数据，不展示业务数据。', '/backoffice/acceptance'),
    ('P0-23 授权状态展示', 'SaaS 员工后台只读取授权云服务返回结果，展示授权状态、席位和到期时间，不暴露授权库或业务库内部字段。', '/backoffice'),
    ('P0-24 授权限制策略', '未授权或授权过期时限制高风险写入操作，保留只读查看和数据核对，不破坏租户隔离。', '/backoffice'),
    ('P0-25 授权拦截审计', '授权限制触发时记录租户范围内的 license.write_blocked 审计事件，便于商业售后和争议追踪。', '/backoffice/audit-logs'),
    ('P0-26 授权席位限制', '授权席位数与启用员工账号数联动，超过席位时限制新增或启用员工账号并记录审计。', '/backoffice/users'),
    ('P0-27 授权状态运维', '平台管理员查看各租户授权状态、席位使用数、到期时间和超限风险，不展示业务数据或授权库内部字段。', '/backoffice/license-ops'),
    ('P0-28 授权客户绑定', 'SaaS 租户必须显式绑定授权客户编号，避免靠名称匹配导致授权错绑。', '/backoffice/license-ops'),
    ('P0-29 授权绑定管理入口', '平台管理员可在授权状态运维页绑定或变更租户授权客户编号，并写入 license.tenant_bind 审计。', '/backoffice/license-ops'),
    ('P0-30 授权绑定持久化', '授权绑定关系持久化到系统侧独立 JSON 文件，不写入客户上传数据目录或 SaaS 业务表。', '/backoffice/license-ops'),
    ('P0-31 授权绑定备份恢复', '授权绑定文件可导出、恢复和校验，保障服务器迁移或重部署后绑定不丢失。', '/backoffice/license-ops'),
    ('P0-32 授权绑定运维交付', '授权绑定、备份、恢复、迁移和审计检查整理为实施人员可执行交付清单。', '/backoffice/acceptance'),
    ('P0-33 实机部署演练', '通用 Linux/VPS、腾讯云 CVM、阿里云 ECS 按接近生产的部署、登录、业务闭环、隔离、授权绑定和备份恢复完成验收。', '/backoffice/deploy-checklist'),
    ('P0-34 生产部署一键自检', '实施人员用一条自检命令检查服务器环境、端口、目录隔离、Docker Compose、Nginx、systemd、logrotate、备份恢复、授权绑定和上线证据。', '/backoffice/deploy-checklist'),
    ('P0-35 首租户初始化向导', '提供可视化登录入口和平台管理员首租户初始化向导，从客户公司、默认项目、租户管理员、授权绑定进入导入、收费项目、测试账单和隔离验收。', '/backoffice/first-tenant-wizard'),
    ('P0-37 首租户业务引导闭环', '首租户创建后提供导入模板、收费项目、测试账单、测试收款、报表、验收记录的可点击交付路径。', '/backoffice/first-tenant-wizard'),
    ('P0-38 首租户交付验收记录', '实施人员在系统内勾选首租户上线交付项，留存实施人员、客户签收人、备注和完成项摘要。', '/backoffice/first-tenant-acceptance'),
    ('P0-39 首租户验收导出打印', '首租户交付验收记录支持打印版和 HTML 导出，作为客户签收材料留存。', '/backoffice/first-tenant-acceptance'),
]
GATES = [
    ('租户隔离证据', 'scripts/saas_isolation_evidence.py'),
    ('商业上线总门禁', 'scripts/saas_release_gate.py'),
    ('上线证据报告', 'scripts/saas_release_evidence.py'),
    ('商业验收总览检查', 'scripts/saas_commercial_readiness_check.py'),
    ('商业交付演示手册', 'docs/saas-commercial-delivery-drill.md'),
    ('商业交付演示脚本', 'scripts/saas_commercial_delivery_drill.py'),
    ('商业交付演示检查', 'scripts/saas_commercial_delivery_drill_check.py'),
    ('最小上线包清单', 'docs/saas-minimal-launch-package.md'),
    ('最小上线包检查', 'scripts/saas_minimal_launch_package_check.py'),
    ('客户交付签收清单', 'docs/saas-customer-acceptance-signoff.md'),
    ('客户交付签收检查', 'scripts/saas_customer_acceptance_signoff_check.py'),
    ('上线总报告', 'docs/saas-commercial-launch-report.md'),
    ('上线总报告检查', 'scripts/saas_commercial_launch_report_check.py'),
    ('正式报告 DOCX', 'release/saas-commercial-launch-report.docx'),
    ('正式报告 PDF', 'release/saas-commercial-launch-report.pdf'),
    ('正式报告检查', 'scripts/saas_formal_launch_report_check.py'),
    ('一页式上线指引', 'docs/saas-operator-one-page-runbook.md'),
    ('一页式上线指引检查', 'scripts/saas_operator_one_page_runbook_check.py'),
    ('首日巡检清单', 'docs/saas-day1-operations-checklist.md'),
    ('首日巡检检查', 'scripts/saas_day1_operations_checklist_check.py'),
    ('七日稳定复盘', 'docs/saas-day7-stability-review.md'),
    ('七日稳定复盘检查', 'scripts/saas_day7_stability_review_check.py'),
    ('下一阶段立项决策', 'docs/saas-next-phase-decision-checklist.md'),
    ('下一阶段立项决策检查', 'scripts/saas_next_phase_decision_check.py'),
    ('下一阶段工单清单', 'docs/saas-next-phase-issue-backlog.md'),
    ('下一阶段工单检查', 'scripts/saas_next_phase_issue_backlog_check.py'),
    ('授权云服务边界设计', 'docs/saas-license-cloud-service-boundary.md'),
    ('授权云服务边界检查', 'scripts/saas_license_cloud_boundary_check.py'),
    ('授权管理后台检查', 'scripts/saas_license_cloud_management_check.py'),
    ('授权状态展示检查', 'scripts/saas_license_status_integration_check.py'),
    ('授权限制策略检查', 'scripts/saas_license_enforcement_check.py'),
    ('授权拦截审计检查', 'scripts/saas_license_enforcement_audit_check.py'),
    ('授权席位限制检查', 'scripts/saas_license_seat_limit_check.py'),
    ('授权状态运维检查', 'scripts/saas_license_ops_page_check.py'),
    ('授权客户绑定检查', 'scripts/saas_license_tenant_binding_check.py'),
    ('授权绑定管理入口检查', 'scripts/saas_license_binding_page_check.py'),
    ('授权绑定持久化检查', 'scripts/saas_license_binding_persistence_check.py'),
    ('授权绑定备份恢复检查', 'scripts/saas_license_binding_backup_check.py'),
    ('授权绑定运维交付检查', 'scripts/saas_license_binding_runbook_check.py'),
    ('授权绑定运维交付清单', 'docs/saas-license-binding-ops-runbook.md'),
    ('实机部署演练检查', 'scripts/saas_production_deployment_rehearsal_check.py'),
    ('实机部署演练清单', 'docs/saas-production-deployment-rehearsal.md'),
    ('生产部署一键自检', 'scripts/saas_production_precheck.py'),
    ('生产部署自检说明', 'docs/saas-production-precheck.md'),
    ('首租户初始化向导检查', 'scripts/saas_first_tenant_wizard_check.py'),
    ('首租户业务引导闭环检查', 'scripts/saas_first_tenant_delivery_loop_check.py'),
    ('首租户交付验收记录检查', 'scripts/saas_first_tenant_acceptance_record_check.py'),
    ('首租户验收导出打印检查', 'scripts/saas_first_tenant_acceptance_export_check.py'),
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
