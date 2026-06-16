#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial contract receivable preview and confirmation."""

import ast
from datetime import date, datetime, timedelta
from server.base import BaseHandler
from server.backups import create_db_backup
from server.bill_snapshots import contract_snapshot, apply_snapshot
from server.contract_billing import get_contract_fee_type_id, _cycle_months, _period_label
from server.data_health import cleanup_invalid_payments
from server.db import add_months, get_db, h, m, qs
from server.contract_amendments import amount_for_period
from server.billing_proration import is_one_time_fee, prorated_month_factor
from server.billing_rules import fee_in_scope


def _as_date(value):
    if isinstance(value, date): return value
    return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()


def _next_start(db, contract_id, contract_start, fee_type_id, cycle, current=None):
    row = db.execute("""SELECT MAX(service_end) last_end FROM bills
        WHERE source='merchant_contract' AND source_ref=? AND fee_type_id=?""", (str(contract_id), fee_type_id)).fetchone()
    if row and row['last_end']:
        return _as_date(row['last_end']) + timedelta(days=1)
    start = _as_date(contract_start)
    current = _as_date(current or start)
    if start < current:
        start = current
    return start


def _contract_rows(db, keyword=''):
    rows = db.execute("""SELECT c.*,COALESCE(NULLIF(c.contract_area,0),s.area,r.area,0) area,
        COALESCE(s.space_no,r.room_number,'') object_no,COALESCE(s.shop_name,c.shop_name,r.shop_name,'') object_name
        FROM merchant_contracts c LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
        LEFT JOIN rooms r ON c.room_id=r.id WHERE c.status='active' ORDER BY c.end_date,c.id""").fetchall()
    if not keyword: return rows
    kw = keyword.lower()
    return [r for r in rows if kw in ' '.join(str(r[x] or '') for x in r.keys()).lower()]


def build_receivable_preview(today=None, advance_days=30, keyword='', status='all'):
    current = _as_date(today or date.today())
    cutoff = current + timedelta(days=int(advance_days or 30))
    db = get_db(); items = []
    rent_fee = get_contract_fee_type_id(db, '合同租金')
    prop_fee = get_contract_fee_type_id(db, '合同物业费')
    commercial_fees = [dict(r) for r in db.execute(
        "SELECT * FROM fee_types WHERE is_active=1 ORDER BY sort_order,id"
    ).fetchall() if fee_in_scope(r, 'commercial')]
    for c in _contract_rows(db, keyword):
        end = _as_date(c['end_date'])
        for kind, label, fee_id, cycle, base_amount in [
            ('rent', '合同租金', rent_fee, c['rent_cycle'], float(c['rent_amount'] or 0)),
            ('property', '合同物业费', prop_fee, c['property_cycle'], float(c['area'] or 0) * float(c['property_rate'] or 0)),
        ]:
            if kind == 'rent':
                from server.special_rent import special_rule_for
                if special_rule_for(db, c['id']):
                    continue
            start = _next_start(db, c['id'], c['start_date'], fee_id, cycle, current)
            months = _cycle_months(cycle)
            service_end = min(add_months(start, months) - timedelta(days=1), end)
            if start > cutoff or start > end: continue
            exists = db.execute("""SELECT id FROM bills WHERE source='merchant_contract' AND source_ref=?
                AND fee_type_id=? AND service_start=? AND service_end=?""",
                (str(c['id']), fee_id, start.isoformat(), service_end.isoformat())).fetchone()
            amount = amount_for_period(db, c, kind, start, service_end)
            item_status = '已存在' if exists else '可生成'
            if status == 'can_generate' and exists: continue
            if status == 'existing' and not exists: continue
            items.append({'item_key': f"{c['id']}:{kind}:{start}:{service_end}", 'contract_id': c['id'],
                'contract_no': c['contract_no'], 'merchant_name': c['merchant_name'], 'object_no': c['object_no'],
                'fee_id': fee_id, 'fee_name': label, 'service_start': start.isoformat(),
                'service_end': service_end.isoformat(), 'billing_period': _period_label(start, service_end),
                'due_date': service_end.isoformat(), 'amount': round(amount, 2), 'status': item_status,
                'default_checked': amount > 0})
        for fee in commercial_fees:
            start = _next_start(db, c['id'], c['start_date'], fee['id'], c['property_cycle'], current)
            months = _cycle_months(c['property_cycle'])
            service_end = min(add_months(start, months) - timedelta(days=1), end)
            if start > cutoff or start > end: continue
            exists = db.execute("""SELECT id FROM bills WHERE source='merchant_contract' AND source_ref=?
                AND fee_type_id=? AND service_start=? AND service_end=?""",
                (str(c['id']), fee['id'], start.isoformat(), service_end.isoformat())).fetchone()
            amount = _commercial_fee_amount(db, c, fee, start, service_end, months)
            item_status = '已存在' if exists else '可生成'
            if status == 'can_generate' and exists: continue
            if status == 'existing' and not exists: continue
            default_checked = (not is_one_time_fee(fee)) and amount > 0
            items.append({'item_key': f"{c['id']}:commercial:{fee['id']}:{start}:{service_end}",
                'contract_id': c['id'], 'contract_no': c['contract_no'], 'merchant_name': c['merchant_name'],
                'object_no': c['object_no'], 'fee_id': fee['id'], 'fee_name': fee['name'],
                'service_start': start.isoformat(), 'service_end': service_end.isoformat(),
                'billing_period': _period_label(start, service_end), 'due_date': service_end.isoformat(),
                'amount': round(amount, 2), 'status': item_status, 'default_checked': default_checked})
    db.close(); return items


