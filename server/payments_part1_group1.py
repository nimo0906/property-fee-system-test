from server.payments_shared import *
from server.money import money_float
from server.bill_snapshots import room_snapshot, contract_snapshot, apply_snapshot
from server.data_health import cleanup_invalid_payments

class PaymentMixinPart1Group1(BaseHandler):
    def _billing_calc(self, d):
        rid = qs(d, 'room_id')
        contract_id = ''
        if str(rid).startswith('contract:'):
            contract_id = str(rid).split(':', 1)[1]
            rid = ''
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
        if not all_rids and not contract_id or not ft_ids:
            return self._redirect('/billing?flash=请选择房间和费用')
        period_start = qs(d, 'period_start', '')
        period_end = qs(d, 'period_end', '')
        if not period_start or not period_end:
            return self._redirect('/billing?flash=请选择出账日期区间')
        months = _calc_month_count(period_start, period_end)
        manual_factor = qs(d, 'proration_factor', '').strip()
        period_label = _period_label(period_start, period_end)
        db = get_db()
        if is_period_closed(period_label):
            db.close()
            return self._redirect('/billing?flash=' + period_label + '已结账，无法生成新账单')
        cleanup_invalid_payments(db)
        due_date = period_end
        total_g = 0
        skipped_existing = 0
        room_names = []
        display_period = period_label
        if contract_id:
            contract = db.execute(
                """SELECT c.*,COALESCE(s.space_no,r.room_number,'') object_no,
                          COALESCE(NULLIF(c.building_area,0),NULLIF(c.contract_area,0),s.area,r.area,0) area,
                          COALESCE(s.floor,r.floor,1) floor,
                          COALESCE(s.water_rate_type,r.water_rate_type,'非居民') water_rate_type,
                          COALESCE(r.building,'商场') building,COALESCE(r.unit,'商场') unit,
                          COALESCE(r.category,'商户') category
                   FROM merchant_contracts c
                   LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
                   LEFT JOIN rooms r ON c.room_id=r.id
                   WHERE c.id=? AND c.status='active'""", (contract_id,)
            ).fetchone()
            if not contract:
                db.close()
                return self._redirect('/commercial_billing?flash=商业合同不存在或已停用')
            all_rids = []
            room_names.append('合同' + contract['contract_no'])
            rm = {'id': contract['commercial_space_id'] or contract['room_id'], 'building': contract['building'], 'unit': contract['unit'],
                  'room_number': contract['object_no'], 'category': contract['category'], 'area': contract['area'],
                  'floor': contract['floor'], 'owner_id': contract['owner_id'],
                  'water_rate_type': contract['water_rate_type'], 'custom_rate': contract['property_rate'], 'commercial_space_id': contract['commercial_space_id'],
                  'payment_cycle': contract['property_cycle']}
            for fid in ft_ids:
                try:
                    fid = int(str(fid).strip())
                except ValueError:
                    continue
                ft = db.execute("SELECT * FROM fee_types WHERE id=? AND is_active=1", (fid,)).fetchone()
                if not ft or not fee_applies_to_room(ft['name'] or '', rm):
                    continue
                exists = db.execute(
                    "SELECT id FROM bills WHERE source='merchant_contract' AND source_ref=? AND fee_type_id=? AND billing_period=?",
                    (str(contract_id), fid, period_label)
                ).fetchone()
                if exists:
                    skipped_existing += 1
                    continue
                custom_key = f'custom_amount_{fid}'
                custom_val = d.get(custom_key, [''])[0] if isinstance(d.get(custom_key), list) else d.get(custom_key, '')
                calc = calculate_bill_amount(db, rm, ft, period_label, months, custom_val, period_start, period_end, manual_factor)
                if calc['amount'] <= 0:
                    continue
                seq = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period=?", (period_label,)).fetchone()[0] + total_g + 1
                bn = f"合同{contract_id}_{period_label.replace('~','-')}_{seq:04d}"
                cur = db.execute(
                    "INSERT INTO bills(room_id,commercial_space_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end,source,source_ref) VALUES(?,?,?,?,?,?,?,'unpaid',?,?,?,?,?)",
                    (contract['room_id'], contract['commercial_space_id'], contract['owner_id'], fid, period_label, calc['amount'], period_end, bn, period_start, period_end, 'merchant_contract', str(contract_id))
                )
                apply_snapshot(db, cur.lastrowid, contract_snapshot(db, int(contract_id)))
                total_g += 1
        for rid in all_rids:
            rm = db.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
            if not rm:
                continue
            bill_months = months
            bill_period_label = period_label
            bill_due_date = due_date
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
                calc = calculate_bill_amount(db, rm, ft, bill_period_label, bill_months, custom_val, period_start, bill_due_date, manual_factor)
                amt = calc['amount']
                if amt <= 0:
                    continue
                on = db.execute("SELECT name FROM owners WHERE id=?", (rm['owner_id'],)).fetchone()
                oname = (on[0] if on else '未知')[:10]
                rshort = rm['building'] + '-' + rm['room_number']
                seq = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period=?", (bill_period_label,)).fetchone()[0] + total_g + 1
                bn = f"{rshort}_{oname}_{bill_period_label.replace('~','-')}_{seq:04d}"
                source = 'merchant_contract' if contract_id else 'normal'
                source_ref = str(contract_id) if contract_id else None
                cur = db.execute(
                    "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,service_start,service_end,source,source_ref) VALUES(?,?,?,?,?,?,'unpaid',?,?,?,?,?)",
                    (rid, rm['owner_id'], fid, bill_period_label, amt, bill_due_date, bn, period_start, bill_due_date, source, source_ref)
                )
                apply_snapshot(db, cur.lastrowid, room_snapshot(db, rid, rm['owner_id']))
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
        cleanup_invalid_payments(db)
        b=db.execute('''SELECT b.*,r.building,r.unit,r.room_number,s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,f.name ft,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE b.id=?''',(bid,)).fetchone()
        if not b:return self._error(404)
        db.close();rem=money_float(b['amount'])-money_float(b['paid'])
        current_operator = _current_operator_name(self)
        if rem <= 0 or b['status'] == 'paid':
            return self._html(self._page('缴费', f'''
<div class="alert alert-info"><strong>该账单已结清</strong>：当前欠费为 ¥0.00，不能重复收款。</div>
<div class="card"><div class="card-header">账单核对</div><div class="card-body">
<div class="row text-center g-2"><div class="col-md-4"><div class="finance-summary"><div class="text-muted small">应收</div><strong class="money">¥{m(b["amount"])}</strong></div></div>
<div class="col-md-4"><div class="finance-summary"><div class="text-muted small">历史已收</div><strong class="money money-paid">¥{m(b["paid"])}</strong></div></div>
<div class="col-md-4"><div class="finance-summary"><div class="text-muted small">当前欠费</div><strong class="money money-paid">¥0.00</strong></div></div></div>
<div class="export-actions mt-3"><form method="POST" action="/bills/receipt_by_ids" target="_blank" class="d-inline">
<input type="hidden" name="bill_ids" value="{bid}"><button class="btn btn-outline-secondary">打印收据</button></form>
<a href="/bills/{bid}" class="btn btn-primary">返回账单详情</a><a href="/bills" class="btn btn-outline-secondary">返回账单管理</a></div>
</div></div>''','bills'))
        self._html(self._page('缴费',f'''
<div class="row g-4"><div class="col-md-5"><div class="card"><div class="card-header">账单信息</div>
<div class="card-body"><table class="table table-borderless mb-0">
<tr><td class="text-muted">对象</td><td>{h(_bill_target_label(b))}</td></tr>
<tr><td class="text-muted">费用</td><td><span class="badge bg-info">{h(b["ft"])}</span></td></tr>
<tr><td class="text-muted">账期</td><td>{h(b["billing_period"])}</td></tr>
<tr><td class="text-muted">编号</td><td><small>{h(b["bill_number"]or"-")}</small></td></tr></table><hr>
<p class="text-center mb-0"><small>应缴</small><h2 class="text-primary text-center">¥{m(b["amount"])}</h2>
{"<small>还需: ¥"+m(rem)+"</small>" if b["paid"]>0 else ""}</p></div></div></div>
<div class="col-md-7"><div class="card"><div class="card-header">录入缴费</div>
<div class="card-body"><form method=POST action="/bills/{bid}/pay" class="row g-3">
<div class="col-md-6"><label>缴费金额 *</label><div class="input-group"><span class="input-group-text">¥</span>
<input name="amount_paid" type="number" class="form-control form-control-lg" value="{m(rem)}" step="0.1" required></div></div>
<div class="col-md-6"><label>支付方式</label><select name="payment_method" class="form-select form-control-lg">
<option value="cash">现金</option><option value="transfer">转账</option><option value="wechat">微信</option><option value="alipay">支付宝</option></select></div>
<div class="col-md-6"><label>收费员</label><input name="operator" class="form-control" value="{h(current_operator)}"></div>
<div class="col-md-6"><label>备注</label><input name="notes" class="form-control"></div>
<div class="col-12"><hr><button class="btn btn-success btn-lg"><i class="bi bi-credit-card"></i> 确认缴费</button>
<a href="/bills/{bid}" class="btn btn-outline-secondary">取消</a></div></form></div></div></div></div>''','bills'))

    def _bill_pay_post(self, bid, d):
        db=get_db()
        cleanup_invalid_payments(db)
        amt=money_float(qs(d,'amount_paid',0))
        if amt<=0:db.close();return self._redirect(f'/bills/{bid}/pay?flash=金额必须大于0')
        bill=db.execute("SELECT amount,billing_period,COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=bills.id),0) paid FROM bills WHERE id=?",(bid,)).fetchone()
        if not bill:db.close();return self._error(404)
        if is_period_closed(bill['billing_period']):
            db.close();return self._redirect(f'/bills/{bid}?flash={bill["billing_period"]}已结账，无法收费')
        rem=money_float(bill['amount'])-money_float(bill['paid'])
        if rem <= 0:
            db.close();return self._redirect(f'/bills/{bid}?flash=账单已结清，不能重复收费')
        if amt > rem:
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
            }, Actor(username=qs(d,'operator') or _current_operator_name(self), role='operator'))
        except ServiceError as exc:
            return self._redirect(f'/bills/{bid}/pay?flash={urllib.parse.quote(str(exc))}')
        self._audit('payment_create', 'bill', bid, {'remaining': rem}, {'amount_paid': amt, 'receipt_number': receipt_no}, qs(d,'notes'))
        after_due = max(0, rem - amt)
        result_title = '收款成功'
        self._html(self._page(result_title, f'''
<div class="alert alert-success"><strong>收款成功</strong>：本次收款 ¥{m(amt)}。</div>
<div class="row text-center g-2 mb-3"><div class="col-md-3"><div class="finance-summary"><div class="text-muted small">本次收款</div><strong class="money money-paid">¥{m(amt)}</strong></div></div>
<div class="col-md-3"><div class="finance-summary"><div class="text-muted small">历史已收</div><strong class="money money-paid">¥{m(float(bill["paid"] or 0) + amt)}</strong></div></div>
<div class="col-md-3"><div class="finance-summary"><div class="text-muted small">当前欠费</div><strong class="money money-due">¥{m(after_due)}</strong></div></div>
<div class="col-md-3"><div class="finance-summary"><div class="text-muted small">收据号</div><strong>{h(receipt_no)}</strong></div></div></div>
<div class="export-actions"><form method="POST" action="/bills/receipt_by_ids" target="_blank" class="d-inline">
<input type="hidden" name="bill_ids" value="{bid}"><button class="btn btn-outline-secondary">打印收据</button></form>
<a class="btn btn-primary" href="/bills/{bid}">返回账单</a><a class="btn btn-outline-primary" href="/bills?status=unpaid">继续收下一个</a><a class="btn btn-outline-secondary" href="/payments">查看缴费记录</a></div>
''','bills'))
