from server.bill_receipt_shared import *
from server.billing_proration import prorated_month_factor


def _receipt_extract_bill_ids(d):
    raw = d.get('bill_ids', []) if d else []
    if isinstance(raw, str):
        raw = [raw]
    ids = []
    for item in raw:
        for part in str(item).split(','):
            cleaned = part.strip().strip('[]').strip().strip("'\"")
            if cleaned.isdigit():
                ids.append(cleaned)
    return ids


def _receipt_back_url(d):
    back_url = qs(d or {}, 'back', '/bills')
    return back_url if back_url.startswith('/bills') or back_url.startswith('/payments') else '/bills'


def _receipt_load_bills(ids):
    placeholders = ','.join('?' * len(ids))
    db = get_db()
    bills = db.execute(f'''SELECT b.*,f.name ft,f.calc_method,f.unit_price,
        COALESCE(r.building,'商场') building,
        CASE WHEN b.commercial_space_id IS NOT NULL THEN '' ELSE r.unit END unit,
        COALESCE(r.room_number,s.space_no) room_number,
        COALESCE(r.area,s.area,0) area,
        COALESCE(b.owner_id,r.owner_id) receipt_owner_id,
        s.merchant_name space_merchant,s.shop_name space_shop,
        COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid,
        (SELECT payment_method FROM payments WHERE bill_id=b.id ORDER BY payment_date DESC,id DESC LIMIT 1) latest_method,
        (SELECT operator FROM payments WHERE bill_id=b.id ORDER BY payment_date DESC,id DESC LIMIT 1) latest_operator,
        (SELECT payment_date FROM payments WHERE bill_id=b.id ORDER BY payment_date DESC,id DESC LIMIT 1) latest_payment_date,
        (SELECT receipt_number FROM payments WHERE bill_id=b.id AND COALESCE(receipt_number,'')<>'' ORDER BY payment_date DESC,id DESC LIMIT 1) latest_receipt_no,
        COALESCE((SELECT SUM(old_amount-new_amount) FROM bill_adjustments WHERE bill_id=b.id AND new_amount<old_amount),0) waiver_amount
        FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
        LEFT JOIN rooms r ON b.room_id=r.id
        LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
        WHERE b.id IN ({placeholders})
        ORDER BY f.sort_order,b.id''', ids).fetchall()
    owner = None
    if bills:
        owner = db.execute("SELECT name,phone FROM owners WHERE id=?", (bills[0]['receipt_owner_id'],)).fetchone()
    db.close()
    return bills, owner


def _receipt_room_str(row):
    if row['commercial_space_id']:
        return f"{h(row['building'])}\\{h(row['room_number'])}"
    return f"{h(row['building'])}\\{h(row['unit'])}\\{h(row['room_number'])}"


def _receipt_rooms_str(bills):
    seen = []
    for row in bills:
        label = _receipt_room_str(row)
        if label not in seen:
            seen.append(label)
    return '、'.join(seen)


def _receipt_months_for_bill(row):
    start = (row['service_start'] or '').strip()
    end = (row['service_end'] or '').strip()
    if start and end:
        return max(1, int(round(prorated_month_factor(start, end))))
    period = row['billing_period'] or ''
    if '~' in period:
        left, right = period.split('~', 1)
        try:
            ly, lm = [int(x) for x in left[:7].split('-')]
            ry, rm = [int(x) for x in right[:7].split('-')]
            return max(1, (ry - ly) * 12 + rm - lm + 1)
        except Exception:
            return 1
    return 1


def _receipt_usage(row):
    months = _receipt_months_for_bill(row)
    cm = row['calc_method']
    if cm in ('area', 'floor'):
        base = receipt_number(row['area'] or 0)
        return f'{base}×{months}' if months > 1 else base
    if cm == 'household':
        return f'1×{months}' if months > 1 else '1'
    if cm == 'meter':
        return '按抄表'
    return '1'