def _commercial_fee_amount(db, contract, fee, start, service_end, months):
    name = fee['name'] or ''
    method = fee['calc_method'] or ''
    area = float(contract['area'] or 0)
    if name == '物业费(商业)':
        return amount_for_period(db, contract, 'property', start, service_end)
    if method == 'area':
        monthly = area * float(fee['unit_price'] or 0)
    elif method in ('fixed', 'household'):
        monthly = float(fee['unit_price'] or 0)
    else:
        monthly = 0.0
    factor = 1.0 if is_one_time_fee(fee) else (prorated_month_factor(start.isoformat(), service_end.isoformat()) or float(months or 1))
    return round(monthly * factor, 2)


def _normalize_keys(item_keys):
    if isinstance(item_keys, str):
        text = item_keys.strip()
        if text.startswith('[') and text.endswith(']'):
            try:
                parsed = ast.literal_eval(text)
                return [str(x) for x in parsed] if isinstance(parsed, list) else [text]
            except Exception:
                return [text]
        return [text]
    values = [str(x) for x in (item_keys or [])]
    if len(values) == 1 and values[0].strip().startswith('['):
        return _normalize_keys(values[0])
    return values


def _edited_item(item, form):
    key = item['item_key']
    edited = dict(item)
    edited['service_start'] = qs(form, f'service_start__{key}', item['service_start'])
    edited['service_end'] = qs(form, f'service_end__{key}', item['service_end'])
    edited['due_date'] = qs(form, f'due_date__{key}', item['due_date'])
    edited['billing_period'] = _period_label(_as_date(edited['service_start']), _as_date(edited['service_end']))
    amount = qs(form, f'amount__{key}', item['amount'])
    edited['amount'] = round(float(amount or 0), 2)
    return edited


def _bill_exists(db, item):
    return db.execute("""SELECT id FROM bills WHERE source='merchant_contract' AND source_ref=?
        AND fee_type_id=? AND service_start=? AND service_end=?""",
        (str(item['contract_id']), item['fee_id'], item['service_start'], item['service_end'])).fetchone()


