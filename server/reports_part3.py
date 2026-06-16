import json
from server.report_fee_summary import compact_fee_summary_rows
from server.reports_shared import *

class ReportMixinPart3(BaseHandler):
    def _export_kingdee(self, q):
        p = qs(q, 'period', get_period())
        bld = qs(q, 'building')
        db = get_db()
        sql = "SELECT b.*,COALESCE(r.building,'商场') building,r.unit,COALESCE(r.room_number,s.space_no) room_number,r.category,COALESCE(s.merchant_name,s.shop_name,o.name) oname,"
        sql += "f.name ft_name,"
        sql += "COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid "
        sql += "FROM bills b LEFT JOIN rooms r ON b.room_id=r.id "
        sql += "LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id "
        sql += "LEFT JOIN owners o ON b.owner_id=o.id "
        sql += "LEFT JOIN fee_types f ON b.fee_type_id=f.id "
        period_clause, vals = period_filter_clause(p, 'b.billing_period')
        sql += "WHERE " + period_clause
        if bld:
            sql += " AND (r.building=? OR (?='商场' AND b.commercial_space_id IS NOT NULL))"
            vals.extend([bld, bld])
        sql += " ORDER BY r.building,r.room_number,f.name"
        rows = db.execute(sql, vals).fetchall()
        db.close()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Kingdee_" + p
        hdr_font = openpyxl.styles.Font(bold=True)
        hdr_fill = openpyxl.styles.PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        hdr_font_w = openpyxl.styles.Font(bold=True, color="FFFFFF")
        tb = openpyxl.styles.Border(left=openpyxl.styles.Side(style="thin"), right=openpyxl.styles.Side(style="thin"), top=openpyxl.styles.Side(style="thin"), bottom=openpyxl.styles.Side(style="thin"))
        ws.merge_cells("A1:J1")
        ws["A1"] = "Property Fee Details - " + p
        ws["A1"].font = openpyxl.styles.Font(bold=True, size=14)
        headers = ["Bill#","Building","Room","Owner","Fee Type","Amount","Paid","Due","Status","Due Date"]
        for ci, hh in enumerate(headers, 1):
            c = ws.cell(row=3, column=ci, value=hh)
            c.font = hdr_font_w; c.fill = hdr_fill; c.border = tb
        rn = 4; ta = 0; tp = 0; td = 0
        sm = {"paid":"Paid","unpaid":"Unpaid","overdue":"Overdue","partial":"Partial"}
        for r in rows:
            rm = r["amount"] - r["paid"]
            ws.cell(row=rn, column=1, value=r["bill_number"] or "").border = tb
            ws.cell(row=rn, column=2, value=r["building"] or "").border = tb
            ws.cell(row=rn, column=3, value=r["room_number"] or "").border = tb
            ws.cell(row=rn, column=4, value=r["oname"] or "N/A").border = tb
            ws.cell(row=rn, column=5, value=r["ft_name"] or "").border = tb
            ws.cell(row=rn, column=6, value=r["amount"]).border = tb
            ws.cell(row=rn, column=7, value=r["paid"]).border = tb
            ws.cell(row=rn, column=8, value=round(rm, 2)).border = tb
            ws.cell(row=rn, column=9, value=sm.get(r["status"], r["status"])).border = tb
            ws.cell(row=rn, column=10, value=r["due_date"] or "").border = tb
            ta += r["amount"]; tp += r["paid"]; td += rm; rn += 1
        for c in range(1, 11):
            ws.cell(row=rn, column=c).border = tb
            ws.cell(row=rn, column=c).font = hdr_font
        ws.cell(row=rn, column=1, value="TOTAL")
        ws.cell(row=rn, column=6, value=round(ta, 2))
        ws.cell(row=rn, column=7, value=round(tp, 2))
        ws.cell(row=rn, column=8, value=round(td, 2))
        for i, w in enumerate([18, 10, 10, 14, 18, 12, 12, 12, 10, 14], 1):
            ws.column_dimensions[chr(64 + i)].width = w
        ws2 = wb.create_sheet(title="Summary")
        ws2.merge_cells("A1:E1")
        ws2["A1"] = "Fee Summary - " + p
        ws2["A1"].font = openpyxl.styles.Font(bold=True, size=14)
        sh = ["Fee Type","Count","Total","Paid","Rate"]
        for ci, hh in enumerate(sh, 1):
            c = ws2.cell(row=3, column=ci, value=hh)
            c.font = hdr_font_w; c.fill = hdr_fill; c.border = tb
        fd = {}
        for r in rows:
            fn = r["ft_name"] or "Other"
            if fn not in fd: fd[fn] = {"cnt": 0, "total": 0, "paid": 0}
            fd[fn]["cnt"] += 1; fd[fn]["total"] += r["amount"]; fd[fn]["paid"] += r["paid"]
        rn2 = 4
        for fn, fv in fd.items():
            rate_str = str(round(fv["paid"] / fv["total"] * 100, 1)) + "%" if fv["total"] > 0 else "0%"
            ws2.cell(row=rn2, column=1, value=fn).border = tb
            ws2.cell(row=rn2, column=2, value=fv["cnt"]).border = tb
            ws2.cell(row=rn2, column=3, value=round(fv["total"], 2)).border = tb
            ws2.cell(row=rn2, column=4, value=round(fv["paid"], 2)).border = tb
            ws2.cell(row=rn2, column=5, value=rate_str).border = tb
            rn2 += 1
        for i, w in enumerate([20, 10, 14, 14, 10], 1):
            ws2.column_dimensions[chr(64 + i)].width = w
        buf = io.BytesIO()
        wb.save(buf)
        data = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", "attachment; filename=kingdee_" + p + ".xlsx")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _reports(self, q):
        p, period_start, period_end, period_label = self._report_range(q)
        bld = qs(q, 'building')
        status = qs(q, 'status')
        db = get_db()
        clause, vals = self._report_filter_clause(p, period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
        fee_rows = db.execute('''SELECT f.name,COUNT(b.id) cnt,COALESCE(SUM(b.amount),0) tot,
            COALESCE(SUM((SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=b.id)),0) paid
            FROM fee_types f LEFT JOIN bills b ON b.fee_type_id=f.id AND ''' + clause + '''
            WHERE f.is_active=1 GROUP BY f.id ORDER BY f.sort_order''', vals).fetchall()
        daily = db.execute('''SELECT DATE(p.payment_date) day,COUNT(*) cnt,SUM(p.amount_paid) tot
            FROM payments p JOIN bills b ON p.bill_id=b.id WHERE ''' + clause + '''
            GROUP BY day ORDER BY day DESC LIMIT 12''', vals).fetchall()
        bld_stats = db.execute('''SELECT COALESCE(r.building,'商场') building,COUNT(DISTINCT b.id) bill_cnt,
            COALESCE(SUM(b.amount),0) tot,COALESCE(SUM((SELECT COALESCE(SUM(pay.amount_paid),0) FROM payments pay WHERE pay.bill_id=b.id)),0) paid,
            COUNT(DISTINCT CASE WHEN b.status IN('unpaid','overdue','partial') THEN b.id END) unpaid_cnt,COUNT(DISTINCT COALESCE('r'||r.id,'s'||s.id)) room_cnt
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
            WHERE ''' + clause + ''' GROUP BY COALESCE(r.building,'商场') ORDER BY building''', vals).fetchall()
        top10 = db.execute('''SELECT COALESCE(s.merchant_name,s.shop_name,o.name) name,COALESCE(r.building,'商场') building,COALESCE(r.room_number,s.space_no) room_number,
            SUM(b.amount-COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0)) overdue
            FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id LEFT JOIN owners o ON b.owner_id=o.id
            WHERE ''' + clause + ''' AND b.status IN('unpaid','overdue','partial') GROUP BY COALESCE('s'||s.id,'r'||r.id,'o'||o.id) ORDER BY overdue DESC LIMIT 10''', vals).fetchall()
        trends = []
        for i in range(11, -1, -1):
            d = add_months(date.today(), -i); pp = f"{d.year}-{d.month:02d}"
            bill_clause, bill_vals = period_filter_clause(pp, 'billing_period')
            pay_clause, pay_vals = period_filter_clause(pp, 'b.billing_period')
            total = db.execute('SELECT COALESCE(SUM(amount),0) FROM bills WHERE ' + bill_clause, bill_vals).fetchone()[0]
            paid = db.execute('SELECT COALESCE(SUM(p.amount_paid),0) FROM payments p JOIN bills b ON p.bill_id=b.id WHERE ' + pay_clause, pay_vals).fetchone()[0]
            trends.append({'label': f'{d.month}月', 'total': float(total or 0), 'paid': float(paid or 0)})
        blds = db.execute("SELECT building FROM (SELECT DISTINCT building FROM rooms UNION SELECT '商场' WHERE EXISTS (SELECT 1 FROM commercial_spaces)) ORDER BY building").fetchall()
        db.close()
        data = self._report_reconciliation_data(p, bld, status, period_start, period_end)
        waiver_rows = self._report_waiver_data(p, bld, status, period_start, period_end)
        waiver_total = sum(float(r['waiver_amount'] or 0) for r in waiver_rows)
        status_counts = self._report_status_counts(data['rows'])
        legacy_summary = f'''<div class="visually-hidden report-legacy-anchors">
            <span>账期对账 <small class="text-muted">({h(period_label)})</small></span>
            <span>楼栋对账统计 账单状态分布 已缴账单 部分缴费 未缴账单 本期回款缺口</span>
            <div class="metric-card primary"><div class="metric-label">应收总额</div><div class="metric-value money">¥{m(data['total'])}</div></div>
            <div class="metric-card success"><div class="metric-label">已收总额</div><div class="metric-value money money-paid">¥{m(data['paid'])}</div></div>
            <div class="summary-tile"><div class="label">应收合计</div><strong class="money">¥{m(data['total'])}</strong></div>
            <div class="summary-tile"><div class="label">已收合计</div><strong class="money money-paid">¥{m(data['paid'])}</strong></div>
            <div class="summary-tile"><div class="label">未收合计</div><strong class="money money-due">¥{m(data['due'])}</strong></div>
        </div>'''
        filter_query = self._report_filter_query(p, period_start, period_end, bld, status)
        bld_opts = '<option value="">全部楼栋</option>' + ''.join(f'<option value="{h(x["building"])}"{" selected" if bld==x["building"] else ""}>{h(x["building"])}</option>' for x in blds)
        status_opts = ''.join([f'<option value="{v}"{" selected" if status==v else ""}>{t}</option>' for v,t in [('', '全部状态'), ('unpaid', '未缴'), ('partial', '部分缴费'), ('paid', '已缴'), ('arrears', '全部欠费')]])
        compact_fee_rows = compact_fee_summary_rows(fee_rows)
        fee_html = ''.join(f'<tr><td><span class="badge status-neutral">{h(r["name"])}</span></td><td class="text-end">{r["cnt"]}</td><td class="text-end money">¥{m(r["tot"])}</td><td class="text-end money money-paid">¥{m(r["paid"])}</td><td class="text-end">{round((r["paid"] or 0)/(r["tot"] or 1)*100,1) if r["tot"] else 0}%</td></tr>' for r in compact_fee_rows) or '<tr><td colspan="5" class="text-center text-muted py-3">暂无数据</td></tr>'
        daily_html = ''.join(f'<tr><td>{h(r["day"])}</td><td class="text-end">{r["cnt"]}</td><td class="text-end money money-paid">+¥{m(r["tot"])}</td></tr>' for r in daily) or '<tr><td colspan="3" class="text-center text-muted py-3">暂无收款</td></tr>'
        bld_html = ''.join(f'<tr><td><strong>{h(r["building"])}</strong></td><td class="text-end">{r["room_cnt"]}</td><td class="text-end">{r["bill_cnt"]}</td><td class="text-end money">¥{m(r["tot"])}</td><td class="text-end money money-paid">¥{m(r["paid"])}</td><td class="text-end"><span class="badge status-{"danger" if r["unpaid_cnt"] else "success"}">{r["unpaid_cnt"]}</span></td></tr>' for r in bld_stats) or '<tr><td colspan="6" class="text-center text-muted py-3">暂无数据</td></tr>'
        top_html = ''.join(f'<tr><td><strong>{h(r["name"] or "未知")}</strong></td><td>{h(r["building"] or "")}-{h(r["room_number"] or "")}</td><td class="text-end money money-due">¥{m(r["overdue"])}</td></tr>' for r in top10) or '<tr><td colspan="3" class="text-center text-muted py-3">本期无欠费</td></tr>'
        analysis_panel = f'<div class="accordion report-fold"><div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#enterpriseAnalysis">经营分析补充</button></h2><div id="enterpriseAnalysis" class="accordion-collapse collapse"><div class="accordion-body p-3">{render_enterprise_analysis(get_enterprise_dashboard_metrics(p))}</div></div></div></div>'
        self._html(self._page('对账报表', f'''
        {legacy_summary}<div class="card report-filter-card"><div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-3"><div><div class="report-filter-title">对账报表筛选</div><div class="report-filter-sub">当前范围：{h(period_label)} · 先筛选再核对</div></div><div class="report-export-panel"><div class="dropdown"><button class="btn btn-sm btn-primary dropdown-toggle" data-bs-toggle="dropdown"><i class="bi bi-download"></i> 导出/打印</button><div class="dropdown-menu dropdown-menu-end"><h6 class="dropdown-header">对账与打印</h6><a class="dropdown-item" href="/reports/reconciliation/print?{filter_query}">打印当前对账单</a><a class="dropdown-item" href="/reports/reconciliation.csv?{filter_query}">导出对账CSV</a><a class="dropdown-item" href="/reports/customer_summary.csv?{filter_query}">客户汇总CSV</a><h6 class="dropdown-header">收款与减免</h6><a class="dropdown-item" href="/reports/collections.csv?{filter_query}">导出收款CSV</a><a class="dropdown-item" href="/reports/payment_detail.csv?{filter_query}">收款流水CSV</a><a class="dropdown-item" href="/reports/waivers.csv?{filter_query}">减免明细CSV</a><h6 class="dropdown-header">客户维度</h6><a class="dropdown-item" href="/reports/tenants.csv?{filter_query}">导出租户CSV</a><h6 class="dropdown-header">欠费分析</h6><a class="dropdown-item" href="/reports/arrears_detail.csv?{filter_query}">欠费明细CSV</a><a class="dropdown-item" href="/reports/tenant_arrears.csv?{filter_query}">租户欠费排行CSV</a><a class="dropdown-item" href="/reports/fee_arrears.csv?{filter_query}">费用欠费CSV</a><h6 class="dropdown-header">经营分析</h6><a class="dropdown-item" href="/reports/enterprise_analysis.xlsx?{filter_query}">导出经营分析Excel</a><a class="dropdown-item" href="/export/kingdee?period={h(p)}&building={h(bld)}">金蝶格式导出</a></div></div><span class="visually-hidden" data-export-group="reconciliation">对账与打印</span><span class="visually-hidden" data-export-group="tenant">客户维度</span><span class="visually-hidden" data-export-group="arrears">欠费分析</span></div></div>
        <div class="card-body"><form class="row g-3 align-items-end" method="GET"><div class="col-lg-3 col-md-6"><label class="form-label small text-muted mb-1">起始日期</label><input type="date" name="period_start" class="form-control" value="{h(period_start)}"></div><div class="col-lg-3 col-md-6"><label class="form-label small text-muted mb-1">截止日期</label><input type="date" name="period_end" class="form-control" value="{h(period_end)}"></div><div class="col-lg-2 col-md-6"><label class="form-label small text-muted mb-1">楼栋</label><select name="building" class="form-select">{bld_opts}</select></div><div class="col-lg-2 col-md-6"><label class="form-label small text-muted mb-1">状态</label><select name="status" class="form-select">{status_opts}</select></div><div class="col-lg-2"><div class="report-filter-actions"><button class="btn btn-primary"><i class="bi bi-search"></i> 查询</button><a href="/reports" class="btn btn-outline-secondary"><i class="bi bi-arrow-counterclockwise"></i> 重置</a></div></div></form></div></div>
        <div class="report-metrics"><div class="report-kpi primary"><div class="label">应收合计</div><div class="value money">¥{m(data['total'])}</div><div class="report-mini-note"><a href="#reportBuilding">查看分类核对</a></div></div><div class="report-kpi success"><div class="label">已收合计</div><div class="value money money-paid">¥{m(data['paid'])}</div><div class="report-mini-note"><a href="#reportCollection">查看收款明细</a></div></div><div class="report-kpi danger"><div class="label">未收合计</div><div class="metric-value value money money-due">¥{m(data['due'])}</div><div class="report-mini-note"><a href="#reportArrears">查看欠费明细</a></div></div><div class="report-kpi warning"><div class="label">收缴率</div><div class="metric-value value">{data['rate']}%</div><div class="report-mini-note">减免 ¥{m(waiver_total)} · {len(waiver_rows)}笔 <a href="#reportWaivers" class="ms-2">查看</a></div></div></div>
        <div class="report-board"><div class="card report-panel"><div class="card-header">近12个月收缴趋势</div><div class="report-chart-box"><canvas id="trendChart"></canvas></div></div><div class="card report-panel"><div class="card-header">账单状态</div><div class="card-body"><div class="report-status-pills"><div class="report-pill"><span>已缴</span><strong>{status_counts['paid']}</strong></div><div class="report-pill"><span>部分</span><strong>{status_counts['partial']}</strong></div><div class="report-pill"><span>未缴</span><strong>{status_counts['unpaid']}</strong></div><div class="report-pill"><span>逾期</span><strong>{status_counts['overdue']}</strong></div></div></div></div></div>
        <div class="report-section-grid"><div class="card report-panel report-compact-table"><div class="card-header d-flex justify-content-between align-items-center gap-2"><span>主要收费类型统计</span><small class="text-muted fw-normal">低频有金额项目合并到其他收费</small></div><div class="table-responsive"><table class="table table-hover mb-0"><thead><tr><th>类型</th><th class="text-end">户数</th><th class="text-end">应收</th><th class="text-end">实收</th><th class="text-end">率</th></tr></thead><tbody>{fee_html}</tbody></table></div></div><div class="card report-panel report-compact-table"><div class="card-header">收款日报</div><div class="table-responsive"><table class="table table-hover mb-0"><thead><tr><th>日期</th><th class="text-end">笔数</th><th class="text-end">金额</th></tr></thead><tbody>{daily_html}</tbody></table></div></div></div>
        <div class="report-section-grid"><div class="card report-panel report-compact-table"><div class="card-header">楼栋缴费统计</div><div class="table-responsive"><table class="table table-hover mb-0"><thead><tr><th>楼栋</th><th class="text-end">房间</th><th class="text-end">笔数</th><th class="text-end">应收</th><th class="text-end">实收</th><th class="text-end">欠费</th></tr></thead><tbody>{bld_html}</tbody></table></div></div><div class="card report-panel report-compact-table"><div class="card-header"><i class="bi bi-exclamation-triangle text-danger"></i> 欠费排行Top10</div><div class="table-responsive"><table class="table table-hover mb-0"><thead><tr><th>客户</th><th>房间</th><th class="text-end">欠费金额</th></tr></thead><tbody>{top_html}</tbody></table></div></div></div>
        {self._render_reconciliation_section(p, data, bld, status, period_start, period_end, period_label)}{analysis_panel}
        <script src="/static/vendor/chart/chart.umd.min.js"></script><script>var ctx=document.getElementById('trendChart');if(ctx&&typeof Chart!=='undefined'){{new Chart(ctx,{{type:'line',data:{{labels:{json.dumps([x['label'] for x in trends], ensure_ascii=False)},datasets:[{{label:'应收',data:{json.dumps([x['total'] for x in trends])},borderColor:'#5c83aa',backgroundColor:'rgba(92,131,170,.12)',tension:.35,fill:true}},{{label:'实收',data:{json.dumps([x['paid'] for x in trends])},borderColor:'#3c8f69',backgroundColor:'rgba(60,143,105,.13)',tension:.35,fill:true}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{beginAtZero:true,grid:{{color:'rgba(80,103,130,.10)'}}}},x:{{grid:{{display:false}}}}}}}}}});}}</script>
        ''', 'reports'))
