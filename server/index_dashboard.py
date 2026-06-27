#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Home dashboard render helpers."""

from server.index_shared import *
from server.ui_components import render_table


def _action_block(role, can_finance_write, can_customer_write):
    receipt_action = '<a href="/bills" class="btn btn-outline-secondary btn-sm"><i class="bi bi-printer"></i> 打印收据</a>' if can_finance_write else ''
    if can_finance_write:
        return f'''
                <a href="/bills/generate" class="btn btn-primary btn-sm"><i class="bi bi-file-earmark-plus"></i> 生成账单</a>
                <a href="/billing" class="btn btn-success btn-sm"><i class="bi bi-cash-coin"></i> 收费登记</a>
                {receipt_action}
                <a href="/reports" class="btn btn-outline-primary btn-sm"><i class="bi bi-graph-up"></i> 对账报表</a>
                <a href="/invoices" class="btn btn-outline-secondary btn-sm"><i class="bi bi-receipt-cutoff"></i> 发票管理</a>'''
    if can_customer_write:
        return '''
                <a href="/collections" class="btn btn-primary btn-sm"><i class="bi bi-telephone-outbound"></i> 客服催费对象</a>
                <a href="/owners" class="btn btn-outline-primary btn-sm"><i class="bi bi-people"></i> 业主管理</a>
                <a href="/rooms" class="btn btn-outline-primary btn-sm"><i class="bi bi-door-open"></i> 房间管理</a>
                <a href="/merchant_contracts" class="btn btn-outline-primary btn-sm"><i class="bi bi-file-earmark-text"></i> 合同档案</a>
                <a href="/meter_readings" class="btn btn-outline-secondary btn-sm"><i class="bi bi-clipboard-data"></i> 抄表管理</a>'''
    return '''
                <a href="/collections" class="btn btn-primary btn-sm"><i class="bi bi-telephone-outbound"></i> 客服催费对象</a>
                <a href="/bills" class="btn btn-outline-primary btn-sm"><i class="bi bi-receipt"></i> 账单管理</a>
                <a href="/reports" class="btn btn-outline-primary btn-sm"><i class="bi bi-graph-up"></i> 对账报表</a>'''


def _first_run_steps(can_finance_write, can_customer_write):
    if can_finance_write:
        return (
            '''<div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/import/template/basic.xlsx" download="basic_info_template.xlsx">1 下载导入模板</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/import">2 导入基础资料</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-secondary w-100" href="/fee_types">3 设置收费项目</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-success w-100" href="/bills/generate">4 生成账单</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-success w-100" href="/billing">5 收费登记</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-info w-100" href="/reports">6 对账报表</a></div>'''
        ), '建议先按模板整理楼栋、房号、楼层、业主、合同日期等基础资料，再生成账单。'
    if can_customer_write:
        return (
            '''<div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/import/template/basic.xlsx" download="basic_info_template.xlsx">1 下载导入模板</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/import">2 导入基础资料</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/owners">3 核对业主</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/rooms">4 核对房间</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/merchant_contracts">5 合同档案</a></div>'''
            '''<div class="col-md-2"><a class="btn btn-outline-info w-100" href="/collections">6 催缴跟进</a></div>'''
        ), '客服账号可维护业主、房间、合同、抄表和导入资料；账单生成、收款确认和结账由财务处理。'
    return (
        '''<div class="col-md-3"><a class="btn btn-outline-primary w-100" href="/bills">1 查看账单</a></div>'''
        '''<div class="col-md-3"><a class="btn btn-outline-primary w-100" href="/collections">2 客服催费对象</a></div>'''
        '''<div class="col-md-3"><a class="btn btn-outline-primary w-100" href="/reports">3 对账报表</a></div>'''
        '''<div class="col-md-3"><a class="btn btn-outline-secondary w-100" href="/owners">4 核对业主资料</a></div>'''
    ), '只读账号用于查看账单、跟进催费和核对资料，不显示生成账单或收费登记入口。'


