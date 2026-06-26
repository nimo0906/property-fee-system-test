#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto billing page rendering helpers."""

from server.auto_billing_runs import run_row_html
from server.auto_billing_scope import SCOPE_OPTIONS, grouped_auto_fees
from server.db import h, m
from server.ui_components import render_table


def render_auto_billing_page(advance_days, fee_options, selected_fee_ids, items, runs, preview_status='all', period_cycle='tenant', target_scope='all'):
    fee_checks = _grouped_fee_checks(fee_options, selected_fee_ids)
    hidden_fee_ids = ''.join(f'<input type="hidden" name="fee_ids" value="{fid}">' for fid in selected_fee_ids)
    status_opts = _status_options(preview_status)
    cycle_opts = _cycle_options(period_cycle)
    scope_opts = _scope_options(target_scope)
    rows = ''.join(_preview_row(x) for x in items)
    preview_empty = _empty_preview_text(preview_status)
    preview_table = render_table(
        ['选择', '租户', '房间/铺位', '收费项目', '服务期', '缴费截止日', ('金额', 'text-end'), '状态'],
        rows,
        table_class='table table-hover align-middle small',
        empty_text=preview_empty,
        col_count=8,
    )
    run_rows = ''.join(run_row_html(r) for r in runs)
    run_table = render_table(
        ['批次号', '生成时间', '操作人', ('笔数', 'text-end'), '服务期范围', '状态', '操作'],
        run_rows,
        table_class='table table-hover align-middle small mb-0',
        empty_text='暂无自动出账记录',
        col_count=7,
    )
    summary = _preview_summary(items)
    no_can_alert = _no_can_alert(summary['can'])
    submit_button = _submit_button(summary['can'])
    return f'''
    <div class="auto-billing-console">
    <div class="d-flex flex-wrap gap-2 justify-content-end mb-3">
      <a class="btn btn-outline-primary" href="/commercial_receivables">
        <i class="bi bi-shop"></i> 商业合同应收
      </a>
    </div>
    <div class="alert alert-info">
      <div><strong>自动出账规则：</strong>按租户合同开始日、结束日、缴费周期计算下一期出账服务期。</div>
      <div>提前 {advance_days} 天只是筛选即将到期的下一期；已存在账单不会重复生成；生成后按缴费截止日进入催缴管理。</div>
    </div>
    <form method="GET" action="/auto_billing" class="row g-2 mb-3 auto-filter-panel">
      <div class="col-auto"><label class="col-form-label">提前出账天数</label></div>
      <div class="col-auto"><input type="number" class="form-control" name="advance_days" min="0" max="365" value="{advance_days}"></div>
      <div class="col-auto"><label class="col-form-label">本次服务期</label></div>
      <div class="col-auto"><select class="form-select" name="period_cycle">{cycle_opts}</select></div>
      <div class="col-auto"><label class="col-form-label">出账范围</label></div>
      <div class="col-auto"><select class="form-select" name="target_scope">{scope_opts}</select></div>
      <div class="col-auto"><label class="col-form-label">预览状态</label></div>
      <div class="col-auto"><select class="form-select" name="preview_status">{status_opts}</select></div>
      <div class="col-12"><div class="card"><div class="card-header py-2">收费项目选择</div><div class="card-body py-2">{fee_checks}</div></div></div>
      <div class="col-auto"><button class="btn btn-primary">刷新预览</button></div>
    </form>
    <div class="card mb-3"><div class="card-header">预览汇总</div><div class="card-body">
      <div class="row text-center g-3">
        <div class="col-md-2"><small class="text-muted">可生成</small><div>可生成 {summary['can']} 笔</div></div>
        <div class="col-md-2"><small class="text-muted">已存在</small><div>已存在 {summary['existing']} 笔</div></div>
        <div class="col-md-2"><small class="text-muted">涉及租户</small><div>涉及租户 {summary['tenants']} 户</div></div>
        <div class="col-md-2"><small class="text-muted">涉及房间</small><div>涉及房间 {summary['rooms']} 间</div></div>
        <div class="col-md-4"><small class="text-muted">应收合计</small><div>应收合计 ¥{m(summary['amount'])}</div></div>
      </div>
    </div></div>
    {no_can_alert}
    <form method="POST" action="/auto_billing/confirm">
      <input type="hidden" name="advance_days" value="{advance_days}"><input type="hidden" name="period_cycle" value="{h(period_cycle)}"><input type="hidden" name="target_scope" value="{h(target_scope)}"><input type="hidden" name="preview_status" value="{h(preview_status)}">{hidden_fee_ids}
      {preview_table}
      {submit_button}
    </form>
    <div class="card mt-3 auto-run-history"><div class="card-header">最近自动出账记录</div>
    {run_table}</div>
    </div>'''


