from server.reports_shared import *

class ReportMixinPart2(BaseHandler):
    def _reports_fee_arrears_csv(self, q):
        p, period_start, period_end, period_label = self._report_range(q)
        building = qs(q, 'building')
        status = qs(q, 'status')
        period_clause, vals = self._report_filter_clause(p, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        cond = [period_clause, "b.status IN ('unpaid','overdue','partial')"]
        if building:
            cond.append('r.building=?')
            vals.append(building)
        if status and status != 'arrears':
            cond.append('b.status=?')
            vals.append(status)
        db = get_db()
        rows = db.execute('''SELECT COALESCE(f.name,'-') fee_type,COUNT(b.id) bill_count,
            COALESCE(SUM(b.amount-COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0)),0) due
            FROM bills b JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE ''' + ' AND '.join(cond) + '''
            GROUP BY f.id,f.name HAVING due>0.001 ORDER BY due DESC,fee_type''', vals).fetchall()
        db.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['fee_type','bill_count','due'])
        for r in rows:
            w.writerow([r['fee_type'], r['bill_count'], m(r['due'])])
        raw = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename=fee_arrears_{(period_start or p)}.csv')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _collection_summary_data(self, period, period_start='', period_end=''):
        db = get_db()
        period_clause, period_vals = self._report_filter_clause(period, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        rows = db.execute('''SELECT date(p.payment_date) day,p.payment_method,COALESCE(p.operator,'') operator,f.name fee_name,
            COUNT(*) cnt,COALESCE(SUM(p.amount_paid),0) amount
            FROM payments p JOIN bills b ON p.bill_id=b.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE ''' + period_clause + ''' GROUP BY day,p.payment_method,p.operator,f.name
            ORDER BY day DESC,p.payment_method,p.operator,f.name''', period_vals).fetchall()
        totals = db.execute('''SELECT p.payment_method,COUNT(*) cnt,COALESCE(SUM(p.amount_paid),0) amount
            FROM payments p JOIN bills b ON p.bill_id=b.id WHERE ''' + period_clause + '''
            GROUP BY p.payment_method ORDER BY p.payment_method''', period_vals).fetchall()
        db.close()
        return {'rows': rows, 'totals': totals, 'amount': sum(float(r['amount'] or 0) for r in rows)}

    def _arrears_analysis_data(self, period, period_start='', period_end=''):
        db = get_db()
        period_clause, period_vals = self._report_filter_clause(period, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        by_fee = db.execute('''SELECT f.name fee_name,COUNT(b.id) cnt,COALESCE(SUM(b.amount-COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0)),0) due
            FROM bills b LEFT JOIN fee_types f ON b.fee_type_id=f.id
            WHERE ''' + period_clause + ''' AND b.status IN('unpaid','overdue','partial')
            GROUP BY f.name ORDER BY due DESC''', period_vals).fetchall()
        long_due = db.execute('''SELECT COALESCE(s.merchant_name,s.shop_name,o.name) owner_name,o.phone,COALESCE(r.building,'商场') building,COALESCE(r.room_number,s.space_no) room_number,COUNT(b.id) cnt,
            MIN(b.billing_period) first_period,COALESCE(SUM(b.amount-COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0)),0) due
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN owners o ON b.owner_id=o.id
            WHERE b.status IN('unpaid','overdue','partial')
            GROUP BY COALESCE('s'||s.id,'r'||r.id,'o'||o.id) HAVING cnt>=2 OR first_period<?
            ORDER BY due DESC LIMIT 20''', (period,)).fetchall()
        db.close()
        return {'by_fee': by_fee, 'long_due': long_due}

    def _render_reconciliation_section(self, period, data, building='', status='', period_start='', period_end='', period_label=''):
        building_rows = ''.join(
            f'''<tr><td>{h(r["building"])}</td><td class="text-end">{r["bill_count"]}</td>
            <td class="text-end"><span class="money">¥{m(r["amount"])}</span></td>
            <td class="text-end"><span class="money money-paid">¥{m(r["paid"])}</span></td>
            <td class="text-end"><span class="money money-due">¥{m(float(r["amount"] or 0)-float(r["paid"] or 0))}</span></td></tr>'''
            for r in data['building_rows']
        ) or '<tr><td colspan="5" class="text-center text-muted py-3">暂无数据</td></tr>'
        income_rows = ''.join(
            f'''<tr><td>{h(name)}</td><td class="text-end">{vals['count']}</td>
            <td class="text-end"><span class="money">¥{m(vals['amount'])}</span></td>
            <td class="text-end"><span class="money money-paid">¥{m(vals['paid'])}</span></td>
            <td class="text-end"><span class="money money-due">¥{m(vals['amount']-vals['paid'])}</span></td></tr>'''
            for name, vals in _stable_income_breakdown(data['rows']).items()
        )
        arrears_rows = ''.join(
            f'''<tr><td>{h(r["bill_number"] or r["id"])}</td><td>{h(_report_target_label(r))}</td>
            <td>{h(_report_customer_name(r))}</td><td>{h(r["phone"] or "")}</td><td>{h(r["fee_name"] or "")}</td>
            <td class="text-end"><span class="money">¥{m(r["amount"])}</span></td>
            <td class="text-end"><span class="money money-paid">¥{m(r["paid"])}</span></td>
            <td class="text-end"><span class="money money-due">¥{m(float(r["amount"] or 0)-float(r["paid"] or 0))}</span></td></tr>'''
            for r in data['arrears'][:50]
        ) or '<tr><td colspan="8" class="text-center text-muted py-3">本账期无欠费</td></tr>'
        filter_query = self._report_filter_query(period, period_start, period_end, building, status)
        collections = self._collection_summary_data(period, period_start, period_end)
        collection_rows = ''.join(
            f'''<tr><td>{h(r["day"])}</td><td>{h(r["payment_method"])}</td><td>{h(r["operator"] or "-")}</td><td>{h(r["fee_name"] or "-")}</td><td class="text-end">{r["cnt"]}</td><td class="text-end money money-paid">¥{m(r["amount"])}</td></tr>'''
            for r in collections['rows'][:80]
        ) or '<tr><td colspan="6" class="text-center text-muted py-3">暂无收款</td></tr>'
        waivers = self._report_waiver_data(period, building, status, period_start, period_end)
        waiver_rows = ''.join(
            f'''<tr><td>{h(r["created_at"] or "")}</td><td>{h(r["bill_number"] or r["id"])}</td><td>{h(r["building"] or "")}-{h(r["room_number"] or "")}</td>
            <td>{h(r["customer_name"] or "未知")}</td><td>{h(r["fee_name"] or "-")}</td>
            <td class="text-end money">¥{m(r["old_amount"])}</td><td class="text-end money">¥{m(r["new_amount"])}</td>
            <td class="text-end money money-due">¥{m(r["waiver_amount"])}</td><td>{h(r["reason"] or "")}</td><td>{h(r["approved_by"] or "")}</td></tr>'''
            for r in waivers[:100]
        ) or '<tr><td colspan="10" class="text-center text-muted py-3">当前筛选范围内暂无减免记录</td></tr>'
        arrears = self._arrears_analysis_data(period, period_start, period_end)
        arrears_fee_rows = ''.join(f'<tr><td>{h(r["fee_name"] or "-")}</td><td class="text-end">{r["cnt"]}</td><td class="text-end money money-due">¥{m(r["due"])}</td></tr>' for r in arrears['by_fee']) or '<tr><td colspan="3" class="text-center text-muted py-3">暂无欠费</td></tr>'
        long_due_rows = ''.join(
            f'<tr><td>{h(r["owner_name"] or "未知")}</td><td>{h(r["building"])}-{h(r["room_number"])}</td><td>{h(r["first_period"])}</td><td class="text-end">{r["cnt"]}</td><td class="text-end money money-due">¥{m(r["due"])}</td></tr>'
            for r in arrears['long_due']
        ) or '<tr><td colspan="5" class="text-center text-muted py-3">暂无长期欠费</td></tr>'
        return f'''
        <div class="accordion report-fold" id="reportDetailFold">
          <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#reportArrears">欠费清单 <span class="badge status-danger ms-2">{len(data['arrears'])}</span></button></h2>
            <div id="reportArrears" class="accordion-collapse collapse show" data-bs-parent="#reportDetailFold"><div class="accordion-body"><div class="d-flex justify-content-end p-2"><a class="btn btn-sm btn-outline-secondary" href="/reports/arrears_detail.csv?{filter_query}">导出欠费明细CSV</a></div><div class="table-responsive report-compact-table"><table class="table table-hover">
            <thead><tr><th>账单号</th><th>房间</th><th>客户</th><th>电话</th><th>项目</th><th class="text-end">应收</th><th class="text-end">已收</th><th class="text-end">未收</th></tr></thead><tbody>{arrears_rows}</tbody></table></div></div></div></div>
          <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#reportCollection">收款对账明细</button></h2>
            <div id="reportCollection" class="accordion-collapse collapse" data-bs-parent="#reportDetailFold"><div class="accordion-body"><div class="d-flex justify-content-end gap-2 p-2"><a class="btn btn-sm btn-outline-secondary" href="/reports/collections.csv?{filter_query}">导出收款汇总CSV</a><a class="btn btn-sm btn-outline-secondary" href="/reports/payment_detail.csv?{filter_query}">导出收款流水CSV</a></div><div class="table-responsive report-compact-table"><table class="table table-hover"><thead><tr><th>日期</th><th>方式</th><th>操作员</th><th>费用类型</th><th class="text-end">笔数</th><th class="text-end">金额</th></tr></thead><tbody>{collection_rows}</tbody></table></div></div></div></div>
          <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#reportWaivers">减免明细 <span class="badge status-warning ms-2">{len(waivers)}</span></button></h2>
            <div id="reportWaivers" class="accordion-collapse collapse" data-bs-parent="#reportDetailFold"><div class="accordion-body"><div class="d-flex justify-content-end p-2"><a class="btn btn-sm btn-outline-secondary" href="/reports/waivers.csv?{filter_query}">导出减免明细CSV</a></div><div class="table-responsive report-compact-table"><table class="table table-hover"><thead><tr><th>时间</th><th>账单号</th><th>房间/商铺</th><th>客户</th><th>费用项目</th><th class="text-end">原金额</th><th class="text-end">新金额</th><th class="text-end">减免</th><th>原因</th><th>审批人</th></tr></thead><tbody>{waiver_rows}</tbody></table></div></div></div></div>
          <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#reportBuilding">楼栋与收入分类</button></h2>
            <div id="reportBuilding" class="accordion-collapse collapse" data-bs-parent="#reportDetailFold"><div class="accordion-body"><div class="report-section-grid"><div class="table-responsive report-compact-table"><table class="table table-hover"><thead><tr><th>楼栋</th><th class="text-end">账单</th><th class="text-end">应收</th><th class="text-end">已收</th><th class="text-end">未收</th></tr></thead><tbody>{building_rows}</tbody></table></div><div class="table-responsive report-compact-table"><table class="table table-hover"><thead><tr><th>收入分类</th><th class="text-end">账单</th><th class="text-end">应收</th><th class="text-end">已收</th><th class="text-end">未收</th></tr></thead><tbody>{income_rows}</tbody></table></div></div></div></div></div>
          <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#reportRisk">欠费分析</button></h2>
            <div id="reportRisk" class="accordion-collapse collapse" data-bs-parent="#reportDetailFold"><div class="accordion-body"><div class="report-section-grid"><div class="table-responsive report-compact-table"><table class="table table-hover"><thead><tr><th>项目</th><th class="text-end">笔数</th><th class="text-end">欠费</th></tr></thead><tbody>{arrears_fee_rows}</tbody></table></div><div class="table-responsive report-compact-table"><table class="table table-hover"><thead><tr><th>客户</th><th>房间</th><th>最早账期</th><th class="text-end">笔数</th><th class="text-end">欠费</th></tr></thead><tbody>{long_due_rows}</tbody></table></div></div></div></div></div>
        </div>'''

    def _reports_reconciliation_print(self, q):
        period, period_start, period_end, period_label = self._report_range(q)
        building = qs(q, 'building')
        status = qs(q, 'status')
        data = self._report_reconciliation_data(period, building, status, period_start, period_end)
        status_counts = self._report_status_counts(data['rows'])
        status_label = {'unpaid':'未缴','partial':'部分缴费','paid':'已缴','arrears':'全部欠费','':'全部状态'}.get(status, status)
        row_parts = []
        for r in data['rows']:
            due = float(r['amount'] or 0) - float(r['paid'] or 0)
            row_parts.append(
                f'<tr><td>{h(r["bill_number"] or r["id"])}</td><td>{h(r["building"])}-{h(r["room_number"])}</td>'
                f'<td>{h(r["owner_name"] or "未知")}</td><td>{h(r["phone"] or "")}</td><td>{h(r["fee_name"] or "")}</td>'
                f'<td class="amt">{m(r["amount"])}</td><td class="amt">{m(r["paid"])}</td><td class="amt">{m(due)}</td></tr>'
            )
        rows = ''.join(row_parts) or '<tr><td colspan="8" class="muted">暂无数据</td></tr>'
        back = '/reports?' + self._report_filter_query(period, period_start, period_end, building, status).replace('&amp;', '&')
        from server.print_helper import print_page
        body = f'''
        <style>
        .recon-summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}}
        .recon-box{{border:1px solid #ccc;padding:10px;text-align:center}} .recon-box strong{{display:block;font-size:18px;margin-top:4px}}
        .recon-status-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}}
        .recon-section-title{{font-weight:700;margin:14px 0 8px;border-left:4px solid #111;padding-left:8px}}
        .recon-table{{width:100%;border-collapse:collapse;font-size:12px}}
        .recon-table th,.recon-table td{{border:1px solid #999;padding:6px}} .recon-table th{{background:#f2f2f2}}
        .recon-table .amt{{text-align:right}} .recon-table .muted{{text-align:center;color:#777}}
        .recon-meta{{text-align:center;color:#555;margin-bottom:18px}}
        </style>
        <h1>对账单打印</h1><div class="recon-meta">日期范围：{h(period_label)}　楼栋：{h(building or '全部')}　状态：{h(status_label)}</div>
        <div class="recon-summary"><div class="recon-box">应收合计<strong>{m(data['total'])}</strong></div><div class="recon-box">已收合计<strong>{m(data['paid'])}</strong></div><div class="recon-box">未收合计<strong>{m(data['due'])}</strong></div><div class="recon-box">收缴率<strong>{data['rate']}%</strong></div></div>
        <div class="recon-section-title">账单状态分布</div>
        <div class="recon-status-grid"><div class="recon-box">已缴账单<strong>{status_counts['paid']}</strong></div><div class="recon-box">部分缴费<strong>{status_counts['partial']}</strong></div><div class="recon-box">未缴账单<strong>{status_counts['unpaid'] + status_counts['overdue']}</strong></div><div class="recon-box">本期回款缺口<strong>{m(data['due'])}</strong></div></div>
        <table class="recon-table"><thead><tr><th>账单号</th><th>房间</th><th>业主</th><th>电话</th><th>项目</th><th>应收</th><th>已收</th><th>未收</th></tr></thead><tbody>{rows}</tbody></table>'''
        self._html(print_page('对账单打印', body, show_back=True, back_url=back))
