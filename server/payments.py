#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment processing, records, and quick billing."""

from server.db import get_db, get_period, calc_bill_late_fee, is_period_closed, h, m, qs, date_to_period, period_to_date, add_months
from server.billing_periods import append_period_filter
from server.base import BaseHandler
from datetime import datetime, date, timedelta
import urllib.parse, csv, io, re
from server.billing_engine import calculate_bill_amount, fee_applies_to_category, fee_applies_to_room
from server.print_helper import print_page
from server.backups import create_db_backup
from server.services import Actor, PaymentService, ServiceError


def _calc_month_count(start_str, end_str):
    """计算日期区间包含的月数。按天数÷30四舍五入。
    eg: 2026-01-28 ~ 2026-05-28 = 120天÷30 = 4个月
        2026-01-01 ~ 2026-12-31 = 364天÷30 ≈ 12个月
    """
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        ed = datetime.strptime(end_str, '%Y-%m-%d').date()
    except:
        return 1
    if ed <= sd:
        return 1
    if sd.day == 1 and ed.day == 1:
        return max(1, (ed.year - sd.year) * 12 + ed.month - sd.month + 1)
    days = (ed - sd).days
    return max(1, (days + 15) // 30)


def _period_label(start_str, end_str):
    """生成账期标签。单月: 2026-06, 多月: 2026-05~2026-08"""
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        ed = datetime.strptime(end_str, '%Y-%m-%d').date()
        if sd.year == ed.year and sd.month == ed.month:
            return f"{sd.year}-{sd.month:02d}"
        return f"{sd.year}-{sd.month:02d}~{ed.year}-{ed.month:02d}"
    except:
        return get_period()


def _cycle_month_count(cycle):
    return {'monthly': 1, 'quarterly': 3, 'semiannual': 6}.get(str(cycle or '').strip(), 0)


def _is_mall_commercial_room(room):
    try:
        return room['unit'] == '商场' and room['category'] in ('商户', '商业')
    except Exception:
        return False


def _room_billing_months(room, fallback_months):
    try:
        cycle = room['payment_cycle'] if 'payment_cycle' in room.keys() else ''
    except Exception:
        cycle = ''
    if _is_mall_commercial_room(room):
        cycle_months = _cycle_month_count(cycle)
        return cycle_months if cycle_months > 1 else max(1, int(fallback_months or 1))
    return max(1, int(fallback_months or 1))


def _cycle_period_label(start_str, months):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
    except Exception:
        return get_period()
    months = max(1, int(months or 1))
    if months == 1:
        return f"{sd.year}-{sd.month:02d}"
    ed = add_months(sd.replace(day=1), months - 1)
    return f"{sd.year}-{sd.month:02d}~{ed.year}-{ed.month:02d}"


def _cycle_due_date(start_str, months, fallback_end):
    try:
        sd = datetime.strptime(start_str, '%Y-%m-%d').date()
        return (add_months(sd, max(1, int(months or 1))) - timedelta(days=1)).isoformat()
    except Exception:
        return fallback_end


def _extract_ids(data, key):
    raw = data.get(key, []) if data else []
    if isinstance(raw, str):
        raw = [raw]
    ids = []
    for item in raw:
        for part in str(item).split(','):
            cleaned = part.strip().strip('[]').strip().strip("'\"")
            if cleaned.isdigit():
                ids.append(cleaned)
    return ids


class PaymentMixin(BaseHandler):

    def _billing_calc(self, d):
        rid = qs(d, 'room_id')
        extra_raw = d.get('extra_room_ids', [])
        if isinstance(extra_raw, str):
            extra_raw = [extra_raw] if extra_raw else []
        all_rids = [rid] + [x for x in extra_raw if x and x != rid]
        all_rids = [x for x in all_rids if x]
        raw = d.get('fee_types', [])
        if isinstance(raw, list):
            raw_items = raw
        else:
            raw_items = raw.split(',')
        ft_ids = []
        for item in raw_items:
            text = str(item)
            if text.strip().isdigit():
                ft_ids.append(text.strip())
            else:
                ft_ids.extend(re.findall(r'\d+', text))
        if not all_rids or not ft_ids:
            return self._redirect('/billing?flash=请选择房间和费用')
        period_start = qs(d, 'period_start', '')
        period_end = qs(d, 'period_end', '')
        if not period_start or not period_end:
            return self._redirect('/billing?flash=请选择出账日期区间')
        months = _calc_month_count(period_start, period_end)
        period_label = _period_label(period_start, period_end)
        db = get_db()
        if is_period_closed(period_label):
            db.close()
            return self._redirect('/billing?flash=' + period_label + '已结账，无法生成新账单')
        due_date = period_end
        total_g = 0
        skipped_existing = 0
        room_names = []
        display_period = period_label
        for rid in all_rids:
            rm = db.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
            if not rm:
                continue
            bill_months = _room_billing_months(rm, months)
            bill_period_label = _cycle_period_label(period_start, bill_months) if _is_mall_commercial_room(rm) else period_label
            bill_due_date = _cycle_due_date(period_start, bill_months, period_end) if _is_mall_commercial_room(rm) else due_date
            display_period = bill_period_label
            room_names.append(rm['building'] + '-' + rm['room_number'])
            for fid in ft_ids:
                try:
                    fid = int(str(fid).strip())
                except ValueError:
                    continue
                if rid != all_rids[0] and d.get(f'er_opt_{rid}_{fid}') is None:
                    continue
                ft = db.execute("SELECT * FROM fee_types WHERE id=? AND is_active=1", (fid,)).fetchone()
                if not ft or (ft['name'] or '').strip().lower().startswith('test'):
                    continue
                if not fee_applies_to_room(ft['name'] or '', rm):
                    continue
                exists = db.execute(
                    "SELECT id FROM bills WHERE room_id=? AND fee_type_id=? AND billing_period=?",
                    (rid, fid, bill_period_label)
                ).fetchone()
                if exists:
                    skipped_existing += 1
                    continue
                custom_key = f'custom_amount_{fid}'
                custom_val = d.get(custom_key, [''])[0] if isinstance(d.get(custom_key), list) else d.get(custom_key, '')
                calc = calculate_bill_amount(db, rm, ft, bill_period_label, bill_months, custom_val)
                amt = calc['amount']
                if amt <= 0:
                    continue
                on = db.execute("SELECT name FROM owners WHERE id=?", (rm['owner_id'],)).fetchone()
                oname = (on[0] if on else '未知')[:10]
                rshort = rm['building'] + '-' + rm['room_number']
                seq = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period=?", (bill_period_label,)).fetchone()[0] + total_g + 1
                bn = f"{rshort}_{oname}_{bill_period_label.replace('~','-')}_{seq:04d}"
                db.execute(
                    "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end) VALUES(?,?,?,?,?,?,'unpaid',?,?,?)",
                    (rid, rm['owner_id'], fid, bill_period_label, amt, bill_due_date, bn, period_start, bill_due_date)
                )
                total_g += 1
        db.commit()
        db.close()
        rooms_str = ','.join(room_names)
        target = f'/bills?period={urllib.parse.quote(display_period)}'
        if total_g == 0 and skipped_existing:
            msg = f'{rooms_str}所选费用在{display_period}已存在账单，未重复生成；已为您显示该房间全部状态账单'
        else:
            msg = f'为{rooms_str}共生成{total_g}笔账单'
        self._redirect(target, msg)

    def _bill_pay(self, bid):
        db=get_db()
        b=db.execute('''SELECT b.*,r.building,r.unit,r.room_number,f.name ft,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE b.id=?''',(bid,)).fetchone()
        if not b:return self._error(404)
        db.close();rem=b['amount']-b['paid']
        self._html(self._page('缴费',f'''
<div class="row g-4"><div class="col-md-5"><div class="card"><div class="card-header">账单信息</div>
<div class="card-body"><table class="table table-borderless mb-0">
<tr><td class="text-muted">房间</td><td>{h(b["building"])}-{h(b["unit"])}-{h(b["room_number"])}</td></tr>
<tr><td class="text-muted">费用</td><td><span class="badge bg-info">{h(b["ft"])}</span></td></tr>
<tr><td class="text-muted">账期</td><td>{h(b["billing_period"])}</td></tr>
<tr><td class="text-muted">编号</td><td><small>{h(b["bill_number"]or"-")}</small></td></tr></table><hr>
<p class="text-center mb-0"><small>应缴</small><h2 class="text-primary text-center">¥{m(b["amount"])}</h2>
{"<small>还需: ¥"+m(rem)+"</small>" if b["paid"]>0 else ""}</p></div></div></div>
<div class="col-md-7"><div class="card"><div class="card-header">录入缴费</div>
<div class="card-body"><form method=POST action="/bills/{bid}/pay" class="row g-3">
<div class="col-md-6"><label>缴费金额 *</label><div class="input-group"><span class="input-group-text">¥</span>
<input name="amount_paid" type="number" class="form-control form-control-lg" value="{m(rem)}" step="0.01" required></div></div>
<div class="col-md-6"><label>支付方式</label><select name="payment_method" class="form-select form-control-lg">
<option value="cash">现金</option><option value="transfer">转账</option><option value="wechat">微信</option><option value="alipay">支付宝</option></select></div>
<div class="col-md-6"><label>收费员</label><input name="operator" class="form-control" value="管理员"></div>
<div class="col-md-6"><label>备注</label><input name="notes" class="form-control"></div>
<div class="col-12"><hr><button class="btn btn-success btn-lg"><i class="bi bi-credit-card"></i> 确认缴费</button>
<a href="/bills/{bid}" class="btn btn-outline-secondary">取消</a></div></form></div></div></div></div>''','bills'))

    def _bill_pay_post(self, bid, d):
        db=get_db()
        amt=float(qs(d,'amount_paid',0))
        if amt<=0:db.close();return self._redirect(f'/bills/{bid}/pay?flash=金额必须大于0')
        bill=db.execute("SELECT amount,billing_period,COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=bills.id),0) paid FROM bills WHERE id=?",(bid,)).fetchone()
        if not bill:db.close();return self._error(404)
        if is_period_closed(bill['billing_period']):
            db.close();return self._redirect(f'/bills/{bid}?flash={bill["billing_period"]}已结账，无法收费')
        rem=float(bill['amount'] or 0)-float(bill['paid'] or 0)
        if amt-rem>0.001:
            db.close();return self._redirect(f'/bills/{bid}/pay?flash=缴费金额不能超过待缴金额¥{m(rem)}')
        create_db_backup('auto_before_payment')
        receipt_no = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}{bid}"
        db.close()
        try:
            PaymentService().create_payment({
                'bill_id': bid,
                'amount': str(amt),
                'method': qs(d,'payment_method','cash'),
                'notes': qs(d,'notes'),
                'receipt_number': receipt_no,
            }, Actor(username=qs(d,'operator','管理员'), role='operator'))
        except ServiceError as exc:
            return self._redirect(f'/bills/{bid}/pay?flash={urllib.parse.quote(str(exc))}')
        self._audit('payment_create', 'bill', bid, {'remaining': rem}, {'amount_paid': amt, 'receipt_number': receipt_no}, qs(d,'notes'))
        self._redirect(f'/bills/{bid}?flash=缴费成功 ¥{m(amt)}')

    def _batch_pay(self, d):
        raw = d.get('bill_ids', [])
        if isinstance(raw, str):
            raw = [raw]
        expanded = []
        for item in raw:
            expanded.extend(str(item).split(','))
        ids = []
        for x in expanded:
            cleaned = str(x).strip().strip('[]').strip().strip("'\"")
            if cleaned.isdigit():
                ids.append(cleaned)
        if not ids:
            return self._redirect('/bills?flash=请勾选账单')

        placeholders = ','.join('?' * len(ids))
        db = get_db()
        rows = db.execute(f'''SELECT b.*,r.building,r.unit,r.room_number,f.name ft,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.id IN ({placeholders}) AND b.status!='paid'
            ORDER BY r.building,r.unit,r.room_number,b.fee_type_id''', ids).fetchall()
        if not rows:
            db.close()
            return self._redirect('/bills?flash=没有可收费的未缴账单')
        closed_periods = sorted({r['billing_period'] for r in rows if is_period_closed(r['billing_period'])})
        if closed_periods:
            db.close()
            return self._redirect('/bills?flash=' + ','.join(closed_periods) + '已结账，无法批量收费')

        method = qs(d, 'payment_method', 'transfer')
        operator = qs(d, 'operator', '批量缴费')
        total = sum(max(0, float(r['amount'] or 0) - float(r['paid'] or 0)) for r in rows)
        selected_ids = ','.join(str(r['id']) for r in rows)
        if qs(d, 'confirm') != '1':
            db.close()
            detail_rows = ''.join(
                f'<tr><td>{h(r["bill_number"] or r["id"])}</td><td>{h(r["building"])}-{h(r["unit"])}-{h(r["room_number"])}</td>'
                f'<td>{h(r["ft"] or "-")}</td><td>{h(r["billing_period"])}</td>'
                f'<td class="text-end"><span class="money">¥{m(r["amount"])}</span></td><td class="text-end"><span class="money money-paid">¥{m(r["paid"])}</span></td>'
                f'<td class="text-end"><span class="money money-due">¥{m(float(r["amount"] or 0)-float(r["paid"] or 0))}</span></td></tr>'
                for r in rows
            )
            return self._html(self._page('批量收费确认', f'''
            <div class="alert alert-warning"><strong>批量收费确认</strong>：请核对账单和金额，确认后将按欠费金额一次性收款。</div>
            <div class="row text-center g-2 mb-3"><div class="col-md-6"><div class="finance-summary"><div class="text-muted small">账单数量</div><strong>{len(rows)}</strong></div></div>
            <div class="col-md-6"><div class="finance-summary"><div class="text-muted small">本次收款合计</div><strong class="money money-paid">¥{m(total)}</strong></div></div></div>
            <div class="card billing-ledger"><div class="card-header">待收费账单</div><div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>编号</th><th>房间</th><th>收费项目</th><th>账期</th><th class="text-end">应收</th><th class="text-end">已收</th><th class="text-end">本次收款</th></tr></thead><tbody>{detail_rows}</tbody></table></div></div>
            <form method="POST" action="/bills/batch_pay" class="row g-3 mt-2">
            <input type="hidden" name="confirm" value="1"><input type="hidden" name="bill_ids" value="{h(selected_ids)}">
            <div class="col-md-4"><label>支付方式</label><select name="payment_method" class="form-select"><option value="transfer">转账</option><option value="wechat">微信</option><option value="alipay">支付宝</option><option value="cash">现金</option></select></div>
            <div class="col-md-4"><label>收费员</label><input name="operator" class="form-control" value="{h(operator)}"></div>
            <div class="col-md-4 d-flex align-items-end"><button class="btn btn-success">确认收款</button><a href="/bills" class="btn btn-outline-secondary ms-2">取消</a></div>
            </form>
            ''', 'bills'))

        backup_name = create_db_backup('auto_before_batch_payment')
        paid_ids = []
        cnt = 0
        service_rows = [dict(r) for r in rows]
        db.close()
        for b in service_rows:
            rem = float(b['amount'] or 0) - float(b['paid'] or 0)
            if rem <= 0:
                continue
            receipt_no = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}{b['id']}"
            try:
                PaymentService().create_payment({
                    'bill_id': b['id'],
                    'amount': str(rem),
                    'method': method,
                    'receipt_number': receipt_no,
                }, Actor(username=operator, role='operator'))
            except ServiceError:
                continue
            paid_ids.append(str(b['id']))
            cnt += 1
        self._audit('batch_payment_create', 'bill', None, None, {'bill_ids': paid_ids, 'total': total}, '批量收费')
        receipt_ids = ','.join(paid_ids)
        receipt_form = ''
        if receipt_ids:
            receipt_form = f'''<form method="POST" action="/bills/receipt_by_ids" target="_blank" class="d-inline">
            <input type="hidden" name="bill_ids" value="{h(receipt_ids)}"><button class="btn btn-outline-secondary">打印本次收据</button></form>'''
        self._html(self._page('批量收费结果', f'''
        <div class="alert alert-success"><strong>批量收费结果</strong>：成功收费 {cnt} 笔。</div>
        <div class="alert alert-light border"><strong>自动备份：</strong><code>{h(backup_name)}</code></div>
        <div class="row text-center g-2 mb-3"><div class="col-md-6"><div class="finance-summary"><div class="text-muted small">成功收费</div><strong>{cnt}</strong></div></div>
        <div class="col-md-6"><div class="finance-summary"><div class="text-muted small">收款合计</div><strong class="money money-paid">¥{m(total)}</strong></div></div></div>
        <div class="export-actions">{receipt_form}<a class="btn btn-primary" href="/payments">查看缴费记录</a><a class="btn btn-outline-secondary" href="/bills">返回账单</a></div>
        ''', 'bills'))

    # ── 缴费记录 ──────────────────────────────────────────────
    def _payments(self, q):
        db=get_db();p=date_to_period(qs(q,'period',get_period()));pm=qs(q,'method','');op=qs(q,'operator','')
        sql='''SELECT p.*,b.bill_number,b.billing_period,b.amount,b.room_id,b.fee_type_id,
            r.building,r.unit,r.room_number,o.name owner_name,f.name ft
            FROM payments p JOIN bills b ON p.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE 1=1'''
        vals=[]
        if p:
            sql, vals = append_period_filter(sql, vals, p, 'b.billing_period')
        if pm:sql+=" AND p.payment_method=?";vals.append(pm)
        if op:sql+=" AND p.operator LIKE ?";vals.append(f'%{op}%')
        sql+=" ORDER BY p.payment_date DESC"
        rows=db.execute(sql,vals).fetchall()
        db.close()
        tc=sum(r['amount_paid'] for r in rows)
        groups = []
        by_room = {}
        for r in rows:
            key = r['room_id'] or 0
            if key not in by_room:
                by_room[key] = {'room_id': key, 'room': f'{r["building"] or ""}-{r["unit"] or ""}-{r["room_number"] or ""}',
                                'owner': r['owner_name'] or '未知', 'rows': [], 'total': 0}
                groups.append(by_room[key])
            by_room[key]['rows'].append(r)
            by_room[key]['total'] += float(r['amount_paid'] or 0)
        rh_parts = []
        for idx, g in enumerate(groups, 1):
            safe_id = str(g['room_id']).replace('-', '_') + '_' + str(idx)
            latest = g['rows'][0]['payment_date'] if g['rows'] else ''
            periods = sorted({x['billing_period'] for x in g['rows'] if x['billing_period']})
            period_text = periods[0] if len(periods) == 1 else (periods[0] + ' ~ ' + periods[-1] if periods else '-')
            methods = '、'.join(sorted({x['payment_method'] for x in g['rows'] if x['payment_method']})) or '-'
            rh_parts.append(f'''<tr class="table-light payment-group" style="cursor:pointer" onclick="togglePaymentGroup('{safe_id}')">
<td><input type="checkbox" class="payment-group-chk" data-payment-group="{safe_id}" onclick="event.stopPropagation();togglePaymentSelection('{safe_id}',this.checked)"></td>
<td><i class="bi bi-chevron-right" id="pay_icon_{safe_id}"></i> <strong>{h(g['room'])}</strong><br><small class="text-muted">{h(g['owner'])}</small></td>
<td><span class="badge status-neutral">汇总</span></td>
<td>{h(period_text)}</td><td><span class="badge status-neutral">{len(g['rows'])}笔</span></td>
<td class="text-end"><strong class="money money-paid">+¥{m(g['total'])}</strong></td>
<td>{h(methods)}</td><td colspan="2"><small class="text-muted">最近：{h(latest or '-')}</small></td></tr>''')
            for r in g['rows']:
                rh_parts.append(f'''<tr class="payment-detail-{safe_id}" style="display:none"><td><input form="paymentActionForm" type="checkbox" name="payment_ids" data-payment-group="{safe_id}" value="{r['id']}"></td><td><small>{h(r["payment_date"]or"-")}</small></td>
<td><small>{h(r["bill_number"]or"-")}</small></td>
<td>{h(r["building"]or"")}-{h(r["unit"]or"")}-{h(r["room_number"]or"")}</td>
<td><span class="badge status-info">{h(r["ft"])}</span></td><td>{h(r["billing_period"])}</td>
<td class="text-end"><span class="money money-paid">+¥{m(r["amount_paid"])}</span></td>
<td>{h(r["payment_method"])}</td><td>{h(r["operator"]or"-")}</td><td><small>{h(r["receipt_number"] or "-")}</small></td></tr>''')
        rh=''.join(rh_parts)
        tpl=self._load_template('payments.html')
        tpl=tpl.replace('{PERIOD}',period_to_date(p)).replace('{OP}',h(op)).replace('{TOTAL}',m(tc))
        tpl=tpl.replace('{SC}',' selected' if pm=='cash' else '').replace('{ST}',' selected' if pm=='transfer' else '')
        tpl=tpl.replace('{SW}',' selected' if pm=='wechat' else '').replace('{SA}',' selected' if pm=='alipay' else '')
        tpl=tpl.replace('<th>经手人</th>', '<th>经手人</th><th>收据号</th>')
        tpl=tpl.replace('{ROWS}',rh or '<tr><td colspan="10" class="text-center text-muted py-4">暂无缴费记录</td></tr>')
        tpl += '''<script>
function togglePaymentGroup(id){var rows=document.querySelectorAll('.payment-detail-'+id);var icon=document.getElementById('pay_icon_'+id);rows.forEach(function(r){r.style.display=r.style.display==='none'?'':'none';});if(icon) icon.className=icon.className==='bi bi-chevron-right'?'bi bi-chevron-down':'bi bi-chevron-right';}
function togglePaymentSelection(id,checked){document.querySelectorAll('input[name="payment_ids"][data-payment-group="'+id+'"]').forEach(function(x){x.checked=checked;});}
function toggleAllPayments(checked){document.querySelectorAll('input[name="payment_ids"],.payment-group-chk').forEach(function(x){x.checked=checked;});}
</script>'''
        self._html(self._page('缴费记录',tpl,'payments'))


    def _payments_print(self, d):
        ids = _extract_ids(d, 'payment_ids')
        if not ids:
            return self._redirect('/payments?flash=请勾选缴费记录')
        rows = self._selected_payment_rows(ids)
        if not rows:
            return self._redirect('/payments?flash=未找到缴费记录')
        detail = ''.join(f'''<tr><td>{h(r["payment_date"] or "-")}</td><td>{h(r["bill_number"] or "-")}</td>
            <td>{h(r["building"] or "")}-{h(r["unit"] or "")}-{h(r["room_number"] or "")}</td>
            <td>{h(r["owner_name"] or "-")}</td><td>{h(r["ft"] or "-")}</td><td>{h(r["billing_period"] or "-")}</td>
            <td class="amt">{m(r["amount_paid"])}</td><td>{h(r["payment_method"] or "-")}</td><td>{h(r["operator"] or "-")}</td></tr>'''
            for r in rows)
        total = sum(float(r['amount_paid'] or 0) for r in rows)
        content = f'''<h1>缴费记录打印</h1><table class="detail"><thead><tr>
            <th>时间</th><th>票据</th><th>房间</th><th>客户</th><th>项目</th><th>账期</th>
            <th class="amt">金额</th><th>方式</th><th>经手人</th></tr></thead>
            <tbody>{detail}</tbody><tfoot><tr class="total-row"><td colspan="6">合计</td>
            <td class="amt">{m(total)}</td><td colspan="2"></td></tr></tfoot></table>'''
        self._html(print_page('缴费记录打印', content, back_url='/payments'))

    def _payment_receipts(self, d):
        ids = _extract_ids(d, 'payment_ids')
        if not ids:
            return self._redirect('/payments?flash=请勾选缴费记录')
        rows = self._selected_payment_rows(ids)
        bill_ids = ','.join(str(r['bill_id']) for r in rows if r['bill_id'])
        if not bill_ids:
            return self._redirect('/payments?flash=未找到可打印收据的账单')
        return self._receipt_by_ids({'bill_ids': bill_ids, 'back': '/bills'})

    def _selected_payment_rows(self, ids):
        placeholders = ','.join('?' * len(ids))
        db = get_db()
        rows = db.execute(f'''SELECT p.*,b.bill_number,b.billing_period,
            r.building,r.unit,r.room_number,o.name owner_name,f.name ft
            FROM payments p JOIN bills b ON p.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE p.id IN ({placeholders}) ORDER BY p.payment_date DESC,p.id DESC''', ids).fetchall()
        db.close()
        return rows


    def _payments_csv(self, q):
        p = date_to_period(qs(q, 'period', get_period()))
        pm = qs(q, 'method', '')
        op = qs(q, 'operator', '')
        sql = """SELECT p.*,b.bill_number,b.billing_period,b.amount,b.room_id,b.fee_type_id,
            r.building,r.unit,r.room_number,o.name owner_name,f.name ft
            FROM payments p JOIN bills b ON p.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE 1=1"""
        vals = []
        if p:
            sql, vals = append_period_filter(sql, vals, p, 'b.billing_period')
        if pm:
            sql += " AND p.payment_method=?"; vals.append(pm)
        if op:
            sql += " AND p.operator LIKE ?"; vals.append(f'%{op}%')
        sql += " ORDER BY p.payment_date DESC"
        db = get_db(); rows = db.execute(sql, vals).fetchall(); db.close()
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(['payment_date','receipt_number','bill_number','building','unit','room_number','owner','fee_type','billing_period','amount_paid','payment_method','operator','notes'])
        for r in rows:
            w.writerow([r['payment_date'] or '', r['receipt_number'] or '', r['bill_number'] or '', r['building'] or '', r['unit'] or '', r['room_number'] or '', r['owner_name'] or '', r['ft'] or '', r['billing_period'] or '', m(r['amount_paid']), r['payment_method'] or '', r['operator'] or '', r['notes'] or ''])
        data = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename=payments_{p}.csv')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

    # ── API ──────────────────────────────────────────────────
    def _api_owner_info(self, oid):
        db=get_db()
        o=db.execute("SELECT name,phone FROM owners WHERE id=?",(oid,)).fetchone()
        db.close()
        self._json({'name':o[0] if o else '','phone':o[1] if o else ''} if o else {})