def _receipt_defaults(bills):
    operators = sorted({b['latest_operator'] for b in bills if b['latest_operator']})
    methods = sorted({b['latest_method'] for b in bills if b['latest_method']})
    pay_dates = sorted({b['latest_payment_date'] for b in bills if b['latest_payment_date']})
    receipt_numbers = [b['latest_receipt_no'] for b in bills if b['latest_receipt_no']]
    return {
        'operator': '、'.join(operators) if operators else '-',
        'payment_method': '、'.join(methods) if methods else '-',
        'payment_time': f'{pay_dates[0]} ~ {pay_dates[-1]}' if len(pay_dates) > 1 else (pay_dates[0] if pay_dates else '-'),
        'receipt_no': receipt_numbers[0] if receipt_numbers else f'JS{datetime.now().strftime("%Y%m%d%H%M%S")}',
    }


class BillReceiptMixinPart1(BaseHandler):
        def _receipt_by_ids(self, d):
            """根据勾选的 bill_ids 生成多模块收据"""
            back_url = _receipt_back_url(d)
            ids = _receipt_extract_bill_ids(d)
            if not ids:
                return self._redirect(back_url, '请勾选要生成收据的账单')
            bills, owner = _receipt_load_bills(ids)
            if not bills:
                return self._redirect(back_url, '未找到账单')
            if qs(d, 'confirm_receipt') != '1':
                return self._receipt_confirm_page(d, bills, owner, back_url)
            return self._receipt_render_page(d, bills, owner, back_url)

        def _receipt_confirm_page(self, d, bills, owner, back_url):
            rm = bills[0]
            defaults = _receipt_defaults(bills)
            owner_name = rm['space_merchant'] or rm['space_shop'] or (owner['name'] if owner else '')
            bill_ids = ','.join(str(b['id']) for b in bills)
            total_due = sum(float(b['amount'] or 0) + float(b['waiver_amount'] or 0) for b in bills)
            total_paid = sum(float(b['paid'] or 0) for b in bills)
            preview_rows = ''.join(f'''<tr><td>{h(b['ft'])}</td><td>{h(_receipt_period_label(b))}</td>
                <td>{h(_receipt_usage(b))}</td><td class="text-end">¥{m(b['amount'])}</td><td class="text-end">¥{m(b['paid'])}</td></tr>''' for b in bills)
            content = f'''
            <div class="alert alert-info"><strong>收据信息确认</strong>：请核对收款收据信息；摘要、备注、凭证号和签字仅用于本次打印，不写入系统。</div>
            <div class="row g-4"><div class="col-md-7"><div class="card"><div class="card-header">收据预览信息</div>
            <div class="card-body"><table class="table table-sm"><tbody>
            <tr><th>套户编号</th><td>{_receipt_rooms_str(bills)}</td></tr><tr><th>客户名称</th><td>{h(owner_name)}</td></tr>
            <tr><th>建筑面积</th><td>{h(receipt_number(rm['area']))}m2</td></tr><tr><th>流水号</th><td>{h(defaults['receipt_no'])}</td></tr>
            </tbody></table><table class="table table-sm"><thead><tr><th>收费项目</th><th>费用区间</th><th>使用量</th><th class="text-end">应收</th><th class="text-end">缴费</th></tr></thead><tbody>{preview_rows}
            <tr class="table-light"><td colspan="3" class="text-end"><strong>合计</strong></td><td class="text-end"><strong>¥{m(total_due)}</strong></td><td class="text-end"><strong>¥{m(total_paid)}</strong></td></tr></tbody></table></div></div></div>
            <div class="col-md-5"><div class="card"><div class="card-header">补充打印信息</div><div class="card-body">
            <form method="POST" action="/bills/receipt_by_ids" target="_blank" class="row g-3">
            <input type="hidden" name="confirm_receipt" value="1"><input type="hidden" name="bill_ids" value="{h(bill_ids)}"><input type="hidden" name="back" value="{h(back_url)}">
            <input type="hidden" name="receipt_no" value="{h(defaults['receipt_no'])}"><input type="hidden" name="payment_time" value="{h(defaults['payment_time'])}">
            <div class="col-12"><label>摘要</label><input name="summary" class="form-control"></div>
            <div class="col-12"><label>备注</label><input name="notes" class="form-control" value="请核对应收、缴费、欠费金额后再交付业主。"></div>
            <div class="col-md-6"><label>凭证号</label><input name="voucher_no" class="form-control"></div>
            <div class="col-md-6"><label>交款人签字</label><input name="payer_signature" class="form-control"></div>
            <div class="col-md-6"><label>收费员</label><input name="operator" class="form-control" value="{h(defaults['operator'])}"></div>
            <div class="col-md-6"><label>支付方式</label><input name="payment_method" class="form-control" value="{h(defaults['payment_method'])}"></div>
            <div class="col-12"><hr><button class="btn btn-primary btn-lg">生成打印收据</button><a class="btn btn-outline-secondary" href="{h(back_url)}">返回</a></div>
            </form></div></div></div></div>'''
            self._html(self._page('收据信息确认', content, 'bills'))

        def _receipt_render_page(self, d, bills, owner, back_url):
            rm = bills[0]
            defaults = _receipt_defaults(bills)
            owner_name = rm['space_merchant'] or rm['space_shop'] or (owner['name'] if owner else '')
            receipt_no = qs(d, 'receipt_no', defaults['receipt_no']) or defaults['receipt_no']
            voucher_no = qs(d, 'voucher_no', '')
            payment_time = qs(d, 'payment_time', defaults['payment_time']) or defaults['payment_time']
            operator_text = qs(d, 'operator', defaults['operator']) or defaults['operator']
            method_text = qs(d, 'payment_method', defaults['payment_method']) or defaults['payment_method']
            summary = qs(d, 'summary', '')
            notes = qs(d, 'notes', '')
            payer_signature = qs(d, 'payer_signature', '')
            rows_html = ''; total_due = total_discount = total_waiver = total_paid = total_rem = 0
            for b in bills:
                discount = 0.0; waiver = float(b['waiver_amount'] or 0); paid = float(b['paid'] or 0)
                due_before_discount = float(b['amount'] or 0) + discount + waiver
                rem = max(0.0, due_before_discount - discount - waiver - paid)
                rows_html += f'''<tr><td>{h(b['ft'])}</td><td>{h(_receipt_period_label(b))}</td><td>{h(_receipt_usage(b))}</td>
                    <td>1</td><td class="amt">{h(str(b['unit_price'] or ''))}</td><td class="amt">{m(due_before_discount)}</td>
                    <td class="amt">{m(discount)}</td><td class="amt">{m(waiver)}</td><td class="amt">{m(paid)}</td><td class="amt">{m(rem)}</td></tr>'''
                total_due += due_before_discount; total_discount += discount; total_waiver += waiver; total_paid += paid; total_rem += rem
            area_str = f"{receipt_number(rm['area'])}m2"
            today_str = datetime.now().strftime('%Y-%m-%d　%H:%M:%S')
            content = f'''
            <h1>陕西金莎国际物业管理有限公司</h1><h2 style="margin-top:0">收款收据</h2>
            <table class="header-info receipt-head"><tr><td><strong>套户编号：</strong>{_receipt_rooms_str(bills)}</td><td><strong>客户名称：</strong>{h(owner_name)}</td><td><strong>建筑面积：</strong>{area_str}</td></tr>
            <tr><td><strong>流水号：</strong>{h(receipt_no)}</td><td><strong>凭证号：</strong>{h(voucher_no)}</td><td><strong>缴费时间：</strong>{h(payment_time)}</td></tr></table>
            <table class="detail receipt-new-detail"><thead><tr><th style="width:18%">收费项目</th><th style="width:18%">费用区间</th><th style="width:12%">使用量</th><th style="width:7%">系数</th><th style="width:8%">单价</th><th class="amt" style="width:10%">应收</th><th class="amt" style="width:9%">优惠</th><th class="amt" style="width:9%">减免</th><th class="amt" style="width:9%">缴费</th><th class="amt" style="width:9%">欠费</th></tr></thead>
            <tbody>{rows_html}<tr class="total-row"><td colspan="5" style="text-align:center"><strong>缴费合计</strong></td><td class="amt"><strong>{m(total_due)}</strong></td><td class="amt"><strong>{m(total_discount)}</strong></td><td class="amt"><strong>{m(total_waiver)}</strong></td><td class="amt"><strong>{m(total_paid)}</strong></td><td class="amt"><strong>{m(total_rem)}</strong></td></tr></tbody></table>
            <table class="header-info receipt-foot"><tr><td colspan="3"><strong>摘要：</strong>{h(summary)}</td></tr><tr><td colspan="3"><strong>备注：</strong>{h(notes)}</td></tr>
            <tr><td><strong>收费员：</strong>{h(operator_text)}</td><td><strong>支付方式：</strong>{h(method_text)}</td><td><strong>交款人签字：</strong>{h(payer_signature)}</td></tr>
            <tr><td colspan="2"></td><td><strong>打印日期：</strong>{today_str}</td></tr></table>'''
            self._html(print_page(f'收款收据-{_receipt_room_str(rm)}', content, back_url=back_url, body_class='receipt-print'))

        def _receipt_setup(self, q):

            """收据设置页：选择房间和服务日期范围"""
            default_start, default_end = _receipt_date_range(q)
            if not default_start or not default_end:
                default_start, default_end = _month_range()
            db = get_db()
            rooms = db.execute("SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id ORDER BY r.building,r.room_number").fetchall()
            db.close()
            rm_opts = '<option value="">--选择房间--</option>' + ''.join(
                f'<option value="{r["id"]}">{h(r["building"])}-{h(r["room_number"])} ({h(r["oname"] or "")})</option>'
                for r in rooms
            )
            self._html(self._page('生成收据', f'''
            <div class="alert alert-info"><i class="bi bi-info-circle"></i> 选择房间、起始日期和截止日期，系统按起始日期和截止日期汇总账单后生成多模块收款收据。</div>
            <div class="row g-4">
            <div class="col-md-5">
            <div class="card">
            <div class="card-header">选择房间</div>
            <div class="card-body">
            <form id="receiptForm" target="_blank">
            <div class="mb-3"><label class="form-label">房间</label>
            <select class="form-select form-select-lg" id="receiptRoom" name="room_id" required>{rm_opts}</select></div>
            <div class="row g-2 mb-3">
            <div class="col-md-6"><label class="form-label">起始日期</label><input type="date" name="period_start" class="form-control" value="{h(default_start)}" required></div>
            <div class="col-md-6"><label class="form-label">截止日期</label><input type="date" name="period_end" class="form-control" value="{h(default_end)}" required></div>
            <small class="text-muted">按账单服务期筛选；旧账单无服务期时按原账单月份匹配。</small>
            </div>
            <hr>
            <div class="d-flex gap-2">
            <button type="button" class="btn btn-primary btn-lg" onclick="generateReceipt()"><i class="bi bi-printer"></i> 打印收据</button>
            <button type="button" class="btn btn-success btn-lg" onclick="exportReceipt()"><i class="bi bi-download"></i> 导出CSV</button>
            </div>
            </form>
            </div></div></div>
            <div class="col-md-7">
            <div class="card"><div class="card-header">收据预览说明</div>
            <div class="card-body">
            <p>多模块收款收据将所选日期范围内的所有费用按收费项目汇总，格式如下：</p>
            <ul class="small">
            <li>同一收费项目跨多月时自动合并为一行</li>
            <li>使用量显示为：面积×月数（如 100×6）</li>
            <li>各费用类型独立分行展示，底部显示合计</li>
            <li>套户编号、客户名称、建筑面积自动填充</li>
            </ul>
            </div></div></div>
            </div>
            <script>
            function generateReceipt(){{
                var f = document.getElementById("receiptForm");
                var rid = f.room_id.value;
                if(!rid){{ alert("请选择房间"); return; }}
                var params = "room_id=" + rid + "&period_start=" + f.period_start.value + "&period_end=" + f.period_end.value;
                window.open("/bills/receipt?" + params, "_blank");
            }}
            function exportReceipt(){{
                var f = document.getElementById("receiptForm");
                var rid = f.room_id.value;
                if(!rid){{ alert("请选择房间"); return; }}
                var params = "room_id=" + rid + "&period_start=" + f.period_start.value + "&period_end=" + f.period_end.value;
                window.open("/bills/export_receipt?" + params, "_blank");
            }}
            </script>
            ''', 'bills'))
