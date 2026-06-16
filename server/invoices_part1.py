from server.invoices_shared import *

class InvoiceMixinPart1(BaseHandler):
    def _invoice_requests(self, q):
        status_filter = qs(q, 'status', '')
        filters = {'status': status_filter} if status_filter else {}
        requests = InvoiceRequestService().list_requests(filters)['items']
        status_options = '<option value="">全部状态</option>' + ''.join(
            f'<option value="{s}"{" selected" if status_filter == s else ""}>{s}</option>'
            for s in ['pending', 'submitted', 'issued', 'failed']
        )
        rows = ''
        for r in requests:
            rows += f'''<tr><td><small>{h(r["request_no"])}</small></td><td>{h(r["buyer_name"] or "-")}</td>
            <td class="text-end">¥{h(r["amount"])}</td><td><span class="badge bg-secondary">{h(r["status"])}</span></td>
            <td>{h(r["external_invoice_id"] or "-")}</td><td><form method="POST" action="/invoice_requests/{h(r["request_no"])}/status" class="d-flex gap-1">
            <select name="status" class="form-select form-select-sm"><option value="submitted">submitted</option><option value="issued">issued</option><option value="failed">failed</option></select>
            <input name="external_invoice_id" class="form-control form-control-sm" placeholder="外部票据号">
            <button class="btn btn-sm btn-primary">更新</button></form></td></tr>'''
        self._html(self._page('电子票据请求', f'''
        <div class="d-flex justify-content-between mb-3"><form method="GET" class="d-flex gap-2">
        <select name="status" class="form-select form-select-sm" onchange="this.form.submit()">{status_options}</select>
        <a href="/invoice_requests" class="btn btn-sm btn-outline-secondary">重置</a></form></div>
        <div class="card"><div class="card-header">电子票据请求</div><div class="table-responsive"><table class="table table-hover mb-0">
        <thead><tr><th>请求号</th><th>抬头</th><th class="text-end">金额</th><th>状态</th><th>外部票据号</th><th style="min-width:360px">操作</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="6" class="text-center text-muted py-3">暂无电子票据请求</td></tr>'}</tbody></table></div></div>
        ''', 'invoices'))

    def _invoice_request_status_post(self, request_no, d):
        try:
            InvoiceRequestService().update_status(request_no, {
                'status': qs(d, 'status'),
                'external_invoice_id': qs(d, 'external_invoice_id'),
                'failure_reason': qs(d, 'failure_reason'),
            })
            return self._redirect('/invoice_requests?flash=电子票据状态已更新')
        except InvoiceRequestError as exc:
            return self._redirect('/invoice_requests?flash=' + str(exc))

    def _invoices(self, q):
        db=get_db()
        raw_period = qs(q, 'period').strip()
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
        if period_start or period_end:
            period_label = f'{period_start or period_end} 至 {period_end or period_start}'
        else:
            period_label = p or '全部'
        kw=qs(q,'keyword').strip()
        sql='''SELECT i.*,b.bill_number,b.billing_period,b.amount bill_amount,
            r.building,r.unit,r.room_number,o.name oname FROM invoices i
            LEFT JOIN bills b ON i.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id
            LEFT JOIN owners o ON b.owner_id=o.id
            WHERE 1=1'''
        vals = []
        if period_start or period_end:
            sql, vals = append_natural_date_range_filter(sql, vals, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        elif p:
            sql, vals = append_period_filter(sql, vals, p, 'b.billing_period')
        if kw:
            sql += ''' AND (i.invoice_number LIKE ? OR i.buyer_name LIKE ? OR i.buyer_tax_id LIKE ?
                OR o.name LIKE ? OR r.building LIKE ? OR r.unit LIKE ? OR r.room_number LIKE ?)'''
            vals.extend([f'%{kw}%'] * 7)
        rows=db.execute(sql + ' ORDER BY i.id DESC', vals).fetchall()
        total_sql = "SELECT COALESCE(SUM(i.amount),0) FROM invoices i JOIN bills b ON i.bill_id=b.id WHERE 1=1"
        total_vals = []
        if period_start or period_end:
            total_sql, total_vals = append_natural_date_range_filter(total_sql, total_vals, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        elif p:
            total_sql, total_vals = append_period_filter(total_sql, total_vals, p, 'b.billing_period')
        total=db.execute(total_sql,total_vals).fetchone()[0]
        avail_sql='''SELECT b.id,b.bill_number,b.amount,b.billing_period,b.customer_name_snapshot,
                r.building,r.unit,r.room_number,r.tenant_name,r.shop_name,o.name oname
            FROM bills b JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            WHERE b.status='paid' AND b.id NOT IN (SELECT bill_id FROM invoices)'''
        avail_vals = []
        if period_start or period_end:
            avail_sql, avail_vals = append_natural_date_range_filter(avail_sql, avail_vals, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        elif p:
            avail_sql, avail_vals = append_period_filter(avail_sql, avail_vals, p, 'b.billing_period')
        avail=db.execute(avail_sql + ''' ORDER BY
            COALESCE(NULLIF(b.customer_name_snapshot,''), NULLIF(r.tenant_name,''), NULLIF(r.shop_name,''), o.name, ''),
            r.building, r.unit, r.room_number, b.billing_period, b.id''', avail_vals).fetchall()
        db.close()
        rh=''
        for r in rows:
            rh+='<tr>'
            rh+='<td><small>'+h(r['invoice_number'] or '-')+'</small></td>'
            rh+='<td>'+h(r['building']or'')+'-'+h(r['unit']or'')+'-'+h(r['room_number']or'')+'</td>'
            buyer_hint = h(r['buyer_name'] or r['oname'] or '-')
            owner_hint = h(r['oname'] or '-')
            rh+='<td><strong>'+buyer_hint+'</strong><br><small class="text-muted">业主：'+owner_hint+'</small></td>'
            rh+='<td class="text-end">¥'+m(r['amount'])+'</td>'
            rh+='<td>'+h(r['issue_date']or'-')+'</td>'
            rh+='<td><span class="badge bg-success">已开具</span></td>'
            rh+='<td><a href="/invoices/'+str(r['id'])+'/print" class="btn btn-sm btn-outline-info"><i class="bi bi-printer"></i> 打印</a> '
            rh+='<form method=POST action="/invoices/'+str(r['id'])+'/delete" style=display:inline><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form></td></tr>'
        av_opts = '<option value="">--选择--</option>'
        current_group = None
        for a in avail:
            tenant = a['customer_name_snapshot'] or a['tenant_name'] or a['shop_name'] or a['oname'] or '未登记商户'
            room_full = '-'.join([x for x in [a['building'], a['unit'], a['room_number']] if x])
            room_short = '-'.join([x for x in [a['building'], a['room_number']] if x])
            group_label = f'{tenant} / {room_full or room_short or "未登记房间"}'
            if group_label != current_group:
                if current_group is not None:
                    av_opts += '</optgroup>'
                av_opts += f'<optgroup label="{h(group_label)}">'
                current_group = group_label
            period_hint = f' {a["billing_period"]}' if a['billing_period'] else ''
            bill_hint = f' {a["bill_number"]}' if a['bill_number'] else ''
            owner_hint = f' 业主:{a["oname"]}' if a['oname'] and a['oname'] != tenant else ''
            av_opts += (
                f'<option value="{a["id"]}">'
                f'{h(room_short or room_full)} {h(tenant)}{h(owner_hint)}{h(period_hint)}{h(bill_hint)} ¥{m(a["amount"])}'
                f'</option>'
            )
        if current_group is not None:
            av_opts += '</optgroup>'
        # Available bills for invoice
        self._html(self._page("发票管理", f'''
    <div class="invoice-dashboard">
    <section class="invoice-section" data-invoice-section="filters">
    <div class="invoice-section-title"><i class="bi bi-funnel"></i> 筛选发票</div>
    <div class="row g-2 align-items-end">
    <form class="row g-2 align-items-end" method=GET>
    <div class="col-auto"><label class="form-label small text-muted mb-1">起始日期</label><input type="date" name="period_start" class="form-control form-control-sm" value="{h(period_start)}" onchange="this.form.submit()"></div>
    <div class="col-auto"><label class="form-label small text-muted mb-1">截止日期</label><input type="date" name="period_end" class="form-control form-control-sm" value="{h(period_end)}" onchange="this.form.submit()"></div>
    <div class="col-auto"><label class="form-label small text-muted mb-1">发票列表筛选</label><input name="keyword" class="form-control form-control-sm" value="{h(kw)}" placeholder="发票号/抬头/税号/房号"></div>
    <div class="col-auto"><button class="btn btn-sm btn-outline-primary"><i class="bi bi-search"></i> 筛选</button><a href="/invoices" class="btn btn-sm btn-outline-secondary"><i class="bi bi-x-circle"></i></a></div></form>
    <div class="col-auto ms-auto"><div class="summary-tile py-2 px-3"><div class="label">筛选范围已开票金额</div><strong class="money">¥{m(total)}</strong></div></div>
    </div></section>
    <div class="row g-4">
    <div class="col-md-8"><section class="invoice-section" data-invoice-section="issued"><div class="invoice-section-title"><i class="bi bi-receipt-cutoff"></i> 已开发票列表 <small class="text-muted">({period_label})</small></div>
    <div class="table-responsive"><table class="table table-hover mb-0"><thead><tr><th>发票号</th><th>房间</th><th>业主</th><th class="text-end">金额</th><th>开票日期</th><th>状态</th><th style="width:100px">操作</th></tr></thead>
    <tbody>{rh or '<tr><td colspan="7" class="text-center text-muted py-3">暂无发票</td></tr>'}</tbody></table></div></section></div>
    <div class="col-md-4"><section class="invoice-section" data-invoice-section="available"><div class="invoice-section-title"><i class="bi bi-receipt"></i> 待开票账单</div>
    <div class="card-body"><form method=POST action="/invoices/create" class="row g-3">
    <input type="hidden" name="period_start" value="{h(period_start)}">
    <input type="hidden" name="period_end" value="{h(period_end)}">
    <div class="col-12"><label>选择已缴费账单</label><select name="bill_id" class="form-select" required>{av_opts}</select></div>
    <div class="col-12"><label>开票日期</label><input name="issue_date" type="date" class="form-control" value="{date.today().isoformat()}"></div>
    <div class="col-12"><label>购买方名称</label><input name="buyer_name" class="form-control" placeholder="单位名称或个人姓名"></div>
    <div class="col-12"><label>纳税人识别号</label><input name="buyer_tax_id" class="form-control" placeholder="税号（选填）"></div>
    <div class="col-12"><hr><button class="btn btn-success"><i class="bi bi-receipt"></i> 开具发票</button></div>
    </form></div></section></div></div></div>''', "invoices"))

    def _invoice_redirect(self, flash, period='', period_start='', period_end=''):
        params = {}
        if period_start:
            params['period_start'] = period_start
        if period_end:
            params['period_end'] = period_end
        if period and not (period_start or period_end):
            params['period'] = period
        params['flash'] = flash
        return self._redirect('/invoices?' + urlencode(params))

    def _invoice_create(self, d):
        db=get_db()
        bid=qs(d,'bill_id')
        period_value = qs(d, 'period').strip()
        period_start = qs(d, 'period_start', '').strip()
        period_end = qs(d, 'period_end', '').strip()
        if not bid:
            db.close()
            return self._invoice_redirect('请选择账单', period_value, period_start, period_end)
        bill=db.execute("SELECT * FROM bills WHERE id=? AND status='paid'",(int(bid),)).fetchone()
        if not bill:
            db.close()
            return self._invoice_redirect('账单未找到或未缴费', period_value, period_start, period_end)
        exist=db.execute("SELECT id FROM invoices WHERE bill_id=?",(int(bid),)).fetchone()
        if exist:
            db.close()
            return self._invoice_redirect('该账单已开过发票', period_value, period_start, period_end)
        # Generate invoice number
        cnt=db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]+1
        inv_no=f"INV-{date.today().strftime('%Y%m%d')}-{cnt:04d}"
        db.execute("INSERT INTO invoices(bill_id,invoice_number,amount,issue_date,buyer_name,buyer_tax_id) VALUES(?,?,?,?,?,?)",
                   (int(bid),inv_no,bill['amount'],qs(d,'issue_date',date.today().isoformat()),qs(d,'buyer_name'),qs(d,'buyer_tax_id')))
        db.commit();db.close()
        self._invoice_redirect('发票开具成功: '+inv_no, period_value, period_start, period_end)
