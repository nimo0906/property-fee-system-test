from server.reports_shared import *

class ReportMixinPart1(BaseHandler):
    def _report_period(self, q):
        raw = qs(q, 'period', get_period()).strip()
        if '~' in raw and len(raw) >= 15:
            return raw
        return date_to_period(raw)

    def _period_month_end(self, start_value):
        try:
            y, mo = [int(x) for x in str(start_value or '')[:7].split('-')]
            return (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
        except Exception:
            return str(start_value or '')

    def _report_range(self, q, default_to_current=True):
        raw = qs(q, 'period', '').strip()
        start = qs(q, 'period_start', '').strip()
        end = qs(q, 'period_end', '').strip()
        period = self._report_period(q) if raw else (get_period() if default_to_current else '')
        if raw and not start and not end:
            start = period_to_date(period.split('~', 1)[0])
            if '~' in period:
                end = self._period_month_end(period.split('~', 1)[1])
            else:
                end = self._period_month_end(start)
        if default_to_current and not start and not end:
            start = period_to_date(period)
            end = self._period_month_end(start)
        if start and not end:
            end = start
        if end and not start:
            start = end
        if end < start:
            start, end = end, start
        label = f'{start} 至 {end}' if (start or end) else (period or '全部')
        return period, start, end, label

    def _report_filter_clause(self, period, start, end, column='b.billing_period', service_start_col='b.service_start', service_end_col='b.service_end'):
        if start or end:
            return natural_date_range_filter_clause(start, end, column, service_start_col, service_end_col)
        return period_filter_clause(period, column)

    def _report_filter_query(self, period, start, end, building='', status=''):
        params = []
        if start or end:
            if start:
                params.append(('period_start', start))
            if end:
                params.append(('period_end', end))
        else:
            params.append(('period', period))
        if building:
            params.append(('building', building))
        if status:
            params.append(('status', status))
        return '&amp;'.join(f'{h(k)}={h(v)}' for k, v in params)

    def _report_reconciliation_data(self, period, building='', status='', period_start='', period_end=''):
        db = get_db()
        period_clause, vals = self._report_filter_clause(period, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        cond = [period_clause]
        if building:
            cond.append("(r.building=? OR (?='商场' AND b.commercial_space_id IS NOT NULL))")
            vals.extend([building, building])
        if status:
            if status == 'arrears':
                cond.append("b.status IN ('unpaid','overdue','partial')")
            else:
                cond.append('b.status=?')
                vals.append(status)
        where = ' AND '.join(cond)
        rows = db.execute(f'''SELECT b.*,r.building,r.unit,r.room_number,r.tenant_name tenant,s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,o.name owner_name,o.phone,f.name fee_name,
            COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
            LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
            LEFT JOIN owners o ON b.owner_id=o.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE {where} ORDER BY COALESCE(r.building,'商场'),COALESCE(r.room_number,s.space_no),b.id''', vals).fetchall()
        building_rows = db.execute(f'''SELECT COALESCE(r.building,'商场') building,COUNT(b.id) bill_count,COALESCE(SUM(b.amount),0) amount,
            COALESCE(SUM((SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=b.id)),0) paid
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
            LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
            WHERE {where} GROUP BY COALESCE(r.building,'商场') ORDER BY building''', vals).fetchall()
        db.close()
        total = sum(float(r['amount'] or 0) for r in rows)
        paid = sum(float(r['paid'] or 0) for r in rows)
        due = total - paid
        rate = round(paid / total * 100, 1) if total else 0
        arrears = [r for r in rows if float(r['amount'] or 0) - float(r['paid'] or 0) > 0.001]
        return {'rows': rows, 'building_rows': building_rows, 'total': total, 'paid': paid, 'due': due, 'rate': rate, 'arrears': arrears}

    def _report_waiver_data(self, period, building='', status='', period_start='', period_end=''):
        db = get_db()
        period_clause, vals = self._report_filter_clause(period, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        cond = [period_clause, 'a.new_amount < a.old_amount']
        if building:
            cond.append("(r.building=? OR (?='商场' AND b.commercial_space_id IS NOT NULL))")
            vals.extend([building, building])
        if status:
            if status == 'arrears':
                cond.append("b.status IN ('unpaid','overdue','partial')")
            else:
                cond.append('b.status=?')
                vals.append(status)
        where = ' AND '.join(cond)
        rows = db.execute(f'''SELECT a.id,b.bill_number,COALESCE(r.building,'商场') building,COALESCE(r.room_number,s.space_no) room_number,
            COALESCE(s.merchant_name,s.shop_name,o.name) customer_name,o.phone,COALESCE(f.name,'-') fee_name,
            a.old_amount,a.new_amount,(a.old_amount-a.new_amount) waiver_amount,a.reason,a.approved_by,a.created_at
            FROM bill_adjustments a JOIN bills b ON a.bill_id=b.id
            LEFT JOIN rooms r ON b.room_id=r.id
            LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
            LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE {where}
            ORDER BY a.created_at DESC,a.id DESC''', vals).fetchall()
        db.close()
        return rows

    def _report_status_counts(self, rows):
        counts = {'paid': 0, 'partial': 0, 'unpaid': 0, 'overdue': 0}
        for r in rows:
            st = r['status'] or ''
            if st in counts:
                counts[st] += 1
        open_count = counts['unpaid'] + counts['partial'] + counts['overdue']
        return {**counts, 'open': open_count, 'total': sum(counts.values())}

    def _reports_enterprise_analysis_xlsx(self, q):
        p, period_start, period_end, period_label = self._report_range(q)
        export_period = date_to_period(period_start) if period_start else p
        if '~' in export_period:
            export_period = export_period.split('~', 1)[0]
        data = build_enterprise_analysis_xlsx(get_enterprise_dashboard_metrics(export_period))
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", f"attachment; filename=enterprise_analysis_{export_period}.xlsx")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _reports_reconciliation_csv(self, q):
        p, period_start, period_end, period_label = self._report_range(q)
        building = qs(q, 'building')
        status = qs(q, 'status')
        data = self._report_reconciliation_data(p, building, status, period_start, period_end)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['building','room','owner','phone','fee_type','period','amount','paid','due','status','due_date','bill_number'])
        for r in data['rows']:
            due = float(r['amount'] or 0) - float(r['paid'] or 0)
            writer.writerow([r['building'] or ('商场' if r['commercial_space_id'] else ''), _report_target_label(r), _report_customer_name(r), r['phone'] or '',
                             r['fee_name'] or '', r['billing_period'] or '', m(r['amount']), m(r['paid']), m(due),
                             r['status'] or '', r['due_date'] or '', r['bill_number'] or ''])
        raw = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename=reconciliation_{(period_start or p)}.csv')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _reports_collections_csv(self, q):
        p, period_start, period_end, period_label = self._report_range(q)
        data = self._collection_summary_data(p, period_start, period_end)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date','method','operator','fee_type','count','amount'])
        for r in data['rows']:
            w.writerow([r['day'], r['payment_method'], r['operator'], r['fee_name'], r['cnt'], m(r['amount'])])
        raw = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename=collections_{(period_start or p)}.csv')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _reports_tenants_csv(self, q):
        p, period_start, period_end, period_label = self._report_range(q)
        building = qs(q, 'building')
        status = qs(q, 'status')
        period_clause, vals = self._report_filter_clause(p, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        cond = [period_clause]
        if building:
            cond.append('r.building=?')
            vals.append(building)
        if status:
            if status == 'arrears':
                cond.append("b.status IN ('unpaid','overdue','partial')")
            else:
                cond.append('b.status=?')
                vals.append(status)
        db = get_db()
        rows = db.execute('''SELECT
            COALESCE(NULLIF(b.customer_name_snapshot,''),NULLIF(r.tenant_name,''),NULLIF(r.shop_name,''),o.name,'-') tenant,
            COALESCE(NULLIF(r.shop_name,''),'-') shop,
            r.building,r.unit,r.room_number,COALESCE(NULLIF(r.business_type,''),'-') business_type,
            COALESCE(NULLIF(r.tenant_phone,''),o.phone,'') phone,
            COUNT(b.id) bill_count,COALESCE(SUM(b.amount),0) amount,
            COALESCE(SUM((SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=b.id)),0) paid
            FROM bills b JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            WHERE ''' + ' AND '.join(cond) + '''
            GROUP BY r.id ORDER BY r.building,r.unit,r.room_number''', vals).fetchall()
        db.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['tenant','shop','building','room','business_type','bill_count','amount','paid','due','phone'])
        for r in rows:
            amount = float(r['amount'] or 0)
            paid = float(r['paid'] or 0)
            room = f"{r['unit'] or ''}-{r['room_number'] or ''}".strip('-')
            w.writerow([r['tenant'], r['shop'], r['building'] or '', room, r['business_type'], r['bill_count'], m(amount), m(paid), m(amount - paid), r['phone'] or ''])
        raw = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename=tenants_{(period_start or p)}.csv')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _reports_tenant_arrears_csv(self, q):
        p, period_start, period_end, period_label = self._report_range(q)
        building = qs(q, 'building')
        status = qs(q, 'status')
        period_clause, vals = self._report_filter_clause(p, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        cond = [period_clause]
        if building:
            cond.append('r.building=?')
            vals.append(building)
        if status and status != 'arrears':
            cond.append('b.status=?')
            vals.append(status)
        cond.append("b.status IN ('unpaid','overdue','partial')")
        db = get_db()
        rows = db.execute('''SELECT
            COALESCE(NULLIF(b.customer_name_snapshot,''),NULLIF(r.tenant_name,''),NULLIF(r.shop_name,''),o.name,'-') tenant,
            COALESCE(NULLIF(r.shop_name,''),'-') shop,
            r.building,r.unit,r.room_number,COALESCE(NULLIF(r.business_type,''),'-') business_type,
            COALESCE(NULLIF(r.tenant_phone,''),o.phone,'') phone,
            COUNT(b.id) bill_count,
            COALESCE(SUM(b.amount-COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0)),0) due
            FROM bills b JOIN rooms r ON b.room_id=r.id LEFT JOIN owners o ON b.owner_id=o.id
            WHERE ''' + ' AND '.join(cond) + '''
            GROUP BY r.id HAVING due>0.001 ORDER BY due DESC,r.building,r.unit,r.room_number''', vals).fetchall()
        db.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['tenant','shop','building','room','business_type','bill_count','due','phone'])
        for r in rows:
            room = f"{r['unit'] or ''}-{r['room_number'] or ''}".strip('-')
            w.writerow([r['tenant'], r['shop'], r['building'] or '', room, r['business_type'], r['bill_count'], m(r['due']), r['phone'] or ''])
        raw = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename=tenant_arrears_{(period_start or p)}.csv')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
