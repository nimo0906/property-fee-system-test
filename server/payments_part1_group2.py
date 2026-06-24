from server.payments_shared import *
from server.money import money_float

class PaymentMixinPart1Group2(BaseHandler):
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
        rows = db.execute(f'''SELECT b.*,r.building,r.unit,r.room_number,s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,f.name ft,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE b.id IN ({placeholders}) AND b.status!='paid'
            ORDER BY COALESCE(r.building,'商场'),r.unit,COALESCE(r.room_number,s.space_no),b.fee_type_id''', ids).fetchall()
        if not rows:
            db.close()
            return self._redirect('/bills?flash=没有可收费的未缴账单')
        closed_periods = sorted({r['billing_period'] for r in rows if is_period_closed(r['billing_period'])})
        if closed_periods:
            db.close()
            return self._redirect('/bills?flash=' + ','.join(closed_periods) + '已结账，无法批量收费')

        method = qs(d, 'payment_method', 'transfer')
        operator = qs(d, 'operator') or _current_operator_name(self)
        total = sum(max(0, money_float(r['amount']) - money_float(r['paid'])) for r in rows)
        selected_ids = ','.join(str(r['id']) for r in rows)
        if qs(d, 'confirm') != '1':
            db.close()
            detail_rows = ''.join(
                f'<tr><td>{h(r["bill_number"] or r["id"])}</td><td>{h(_bill_target_label(r))}</td>'
                f'<td>{h(r["ft"] or "-")}</td><td>{h(r["billing_period"])}</td>'
                f'<td class="text-end"><span class="money">¥{m(r["amount"])}</span></td><td class="text-end"><span class="money money-paid">¥{m(r["paid"])}</span></td>'
                f'<td class="text-end"><span class="money money-due">¥{m(money_float(r["amount"])-money_float(r["paid"]))}</span></td></tr>'
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
            rem = money_float(b['amount']) - money_float(b['paid'])
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