def render_index_dashboard(handler, *, role, can_finance_write, can_customer_write, ta, tp, rate, enterprise,
                           p, month_start, month_end, today_paid, pending_cnt, overdue_cnt, today_payment_cnt,
                           invoice_todo_cnt, zero_amount_cnt, meter_needed, pending_rows, contract_rows, fts):
    paid_link = '/payments' if can_finance_write else '/reports'
    contract_alert_link = '/alert_center' if can_finance_write else '/merchant_contracts'
    invoice_link = '/invoices' if can_finance_write else '/bills'
    health_link = '/system_health' if role in ('admin', 'system_admin') else '/reports'
    contract_risks = enterprise['risk_counts']
    b_data = enterprise['segments'].get('B座', {'due': 0, 'paid': 0, 'bill_count': 0})
    mall_data = enterprise['segments'].get('商场', {'due': 0, 'paid': 0, 'bill_count': 0})
    b_rate = round(float(b_data['paid'] or 0) / float(b_data['due'] or 1) * 100, 1) if float(b_data['due'] or 0) > 0 else 0
    mall_rate = round(float(mall_data['paid'] or 0) / float(mall_data['due'] or 1) * 100, 1) if float(mall_data['due'] or 0) > 0 else 0
    total_fee_due = sum(float(f['tot'] or 0) for f in fts) or 1
    top_fees = fts[:3]

    def pct_width(value):
        try:
            return max(0, min(100, float(value)))
        except Exception:
            return 0

    fee_rows = ''.join(
        '<div class="focus-bar-row"><span>{}</span><div class="focus-track"><div class="focus-fill" style="width:{}%"></div></div><b>{}%</b></div>'.format(
            h(f["name"]),
            pct_width(float(f['tot'] or 0) / total_fee_due * 100),
            round(float(f['tot'] or 0) / total_fee_due * 100),
        )
        for f in top_fees
    ) or '<div class="focus-empty">暂无收入结构</div>'
    month_due = float(ta or 0) - float(tp or 0)
    due_width = pct_width(month_due / float(ta or 1) * 100) if float(ta or 0) > 0 else 0
    priority_cards = f'''
            <a class="focus-risk" href="/bills?status=unpaid&period_start={month_start}&period_end={month_end}"><i class="risk-line red"></i><b>待收费账单</b><strong>{pending_cnt}</strong></a>
            <a class="focus-risk" href="{contract_alert_link}"><i class="risk-line gold"></i><b>合同预警</b><strong>{contract_risks["contracts_expiring_30d"]}</strong></a>
            <a class="focus-risk" href="/meter_readings"><i class="risk-line blue"></i><b>待抄表确认</b><strong>{meter_needed}</strong></a>
        '''
    if can_finance_write:
        quick_actions = '''
            <a class="focus-action active" href="/bills">账单核对</a>
            <a class="focus-action" href="/reminders">催缴名单</a>
            <a class="focus-action" href="/merchant_contracts">合同预警</a>
            <a class="focus-action" href="/reports">对账报表</a>
        '''
    elif can_customer_write:
        quick_actions = '''
            <a class="focus-action active" href="/collections">催缴对象</a>
            <a class="focus-action" href="/rooms">房间资料</a>
            <a class="focus-action" href="/merchant_contracts">合同档案</a>
            <a class="focus-action" href="/meter_readings">抄表管理</a>
        '''
    else:
        quick_actions = '''
            <a class="focus-action active" href="/bills">账单管理</a>
            <a class="focus-action" href="/collections">催缴对象</a>
            <a class="focus-action" href="/reports">对账报表</a>
            <a class="focus-action" href="/owners">业主资料</a>
        '''
    primary_actions = _action_block(role, can_finance_write, can_customer_write)
    first_run_steps, first_run_note = _first_run_steps(can_finance_write, can_customer_write)
    pending_table = render_table(
        ['编号', '房间', '业主', '项目', ('待收', 'text-end'), '操作'],
        pending_rows,
        table_class='table table-hover mb-0 small',
        empty_text='暂无待收费账单',
        col_count=6,
    )
    contract_table = render_table(
        ['房间', '业主', '到期', ''],
        contract_rows,
        table_class='table table-sm mb-0',
        empty_text='30天内暂无到期合同',
        col_count=4,
    )
    html = f"""
        <section class="workbench-command-shell dashboard-focus-shell">
            <div class="workbench-command-hero">
                <button class="workbench-menu-chip d-lg-none" type="button" data-bs-toggle="offcanvas" data-bs-target="#mobileNav" aria-label="打开菜单"><i class="bi bi-list"></i> 菜单</button>
                <div class="workbench-title-block">
                    <div class="focus-kicker">PROPERTY FINANCE</div>
                    <h2>收费工作台</h2>
                </div>
                <div class="workbench-command-actions workbench-primary-actions">{primary_actions}</div>
            </div>
            {handler._default_password_warning_html()}
            <div class="workbench-proposal-grid">
                <section class="workbench-main-panel">
                    <div class="panel-heading">
                        <div>
                            <div class="focus-kicker">PROPERTY FINANCE COMMAND</div>
                            <h2>经营看板</h2>
                        </div>
                        <div class="period-pill">{p}</div>
                    </div>
                    <nav class="workbench-view-tabs" data-testid="workbench-view-tabs" aria-label="收费工作台视图">
                        <a class="active" href="#today-focus"><i class="bi bi-lightning-charge"></i> 今日</a>
                        <a href="#month-summary"><i class="bi bi-calendar3"></i> 本月</a>
                        <a href="/bills?building=B%E5%BA%A7&period_start={month_start}&period_end={month_end}"><i class="bi bi-building"></i> B座</a>
                        <a href="/bills?building=%E5%95%86%E5%9C%BA&period_start={month_start}&period_end={month_end}"><i class="bi bi-shop"></i> 商场</a>
                    </nav>
                    <div class="today-command-grid" id="today-focus">
                        <a class="today-command-item" href="/bills?status=unpaid&period_start={month_start}&period_end={month_end}">
                            <span>待收费账单</span><strong>{pending_cnt}</strong><em>今日优先</em>
                        </a>
                        <a class="today-command-item warn" href="{contract_alert_link}">
                            <span>合同预警</span><strong>{contract_risks["contracts_expiring_30d"]}</strong><em>30天内</em>
                        </a>
                        <a class="today-command-item blue" href="/meter_readings">
                            <span>待抄表确认</span><strong>{meter_needed}</strong><em>本月</em>
                        </a>
                    </div>
                    <div class="focus-card focus-summary-card" id="month-summary">
                        <div class="focus-card-inner focus-summary-grid">
                            <div>
                                <div class="focus-eyebrow">本月应收</div>
                                <div class="focus-money">¥{m(ta)}</div>
                                <div class="focus-stat-grid">
                                    <a class="focus-stat" href="{paid_link}"><span>已收</span><b>¥{m(tp)}</b></a>
                                    <a class="focus-stat red" href="/bills?status=unpaid&period_start={month_start}&period_end={month_end}"><span>未收</span><b>¥{m(month_due)}</b></a>
                                    <a class="focus-stat gold" href="{contract_alert_link}"><span>合同预警</span><b>{contract_risks["contracts_expiring_30d"]} 份</b></a>
                                </div>
                            </div>
                            <div class="focus-ring" style="--rate:{pct_width(rate)}%"><div><b>{rate}%</b><span>收缴率</span></div></div>
                        </div>
                    </div>
                </section>
                <aside class="workbench-side-panel">
                    <div class="focus-section-title"><b>快捷入口</b><span>财务操作</span></div>
                    <div class="focus-actions side-actions">{quick_actions}</div>
                    <div class="focus-card"><div class="focus-card-inner">
                        <div class="focus-section-title"><b>B座 / 商场</b><span>收缴率</span></div>
                        <div class="focus-bars">
                            <div class="focus-bar-row"><span>B座</span><div class="focus-track"><div class="focus-fill" style="width:{pct_width(b_rate)}%"></div></div><b>{b_rate}%</b></div>
                            <div class="focus-bar-row"><span>商场</span><div class="focus-track"><div class="focus-fill gold" style="width:{pct_width(mall_rate)}%"></div></div><b>{mall_rate}%</b></div>
                            <div class="focus-bar-row"><span>欠费</span><div class="focus-track"><div class="focus-fill red" style="width:{due_width}%"></div></div><b>{pending_cnt}</b></div>
                        </div>
                    </div></div>
                    <div class="focus-card"><div class="focus-card-inner">
                        <div class="focus-section-title"><b>业务动态</b><span>实时</span></div>
                        <div class="focus-mini-list">
                            <a class="focus-mini" href="{paid_link}"><b>今日收款 <em>¥{m(today_paid)}</em></b></a>
                            <a class="focus-mini" href="{invoice_link}"><b>待开票 <em>{invoice_todo_cnt} 笔</em></b></a>
                            <a class="focus-mini" href="/meter_readings"><b>待抄表 <em>{meter_needed} 项</em></b></a>
                        </div>
                    </div></div>
                </aside>
            </div>
            <div class="dashboard-focus-grid workbench-lower-grid">
                <div class="focus-card"><div class="focus-card-inner">
                    <div class="focus-section-title"><b>收入结构</b><span>本月</span></div>
                    <div class="focus-bars">{fee_rows}</div>
                </div></div>
                <div class="focus-card"><div class="focus-card-inner">
                    <div class="focus-section-title"><b>本月收费概况</b><span>看板</span></div>
                    <div class="row text-center g-2">
                        <div class="col-6"><div class="summary-tile"><div class="label">待收费账单</div><strong>{pending_cnt}</strong><span class="text-muted small"> 笔</span></div></div>
                        <div class="col-6"><div class="summary-tile"><div class="label">收缴率</div><strong>{rate}%</strong></div></div>
                    </div>
                </div></div>
                <div class="focus-card"><div class="focus-card-inner">
                    <div class="focus-section-title"><b>优先处理</b><span>今日</span></div>
                    <div class="focus-risk-list">{priority_cards}</div>
                </div></div>
            </div>
        </section>
        <div class="row g-3 mb-3 mt-3">
            <div class="col-md-7">
                <div class="card"><div class="card-header py-2 d-flex justify-content-between"><span><i class="bi bi-list-check"></i> 待收费账单</span><a href="/bills?status=unpaid" class="btn btn-sm btn-outline-primary">查看全部</a></div>
                {pending_table}</div>
            </div>
            <div class="col-md-5">
                <div class="card mb-3"><div class="card-header py-2"><i class="bi bi-calendar-check"></i> 即将到期合同</div>{contract_table}</div>
            </div>
        </div>
    """
    return html, primary_actions