def confirm_receivables(item_keys, today=None, advance_days=30, operator='管理员', form=None):
    db = get_db(); generated = 0
    cleanup_invalid_payments(db)
    preview = {x['item_key']: x for x in build_receivable_preview(today, advance_days, status='all')}
    first_keyword = ''
    for key in _normalize_keys(item_keys):
        item = preview.get(key)
        if not item or item['status'] != '可生成' or item['amount'] <= 0: continue
        item = _edited_item(item, form or {})
        if _as_date(item['service_end']) < _as_date(item['service_start']) or item['amount'] <= 0: continue
        if _bill_exists(db, item): continue
        c = db.execute("SELECT * FROM merchant_contracts WHERE id=?", (item['contract_id'],)).fetchone()
        bill_no = f"MCR-{item['contract_id']}-{item['fee_id']}-{item['service_start']}-{item['service_end']}"
        cur = db.execute("""INSERT INTO bills(room_id,commercial_space_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,notes,source,source_ref,service_start,service_end)
            VALUES(?,?,?,?,?,?,?,'unpaid',?,?,?,?,?,?)""",
            (c['room_id'], c['commercial_space_id'], c['owner_id'], item['fee_id'], item['billing_period'], item['amount'], item['due_date'], bill_no,
             f"商业合同应收人工核对后生成，操作员：{operator}", 'merchant_contract', str(item['contract_id']), item['service_start'], item['service_end']))
        apply_snapshot(db, cur.lastrowid, contract_snapshot(db, item['contract_id']))
        generated += 1
        if not first_keyword:
            first_keyword = item['contract_no'] or item['merchant_name'] or item['object_no']
    db.commit(); db.close(); return generated, first_keyword


class CommercialReceivableMixin(BaseHandler):
    def _commercial_receivables(self, q):
        today = qs(q, 'today') or date.today().isoformat(); adv = int(qs(q, 'advance_days', 30) or 30)
        kw = qs(q, 'keyword').strip(); st = qs(q, 'status') or 'all'
        items = build_receivable_preview(today, adv, kw, st)
        can_generate_count = sum(1 for x in items if x['status'] == '可生成')
        existing_count = sum(1 for x in items if x['status'] != '可生成')
        checked_count = sum(1 for x in items if x['status'] == '可生成' and x.get('default_checked'))
        checked_total = sum(float(x['amount'] or 0) for x in items if x['status'] == '可生成' and x.get('default_checked'))
        unchecked_count = sum(1 for x in items if x['status'] == '可生成' and not x.get('default_checked'))
        zero_count = sum(1 for x in items if x['status'] == '可生成' and float(x['amount'] or 0) <= 0)
        rows = ''.join(_row(x) for x in items) or '<tr><td colspan="9" class="text-center text-muted py-4">暂无商业合同应收提醒</td></tr>'
        self._html(self._page('商业合同应收', f'''<div class="d-flex justify-content-between align-items-center gap-2 flex-wrap mb-2"><div class="alert alert-info mb-0 flex-fill">商业合同应收：只显示当前日期以后、合同未到期的下一期待确认账单。</div><a class="btn btn-outline-secondary" href="/auto_billing"><i class="bi bi-arrow-left"></i> 返回</a></div>
        <form method="GET" class="row g-2 mb-3"><div class="col-auto"><label>当前日期</label><input name="today" type="date" class="form-control" value="{h(today)}"></div>
        <div class="col-auto"><label>提前天数</label><input name="advance_days" type="number" class="form-control" value="{adv}"></div>
        <div class="col-auto"><label>状态</label><select name="status" class="form-select"><option value="all">全部</option><option value="can_generate" {'selected' if st=='can_generate' else ''}>可生成</option><option value="existing" {'selected' if st=='existing' else ''}>已存在</option></select></div>
        <div class="col-auto"><label>关键字</label><input name="keyword" class="form-control" value="{h(kw)}"></div><div class="col-auto align-self-end"><button class="btn btn-primary">刷新</button></div></form>
        <form method="POST" action="/commercial_receivables/confirm"><input type="hidden" name="today" value="{h(today)}"><input type="hidden" name="advance_days" value="{adv}"><input type="hidden" name="confirm" value="1">
        <div class="alert alert-warning py-2"><strong>金额确认：</strong>请逐项核对金额、服务期和应收日期；保存后按修改后的内容写入账单。</div>
        <div class="row text-center g-2 mb-2">
        <div class="col-md-3"><div class="border rounded p-2"><div class="text-muted small">可生成项目</div><strong>{can_generate_count}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-2"><div class="text-muted small">默认勾选</div><strong>{checked_count}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-2"><div class="text-muted small">未自动勾选</div><strong>{unchecked_count}</strong></div></div>
        <div class="col-md-3"><div class="border rounded p-2"><div class="text-muted small">已存在/异常</div><strong>{existing_count + zero_count}</strong></div></div>
        </div>
        <div class="alert alert-light border py-2"><strong>生成前核对：</strong>一次性、临时类、金额为 0 或需人工确认的项目不会默认勾选；生成前请按实际发生勾选，避免自动多收或漏收。</div>
        <div class="alert alert-secondary py-2"><strong>本页已勾选：</strong><span id="selectedReceivableCount">{checked_count}</span> 项，合计 <span class="money" id="selectedReceivableTotal">¥{m(checked_total)}</span>。一次性/临时类默认不勾选，可按实际发生手动选择。</div>
        <div class="table-responsive"><table class="table table-hover align-middle small"><thead><tr><th>选择</th><th>合同</th><th>商户</th><th>对象</th><th>费用</th><th>服务期</th><th>应收日</th><th class="text-end">应收金额</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table></div>
        <button class="btn btn-primary">确认生成选中账单</button></form>
        <script>
        function updateReceivableSummary(){{
            var total=0,count=0;
            document.querySelectorAll('.receivable-check:checked').forEach(function(x){{ count++; total+=parseFloat(x.dataset.amount||'0')||0; }});
            var c=document.getElementById('selectedReceivableCount'); if(c)c.textContent=count;
            var t=document.getElementById('selectedReceivableTotal'); if(t)t.textContent='¥'+total.toFixed(2);
        }}
        document.querySelectorAll('.receivable-check').forEach(function(x){{x.addEventListener('change',updateReceivableSummary);}});
        </script>''', 'auto_billing'))

    def _commercial_receivables_confirm(self, d):
        keys = _normalize_keys(d.get('item_keys', []))
        if not keys: return self._redirect('/commercial_receivables?flash=请勾选应收项目')
        create_db_backup('auto_before_commercial_receivables')
        user = self._get_current_user() or {}
        count, keyword = confirm_receivables(keys, qs(d, 'today') or None, qs(d, 'advance_days', 30),
                                    user.get('display_name') or user.get('username') or '管理员', d)
        self._audit('commercial_receivables_confirm', 'bill', None, None, {'generated': count}, '商业合同应收确认')
        target = '/bills'
        if keyword:
            import urllib.parse
            target += '?' + urllib.parse.urlencode({'keyword': keyword})
        return self._redirect(target, flash=f'已生成{count}笔商业合同账单')


