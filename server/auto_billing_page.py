#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto billing page rendering helpers."""

from server.auto_billing_runs import run_row_html
from server.db import h, m


def render_auto_billing_page(advance_days, fee_options, selected_fee_ids, items, runs, preview_status='all'):
    fee_checks = ''.join(
        f'''<label class="form-check form-check-inline mb-2">
            <input class="form-check-input" type="checkbox" name="fee_ids" value="{f['id']}"
                {"checked" if int(f['id']) in selected_fee_ids else ""}>
            <span class="form-check-label">{h(f['name'])}</span>
        </label>'''
        for f in fee_options
    )
    hidden_fee_ids = ''.join(f'<input type="hidden" name="fee_ids" value="{fid}">' for fid in selected_fee_ids)
    status_opts = _status_options(preview_status)
    rows = ''.join(_preview_row(x) for x in items) or _empty_preview_row()
    run_rows = ''.join(run_row_html(r) for r in runs) or '<tr><td colspan="7" class="text-center text-muted py-3">暂无自动出账记录</td></tr>'
    summary = _preview_summary(items)
    return f'''
    <div class="alert alert-info">
      <div><strong>自动出账规则：</strong>按租户合同开始日、结束日、缴费周期计算下一期账单。</div>
      <div>提前 {advance_days} 天只是筛选即将到期的下一期；已存在账单不会重复生成；生成后按缴费截止日进入催缴管理。</div>
    </div>
    <form method="GET" action="/auto_billing" class="row g-2 mb-3">
      <div class="col-auto"><label class="col-form-label">提前出账天数</label></div>
      <div class="col-auto"><input type="number" class="form-control" name="advance_days" min="0" max="365" value="{advance_days}"></div>
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
    <form method="POST" action="/auto_billing/confirm">
      <input type="hidden" name="advance_days" value="{advance_days}"><input type="hidden" name="preview_status" value="{h(preview_status)}">{hidden_fee_ids}
      <div class="table-responsive"><table class="table table-hover align-middle small">
      <thead><tr><th>选择</th><th>租户</th><th>房间/铺位</th><th>收费项目</th><th>服务期</th><th>缴费截止日</th><th class="text-end">金额</th><th>状态</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
      <button class="btn btn-success"><i class="bi bi-check2-circle"></i> 进入生成确认</button>
    </form>
    <div class="card mt-3"><div class="card-header">最近自动出账记录</div>
    <div class="table-responsive"><table class="table table-hover align-middle small mb-0">
    <thead><tr><th>批次号</th><th>生成时间</th><th>操作人</th><th class="text-end">笔数</th><th>服务期范围</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>{run_rows}</tbody></table></div></div>'''


def _preview_row(x):
    return f'''<tr><td><input type="checkbox" name="item_keys" value="{h(x['item_key'])}" {"checked" if x["can_generate"] else "disabled"}></td>
    <td>{h(x["tenant_name"])}</td><td>{h(x["room_name"])}</td><td>{h(x["fee_name"])}</td>
    <td>{h(x["service_start"])} 至 {h(x["service_end"])}</td><td>{h(x["due_date"])}</td>
    <td class="text-end">¥{m(x["amount"])}</td><td>{"可生成" if x["can_generate"] else "已存在"}</td></tr>'''


def _empty_preview_row():
    return '<tr><td colspan="8" class="text-center text-muted py-4">未来指定天数内暂无需要生成的租户账单</td></tr>'


def _preview_summary(items):
    can_items = [x for x in items if x['can_generate']]
    return {
        'can': len(can_items),
        'existing': len(items) - len(can_items),
        'tenants': len({x['tenant_name'] for x in can_items}),
        'rooms': len({x['room_id'] for x in can_items}),
        'amount': sum(float(x['amount'] or 0) for x in can_items),
    }



def _status_options(current):
    options = [('all', '全部'), ('can_generate', '只看可生成'), ('existing', '只看已存在')]
    return ''.join(f'<option value="{value}"{" selected" if current == value else ""}>{label}</option>' for value, label in options)