def _grouped_fee_checks(fee_options, selected_fee_ids):
    blocks = []
    selected = {int(x) for x in selected_fee_ids}
    for _key, label, fees in grouped_auto_fees(fee_options):
        checks = ''.join(
            f'''<label class="form-check form-check-inline mb-2">
                <input class="form-check-input" type="checkbox" name="fee_ids" value="{f['id']}"
                    {"checked" if int(f['id']) in selected else ""}>
                <span class="form-check-label">{h(f['name'])}</span>
            </label>'''
            for f in fees
        ) or '<span class="text-muted small">暂无可选项目</span>'
        blocks.append(f'<div class="mb-2"><div class="fw-semibold text-muted small mb-1">{label}</div>{checks}</div>')
    return ''.join(blocks)


def _preview_row(x):
    return f'''<tr><td><input type="checkbox" name="item_keys" value="{h(x['item_key'])}" {"checked" if x["can_generate"] else "disabled"}></td>
    <td>{h(x["tenant_name"])}</td><td>{h(x["room_name"])}</td><td>{h(x["fee_name"])}</td>
    <td>{h(x["service_start"])} 至 {h(x["service_end"])}</td><td>{h(x["due_date"])}</td>
    <td class="text-end">¥{m(x["amount"])}</td><td>{_row_status_text(x)}</td></tr>'''


def _row_status_text(x):
    if x['can_generate']:
        return '可生成'
    return '已存在<br><small class="text-muted">同房间、同收费项目、同服务期已存在账单</small>'


def _empty_preview_text(preview_status):
    if preview_status == 'can_generate':
        return '当前筛选条件下没有可生成账单，可切换到“全部”或“只看已存在”查看原因；检查租户合同开始/结束日期、缴费周期、收费项目是否适用。'
    return '未来指定天数内暂无需要生成的租户账单'


def _preview_summary(items):
    can_items = [x for x in items if x['can_generate']]
    return {
        'can': len(can_items),
        'existing': len(items) - len(can_items),
        'tenants': len({x.get('customer_name_snapshot') or x['tenant_name'] for x in can_items}),
        'rooms': len({x['room_id'] for x in can_items}),
        'amount': sum(float(x['amount'] or 0) for x in can_items),
    }



def _status_options(current):
    options = [('all', '全部'), ('can_generate', '只看可生成'), ('existing', '只看已存在')]
    return ''.join(f'<option value="{value}"{" selected" if current == value else ""}>{label}</option>' for value, label in options)


def _cycle_options(current):
    options = [
        ('tenant', '按租户资料周期'),
        ('monthly', '单月'),
        ('quarterly', '季度'),
        ('semiannual', '半年'),
        ('yearly', '一年'),
    ]
    return ''.join(f'<option value="{value}"{" selected" if current == value else ""}>{label}</option>' for value, label in options)


def _scope_options(current):
    return ''.join(
        f'<option value="{value}"{" selected" if current == value else ""}>{label}</option>'
        for value, label in SCOPE_OPTIONS
    )



def _no_can_alert(can_count):
    if can_count:
        return ''
    return '<div class="alert alert-secondary">当前筛选条件下没有可生成账单，可切换到“全部”或“只看已存在”查看原因；检查租户合同开始/结束日期、缴费周期、收费项目是否适用。</div>'


def _submit_button(can_count):
    if can_count:
        return '<button class="btn btn-success"><i class="bi bi-check2-circle"></i> 进入生成确认</button>'
    return '<button class="btn btn-secondary" disabled>暂无可生成账单</button>'
