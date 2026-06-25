from server.payments_shared import *
from server.pagination import pagination_state, query_items, render_pagination
from server.bill_receipt_shared import _receipt_period_label, print_style_table


def _payment_period_text(row):
    start = (row['service_start'] or '' ).strip()
    end = (row['service_end'] or '' ).strip()
    if start and end:
        return f"{start} 至 {end}"
    return row['billing_period'] or '-'


class PaymentMixinPart2(BaseHandler):
    def _payments(self, q):
        raw_period = qs(q, 'period', '').strip()
        period_start = qs(q, 'period_start', '').strip()
        period_end = qs(q, 'period_end', '').strip()
        p = date_to_period(raw_period) if raw_period else ''
        if p and not period_start and not period_end:
            period_start = period_to_date(p)
            try:
                y, mo = [int(x) for x in period_start[:7].split('-')]
                period_end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
            except Exception:
                period_end = period_start
        db=get_db();pm=qs(q,'method','');op=qs(q,'operator','').strip();kw=qs(q,'keyword','').strip()
        sql='''SELECT p.*,b.bill_number,b.billing_period,b.service_start,b.service_end,b.amount,b.room_id,b.commercial_space_id,b.fee_type_id,
            r.building,r.unit,r.room_number,r.tenant_name,r.shop_name,s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,o.name owner_name,f.name ft
            FROM payments p JOIN bills b ON p.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE 1=1'''
        vals=[]
        if period_start or period_end:
            sql, vals = append_natural_date_range_filter(sql, vals, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        elif p:
            sql, vals = append_period_filter(sql, vals, p, 'b.billing_period')
        if pm:sql+=" AND p.payment_method=?";vals.append(pm)
        if op:sql+=" AND p.operator LIKE ?";vals.append(f'%{op}%')
        if kw:
            like = f'%{kw}%'
            sql += ''' AND (
                r.room_number LIKE ? OR r.tenant_name LIKE ? OR r.shop_name LIKE ?
                OR s.space_no LIKE ? OR s.shop_name LIKE ? OR s.merchant_name LIKE ?
                OR o.name LIKE ? OR r.building LIKE ? OR r.unit LIKE ?
                OR b.bill_number LIKE ? OR p.receipt_number LIKE ? OR f.name LIKE ?
            )'''
            vals.extend([like] * 12)
        total_rows = db.execute("SELECT COUNT(*) FROM (" + sql + ")", vals).fetchone()[0]
        total_amount = db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) FROM (" + sql + ")",
            vals,
        ).fetchone()[0]
        pg, per_page, total_pages = pagination_state(q, total_rows)
        sql+=" ORDER BY p.payment_date DESC,p.id DESC LIMIT ? OFFSET ?"
        page_vals = vals + [per_page, (pg - 1) * per_page]
        rows=db.execute(sql,page_vals).fetchall()
        room_ids = sorted({r['room_id'] for r in rows if r['room_id']})
        space_ids = sorted({r['commercial_space_id'] for r in rows if r['commercial_space_id']})
        bill_context = {}
        if room_ids:
            placeholders = ','.join('?' for _ in room_ids)
            bill_rows = db.execute(f'''SELECT b.room_id,b.commercial_space_id,b.service_start,b.service_end,b.billing_period,b.amount,b.status,
                COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                FROM bills b WHERE b.room_id IN ({placeholders}) ORDER BY COALESCE(b.service_start,b.billing_period),b.id''', room_ids).fetchall()
            for bill in bill_rows:
                key = ('space', bill['commercial_space_id']) if bill['commercial_space_id'] else ('room', bill['room_id'] or 0)
                ctx = bill_context.setdefault(key, {'paid_through': '', 'next_due': '', 'partial_due': '', 'paid_total': 0.0, 'due_total': 0.0})
                start = (bill['service_start'] or '').strip()
                end = (bill['service_end'] or '').strip()
                paid = float(bill['paid'] or 0)
                amt = float(bill['amount'] or 0)
                ctx['paid_total'] += paid
                ctx['due_total'] += max(0.0, amt - paid)
                if paid > 0 and end and end > ctx['paid_through']:
                    ctx['paid_through'] = end
                if paid < amt:
                    due_label = f"{start} 至 {end}" if start and end else (bill['billing_period'] or '-')
                    if paid <= 0 and not ctx['next_due']:
                        ctx['next_due'] = due_label
                    elif paid > 0 and not ctx.get('partial_due'):
                        ctx['partial_due'] = due_label
        if space_ids:
            placeholders = ','.join('?' for _ in space_ids)
            bill_rows = db.execute(f'''SELECT b.room_id,b.commercial_space_id,b.service_start,b.service_end,b.billing_period,b.amount,b.status,
                COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
                FROM bills b WHERE b.commercial_space_id IN ({placeholders}) ORDER BY COALESCE(b.service_start,b.billing_period),b.id''', space_ids).fetchall()
            for bill in bill_rows:
                key = ('space', bill['commercial_space_id']) if bill['commercial_space_id'] else ('room', bill['room_id'] or 0)
                ctx = bill_context.setdefault(key, {'paid_through': '', 'next_due': '', 'partial_due': '', 'paid_total': 0.0, 'due_total': 0.0})
                start = (bill['service_start'] or '').strip()
                end = (bill['service_end'] or '').strip()
                paid = float(bill['paid'] or 0)
                amt = float(bill['amount'] or 0)
                ctx['paid_total'] += paid
                ctx['due_total'] += max(0.0, amt - paid)
                if paid > 0 and end and end > ctx['paid_through']:
                    ctx['paid_through'] = end
                if paid < amt:
                    due_label = f"{start} 至 {end}" if start and end else (bill['billing_period'] or '-')
                    if paid <= 0 and not ctx['next_due']:
                        ctx['next_due'] = due_label
                    elif paid > 0 and not ctx.get('partial_due'):
                        ctx['partial_due'] = due_label
        db.close()
        tc=float(total_amount or 0)
        groups = []
        by_room = {}
        for r in rows:
            key = ('space', r['commercial_space_id']) if r['commercial_space_id'] else ('room', r['room_id'] or 0)
            if key not in by_room:
                by_room[key] = {'group_kind': key[0], 'group_id': key[1], 'room': _bill_target_label(r),
                                'owner': _bill_customer_label(r), 'rows': [], 'total': 0}
                groups.append(by_room[key])
            by_room[key]['rows'].append(r)
            by_room[key]['total'] += float(r['amount_paid'] or 0)
        rh_parts = []
        for idx, g in enumerate(groups, 1):
            safe_id = f"p{idx}_{g['group_kind']}_{g['group_id'] or 0}".replace('-', '_')
            latest = g['rows'][0]['payment_date'] if g['rows'] else ''
            periods = sorted({_payment_period_text(x) for x in g['rows'] if x['billing_period']})
            period_text = periods[0] if len(periods) == 1 else (periods[0] + ' ~ ' + periods[-1] if periods else '-')
            methods = '、'.join(sorted({x['payment_method'] for x in g['rows'] if x['payment_method']})) or '-'
            ctx = bill_context.get((g['group_kind'], g['group_id']), {'paid_through': '', 'next_due': '', 'partial_due': '', 'paid_total': 0.0, 'due_total': 0.0})
            ctx_bits = [f"历史缴费/欠费：已收 ¥{m(ctx.get('paid_total', 0))}，欠费 ¥{m(ctx.get('due_total', 0))}"]
            if ctx.get('paid_through'): ctx_bits.append(f"已缴至：{ctx['paid_through']}")
            if ctx.get('next_due'): ctx_bits.append(f"下期待缴：{ctx['next_due']}")
            elif ctx.get('partial_due'): ctx_bits.append(f"未缴清：{ctx['partial_due']}")
            ctx_text = ' · '.join(ctx_bits)
            room_line = f"<br><small class='text-muted'>{h(ctx_text)}</small>" if ctx_text else ''
            rh_parts.append(f'''<tr class="table-light payment-group" style="cursor:pointer" onclick="togglePaymentGroup('{safe_id}')">
<td><input type="checkbox" class="payment-group-chk" data-payment-group="{safe_id}" onclick="event.stopPropagation();togglePaymentSelection('{safe_id}',this.checked)"></td>
<td><i class="bi bi-chevron-right" id="pay_icon_{safe_id}"></i> <strong>{h(g['room'])}</strong><br><small class="text-muted">{h(g['owner'])}</small>{room_line}</td>
<td><span class="badge status-neutral">汇总</span></td>
<td>{h(period_text)}</td><td><span class="badge status-neutral">{len(g['rows'])}笔</span></td>
<td class="text-end"><strong class="money money-paid">+¥{m(g['total'])}</strong></td>
<td>{h(methods)}</td><td colspan="2"><small class="text-muted">最近：{h(latest or '-')}</small></td></tr>''')
            for r in g['rows']:
                rh_parts.append(f'''<tr class="payment-detail-{safe_id}" style="display:none"><td><input form="paymentActionForm" type="checkbox" name="payment_ids" data-payment-group="{safe_id}" value="{r['id']}"></td><td><small>{h(r["payment_date"]or"-")}</small></td>
<td><small>{h(r["bill_number"]or"-")}</small></td>
<td>{h(_bill_target_label(r))}</td>
<td><span class="badge status-info">{h(r["ft"])}</span></td><td>{h(_payment_period_text(r))}</td>
<td class="text-end"><span class="money money-paid">+¥{m(r["amount_paid"])}</span></td>
<td>{h(r["payment_method"])}</td><td>{h(r["operator"]or"-")}</td><td><small>{h(r["receipt_number"] or "-")}</small></td></tr>''')
        rh=''.join(rh_parts)
        tpl=self._load_template('payments.html')
        tpl=tpl.replace('{PERIOD_START}',h(period_start)).replace('{PERIOD_END}',h(period_end)).replace('{OP}',h(op)).replace('{KW}',h(kw)).replace('{TOTAL}',m(tc))
        tpl=tpl.replace('{SC}',' selected' if pm=='cash' else '').replace('{ST}',' selected' if pm=='transfer' else '')
        tpl=tpl.replace('{SW}',' selected' if pm=='wechat' else '').replace('{SA}',' selected' if pm=='alipay' else '')
        tpl=tpl.replace('<th>经手人</th>', '<th>经手人</th><th>收据号</th>')
        tpl=tpl.replace('{ROWS}',rh or '<tr><td colspan="10" class="text-center text-muted py-4">暂无缴费记录</td></tr>')
        page_links = render_pagination(
            '/payments',
            query_items(q, ['period_start', 'period_end', 'keyword', 'method', 'operator']),
            pg,
            total_pages,
            per_page,
            total_rows,
            '缴费记录分页',
        )
        tpl = tpl.replace('{PAGE_LINKS}', page_links)
        tpl += '<script src="/static/payment_ui.js?v=20260625csrf"></script>'
        self._html(self._page('缴费记录',tpl,'payments'))

    def _payments_print(self, d):
        ids = _extract_ids(d, 'payment_ids')
        if not ids:
            return self._redirect('/payments?flash=请勾选缴费记录')
        rows = self._selected_payment_rows(ids)
        if not rows:
            return self._redirect('/payments?flash=未找到缴费记录')
        self._html(print_style_table('缴费记录打印', rows, '缴费记录打印', '/payments', payment_mode=True))

    def _payment_receipts(self, d):
        ids = _extract_ids(d, 'payment_ids')
        if not ids:
            return self._redirect('/payments?flash=请勾选缴费记录')
        rows = self._selected_payment_rows(ids)
        bill_ids = ','.join(str(r['bill_id']) for r in rows if r['bill_id'])
        if not bill_ids:
            return self._redirect('/payments?flash=未找到可打印收据的账单')
        return self._receipt_by_ids({'bill_ids': bill_ids, 'back': '/payments'})

    def _selected_payment_rows(self, ids):
        placeholders = ','.join('?' * len(ids))
        db = get_db()
        rows = db.execute(f'''SELECT p.*,b.bill_number,b.billing_period,b.service_start,b.service_end,b.commercial_space_id,b.amount,
            r.building,r.unit,r.room_number,COALESCE(r.area,s.area,0) area,
            s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,o.name owner_name,
            f.name ft,f.calc_method,f.unit_price,
            COALESCE((SELECT SUM(old_amount-new_amount) FROM bill_adjustments WHERE bill_id=b.id AND new_amount<old_amount),0) waiver_amount
            FROM payments p JOIN bills b ON p.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE p.id IN ({placeholders}) ORDER BY p.payment_date DESC,p.id DESC''', ids).fetchall()
        db.close()
        return rows

    def _payments_csv(self, q):
        raw_period = qs(q, 'period', '').strip()
        period_start = qs(q, 'period_start', '').strip()
        period_end = qs(q, 'period_end', '').strip()
        p = date_to_period(raw_period) if raw_period else ''
        if p and not period_start and not period_end:
            period_start = period_to_date(p)
            try:
                y, mo = [int(x) for x in period_start[:7].split('-')]
                period_end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
            except Exception:
                period_end = period_start
        pm = qs(q, 'method', '')
        op = qs(q, 'operator', '')
        kw = qs(q, 'keyword', '').strip()
        sql = """SELECT p.*,b.bill_number,b.billing_period,b.amount,b.room_id,b.commercial_space_id,b.fee_type_id,
            r.building,r.unit,r.room_number,r.tenant_name,r.shop_name,s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,o.name owner_name,f.name ft
            FROM payments p JOIN bills b ON p.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id WHERE 1=1"""
        vals = []
        if period_start or period_end:
            sql, vals = append_natural_date_range_filter(sql, vals, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        elif p:
            sql, vals = append_period_filter(sql, vals, p, 'b.billing_period')
        if pm:
            sql += " AND p.payment_method=?"; vals.append(pm)
        if op:
            sql += " AND p.operator LIKE ?"; vals.append(f'%{op}%')
        if kw:
            like = f'%{kw}%'
            sql += """ AND (
                r.room_number LIKE ? OR r.tenant_name LIKE ? OR r.shop_name LIKE ?
                OR s.space_no LIKE ? OR s.shop_name LIKE ? OR s.merchant_name LIKE ?
                OR o.name LIKE ? OR r.building LIKE ? OR r.unit LIKE ?
                OR b.bill_number LIKE ? OR p.receipt_number LIKE ? OR f.name LIKE ?
            )"""
            vals.extend([like] * 12)
        sql += " ORDER BY p.payment_date DESC"
        db = get_db(); rows = db.execute(sql, vals).fetchall(); db.close()
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(['payment_date','receipt_number','bill_number','object','owner','fee_type','billing_period','amount_paid','payment_method','operator','notes'])
        for r in rows:
            w.writerow([r['payment_date'] or '', r['receipt_number'] or '', r['bill_number'] or '', _bill_target_label(r), _bill_customer_label(r), r['ft'] or '', r['billing_period'] or '', m(r['amount_paid']), r['payment_method'] or '', r['operator'] or '', r['notes'] or ''])
        data = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename=payments_{(period_start or p or "all")}.csv')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def _api_owner_info(self, oid):
        db=get_db()
        o=db.execute("SELECT name,phone FROM owners WHERE id=?",(oid,)).fetchone()
        db.close()
        self._json({'name':o[0] if o else '','phone':o[1] if o else ''} if o else {})