def _row(x):
    checked = 'checked' if x['status'] == '可生成' and x.get('default_checked') else ''
    if x['status'] != '可生成':
        checked = 'disabled'
    badge = 'status-success' if x['status'] == '可生成' else 'status-neutral'
    key = x['item_key']; disabled = '' if x['status'] == '可生成' else 'disabled'
    default_flag = '1' if x.get('default_checked') else '0'
    return f'''<tr><td><input type="checkbox" class="receivable-check" name="item_keys" value="{h(key)}" data-amount="{h(x['amount'])}" data-default-checked="{default_flag}" {checked}></td>
    <td>{h(x['contract_no'])}</td><td>{h(x['merchant_name'])}</td><td>{h(x['object_no'])}</td><td>{h(x['fee_name'])}</td>
    <td><div class="d-flex flex-column gap-1"><input type="date" class="form-control form-control-sm" name="service_start__{h(key)}" value="{h(x['service_start'])}" {disabled}>
    <input type="date" class="form-control form-control-sm" name="service_end__{h(key)}" value="{h(x['service_end'])}" {disabled}></div></td>
    <td><input type="date" class="form-control form-control-sm" name="due_date__{h(key)}" value="{h(x['due_date'])}" {disabled}></td>
    <td class="text-end"><input type="number" step="0.01" min="0" class="form-control form-control-sm text-end" name="amount__{h(key)}" value="{m(x['amount'])}" {disabled}></td>
    <td><span class="badge {badge}">{x['status']}</span></td></tr>'''
