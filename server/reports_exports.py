from server.reports_shared import *


def _send_csv(handler, filename, headers, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    raw = buf.getvalue().encode('utf-8-sig')
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/csv; charset=utf-8')
    handler.send_header('Content-Disposition', f'attachment; filename={filename}')
    handler.send_header('Content-Length', str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class ReportExportMixin(BaseHandler):
    def _reports_arrears_detail_csv(self, q):
        p, start, end, _ = self._report_range(q)
        building = qs(q, 'building')
        status = qs(q, 'status') or 'arrears'
        data = self._report_reconciliation_data(p, building, status, start, end)
        rows = []
        for r in data['arrears']:
            due = float(r['amount'] or 0) - float(r['paid'] or 0)
            rows.append([
                r['bill_number'] or r['id'], _report_target_label(r), _report_customer_name(r),
                r['phone'] or '', r['fee_name'] or '', r['billing_period'] or '',
                m(r['amount']), m(r['paid']), m(due), r['status'] or '', r['due_date'] or '',
            ])
        _send_csv(self, f'arrears_detail_{start or p}.csv', [
            'bill_number', 'target', 'customer', 'phone', 'fee_type', 'period',
            'amount', 'paid', 'due', 'status', 'due_date',
        ], rows)

    def _reports_payment_detail_csv(self, q):
        p, start, end, _ = self._report_range(q)
        building = qs(q, 'building')
        period_clause, vals = self._report_filter_clause(p, start, end, 'b.billing_period', 'b.service_start', 'b.service_end')
        cond = [period_clause]
        if building:
            cond.append("(r.building=? OR (?='商场' AND b.commercial_space_id IS NOT NULL))")
            vals.extend([building, building])
        db = get_db()
        rows = db.execute(f'''SELECT p.payment_date,p.receipt_number,p.payment_method,p.operator,p.amount_paid,
            b.bill_number,b.billing_period,COALESCE(r.building,'商场') building,r.unit,r.room_number,
            s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,o.name owner_name,f.name fee_name,b.commercial_space_id
            FROM payments p JOIN bills b ON p.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
            LEFT JOIN owners o ON b.owner_id=o.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE {' AND '.join(cond)} ORDER BY p.payment_date DESC,p.id DESC''', vals).fetchall()
        db.close()
        out = []
        for r in rows:
            out.append([
                r['payment_date'] or '', r['receipt_number'] or '', r['bill_number'] or '',
                _report_target_label(r), _report_customer_name(r), r['fee_name'] or '',
                r['payment_method'] or '', r['operator'] or '', m(r['amount_paid']),
            ])
        _send_csv(self, f'payment_detail_{start or p}.csv', [
            'payment_date', 'receipt_number', 'bill_number', 'target', 'customer',
            'fee_type', 'method', 'operator', 'amount',
        ], out)

    def _reports_waivers_csv(self, q):
        p, start, end, _ = self._report_range(q)
        rows = self._report_waiver_data(p, qs(q, 'building'), qs(q, 'status'), start, end)
        out = [[
            r['created_at'] or '', r['bill_number'] or '', f"{r['building'] or ''}-{r['room_number'] or ''}",
            r['customer_name'] or '', r['fee_name'] or '', m(r['old_amount']), m(r['new_amount']),
            m(r['waiver_amount']), r['reason'] or '', r['approved_by'] or '',
        ] for r in rows]
        _send_csv(self, f'waivers_{start or p}.csv', [
            'created_at', 'bill_number', 'target', 'customer', 'fee_type',
            'old_amount', 'new_amount', 'waiver_amount', 'reason', 'approved_by',
        ], out)

    def _reports_customer_summary_csv(self, q):
        p, start, end, _ = self._report_range(q)
        data = self._report_reconciliation_data(p, qs(q, 'building'), qs(q, 'status'), start, end)
        grouped = {}
        for r in data['rows']:
            key = (_report_charge_customer_name(r), _report_target_label(r))
            item = grouped.setdefault(key, {
                'phone': r['phone'] or '', 'count': 0, 'amount': 0.0, 'paid': 0.0,
                'paid_count': 0, 'partial_count': 0, 'unpaid_count': 0,
            })
            amount = float(r['amount'] or 0)
            paid = float(r['paid'] or 0)
            item['count'] += 1
            item['amount'] += amount
            item['paid'] += paid
            if r['status'] == 'paid':
                item['paid_count'] += 1
            elif r['status'] == 'partial':
                item['partial_count'] += 1
            else:
                item['unpaid_count'] += 1
        rows = []
        for (customer, target), item in sorted(grouped.items()):
            rows.append([
                customer, target, item['phone'], item['count'], m(item['amount']),
                m(item['paid']), m(item['amount'] - item['paid']), item['paid_count'],
                item['partial_count'], item['unpaid_count'],
            ])
        _send_csv(self, f'customer_summary_{start or p}.csv', [
            'customer', 'target', 'phone', 'bill_count', 'amount', 'paid', 'due',
            'paid_count', 'partial_count', 'unpaid_count',
        ], rows)
