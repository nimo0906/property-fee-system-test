#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Home page dashboard — clean, chart-driven overview."""

from server.db import get_db, get_period, add_months, h, m, qs, update_overdue_bills, period_to_date
from server.base import BaseHandler
from datetime import date
import json


class IndexMixin(BaseHandler):

    def _index(self):
        update_overdue_bills()
        db = get_db()
        p = get_period()
        tr = db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        to = db.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
        tu = db.execute("SELECT COUNT(*) FROM bills WHERE billing_period=? AND status IN('unpaid','overdue')", (p,)).fetchone()[0]
        ta = db.execute("SELECT COALESCE(SUM(amount),0) FROM bills WHERE billing_period=?", (p,)).fetchone()[0]
        tp = db.execute("SELECT COALESCE(SUM(p.amount_paid),0) FROM payments p JOIN bills b ON p.bill_id=b.id WHERE b.billing_period=?", (p,)).fetchone()[0]
        rate = round(tp / ta * 100, 1) if ta > 0 else 0

        # 本月每日收款趋势：按实际 payment_date 实时汇总，收费登记后刷新即变动。
        y, mo = [int(x) for x in p.split('-')]
        first_day = date(y, mo, 1)
        next_month = add_months(first_day, 1)
        days = (next_month - first_day).days
        paid_by_day = {
            r['day']: float(r['paid'] or 0)
            for r in db.execute("""SELECT strftime('%d', payment_date) day,COALESCE(SUM(amount_paid),0) paid
                FROM payments WHERE strftime('%Y-%m', payment_date)=? GROUP BY day""", (p,)).fetchall()
        }
        trends = []
        for day in range(1, days + 1):
            key = f"{day:02d}"
            trends.append({'label': f"{day}日", 'paid': paid_by_day.get(key, 0.0)})

        today_paid = db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE date(payment_date)=date('now','localtime')"
        ).fetchone()[0]
        month_due = float(ta or 0) - float(tp or 0)
        pending_cnt = db.execute(
            "SELECT COUNT(*) FROM bills WHERE billing_period=? AND status IN('unpaid','overdue','partial')",
            (p,)
        ).fetchone()[0]
        today = date.today().isoformat()
        expiring_contracts = db.execute("""SELECT r.*,o.name owner_name FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
            WHERE r.contract_end IS NOT NULL AND r.contract_end<>'' AND r.contract_end BETWEEN ? AND date(?, '+30 days')
            ORDER BY r.contract_end LIMIT 8""", (today, today)).fetchall()
        expired_contract_count = db.execute("SELECT COUNT(*) FROM rooms WHERE contract_end IS NOT NULL AND contract_end<>'' AND contract_end < ?", (today,)).fetchone()[0]
        meter_needed = db.execute("""SELECT COUNT(*) FROM fee_types f WHERE f.is_active=1 AND f.calc_method='meter'
            AND NOT EXISTS (SELECT 1 FROM meter_readings m WHERE m.fee_type_id=f.id AND m.period=replace(?, '-', '') AND m.status='confirmed')""", (p,)).fetchone()[0]
        overdue_cnt = db.execute(
            "SELECT COUNT(*) FROM bills WHERE billing_period=? AND status='overdue'",
            (p,)
        ).fetchone()[0]
        today_payment_cnt = db.execute(
            "SELECT COUNT(*) FROM payments WHERE date(payment_date)=date('now','localtime')"
        ).fetchone()[0]
        invoice_todo_cnt = db.execute("""SELECT COUNT(*) FROM bills b
            WHERE b.status='paid' AND b.id NOT IN (SELECT bill_id FROM invoices)
            AND b.id NOT IN (SELECT bill_id FROM invoice_requests WHERE status IN('pending','submitted','issued'))""").fetchone()[0]
        zero_amount_cnt = db.execute(
            "SELECT COUNT(*) FROM bills WHERE billing_period=? AND amount<=0",
            (p,)
        ).fetchone()[0]

        # 待收费账单
        pending_bills = db.execute(
            """SELECT b.*,r.building,r.unit,r.room_number,o.name owner_name,f.name ft,
               COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
               FROM bills b
               LEFT JOIN rooms r ON b.room_id=r.id
               LEFT JOIN owners o ON b.owner_id=o.id
               LEFT JOIN fee_types f ON b.fee_type_id=f.id
               WHERE b.billing_period=? AND b.status IN('unpaid','overdue','partial')
               ORDER BY CASE b.status WHEN 'overdue' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END,b.due_date,r.building,r.room_number
               LIMIT 8""",
            (p,)
        ).fetchall()

        # 各收费项目
        fts = db.execute(
            "SELECT f.name,COUNT(b.id) cnt,COALESCE(SUM(b.amount),0) tot FROM fee_types f LEFT JOIN bills b ON b.fee_type_id=f.id AND b.billing_period=? WHERE f.is_active=1 GROUP BY f.id ORDER BY f.sort_order", (p,)
        ).fetchall()
        fs = ''.join(
            f'<tr><td><span class="badge status-neutral">{h(f["name"])}</span></td><td class="text-end"><span class="money">¥{m(f["tot"])}</span></td><td class="text-end">{f["cnt"]}笔</td></tr>'
            for f in fts
        )

        db.close()

        role = (self._get_current_user() or {}).get('role')
        can_write = role != 'readonly'

        pending_rows = ''.join(
            f'''<tr><td><small>{h(b["bill_number"]or"-")}</small></td>
            <td>{h(b["building"]or"")}-{h(b["unit"]or"")}-{h(b["room_number"]or"")}</td>
            <td>{h(b["owner_name"] or "-")}</td>
            <td><span class="badge status-info">{h(b["ft"])}</span></td>
            <td class="text-end"><span class="money money-due">¥{m(float(b["amount"] or 0)-float(b["paid"] or 0))}</span></td>
            <td>{f'<a href="/bills/{b["id"]}/pay" class="btn btn-sm btn-outline-success">收费登记</a>' if can_write else '<a href="/bills" class="btn btn-sm btn-outline-primary">查看账单</a>'}</td></tr>'''
            for b in pending_bills
        )

        contract_rows = ''.join(
            f'''<tr><td>{h(r["building"])}-{h(r["room_number"])}</td><td>{h(r["owner_name"] or "-")}</td><td>{h(r["contract_end"] or "-")}</td><td><a class="btn btn-sm btn-outline-primary" href="/rooms/{r["id"]}/edit">处理</a></td></tr>'''
            for r in expiring_contracts
        ) or '<tr><td colspan="4" class="text-center text-muted py-3">30天内暂无到期合同</td></tr>'

        trends_json = json.dumps(trends, ensure_ascii=False)

        first_run_steps = '''
                    <div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/import/template/basic.csv" download="basic_info_template.csv">1 下载导入模板</a></div>
                    <div class="col-md-2"><a class="btn btn-outline-primary w-100" href="/import">2 导入基础资料</a></div>
                    <div class="col-md-2"><a class="btn btn-outline-secondary w-100" href="/fee_types">3 设置收费项目</a></div>
                    <div class="col-md-2"><a class="btn btn-outline-success w-100" href="/bills/generate">4 生成账单</a></div>
                    <div class="col-md-2"><a class="btn btn-outline-success w-100" href="/billing">5 收费登记</a></div>
                    <div class="col-md-2"><a class="btn btn-outline-info w-100" href="/reports">6 对账报表</a></div>''' if can_write else '''
                    <div class="col-md-3"><a class="btn btn-outline-primary w-100" href="/bills">1 查看账单</a></div>
                    <div class="col-md-3"><a class="btn btn-outline-primary w-100" href="/collections">2 客服催费对象</a></div>
                    <div class="col-md-3"><a class="btn btn-outline-primary w-100" href="/reports">3 对账报表</a></div>
                    <div class="col-md-3"><a class="btn btn-outline-secondary w-100" href="/owners">4 核对业主资料</a></div>'''
        first_run_note = '建议先按模板整理楼栋、房号、楼层、业主、合同日期等基础资料，再生成账单。' if can_write else '客服只读账号用于查看账单、跟进催费和核对资料，不显示生成账单或收费登记入口。'
        primary_actions = '''
                <a href="/bills/generate" class="btn btn-primary btn-sm"><i class="bi bi-file-earmark-plus"></i> 生成账单</a>
                <a href="/billing" class="btn btn-success btn-sm"><i class="bi bi-cash-coin"></i> 收费登记</a>
                <a href="/bills" class="btn btn-outline-secondary btn-sm"><i class="bi bi-printer"></i> 打印收据</a>
                <a href="/reports" class="btn btn-outline-primary btn-sm"><i class="bi bi-graph-up"></i> 对账报表</a>
                <a href="/invoices" class="btn btn-outline-secondary btn-sm"><i class="bi bi-receipt-cutoff"></i> 发票管理</a>''' if can_write else '''
                <a href="/collections" class="btn btn-primary btn-sm"><i class="bi bi-telephone-outbound"></i> 客服催费对象</a>
                <a href="/bills" class="btn btn-outline-primary btn-sm"><i class="bi bi-receipt"></i> 账单管理</a>
                <a href="/reports" class="btn btn-outline-primary btn-sm"><i class="bi bi-graph-up"></i> 对账报表</a>'''
        # 顶部标题栏已经提供主操作按钮，首页右侧不再重复展示快捷按钮。

        first_run = f'''
        <div class="card border-primary">
            <div class="card-header text-primary"><i class="bi bi-signpost-2"></i> 首次使用建议流程</div>
            <div class="card-body">
                <div class="row g-2 text-center">
                    {first_run_steps}
                </div>
                <p class="small text-muted mt-3 mb-0">{first_run_note}</p>
            </div>
        </div>'''

        todo_cards = f'''
        <div class="card">
            <div class="card-header py-2"><i class="bi bi-lightning-charge"></i> 待办中心</div>
            <div class="card-body">
                <div class="row g-2">
                    <div class="col-md-2 col-6"><a class="summary-tile d-block text-decoration-none" href="/reminders?status=overdue&period={period_to_date(p)}"><div class="label">逾期未收</div><strong>{overdue_cnt}</strong><span class="text-muted small"> 笔</span></a></div>
                    <div class="col-md-2 col-6"><a class="summary-tile d-block text-decoration-none" href="/bills?status=unpaid&period={period_to_date(p)}"><div class="label">待收费</div><strong>{pending_cnt}</strong><span class="text-muted small"> 笔</span></a></div>
                    <div class="col-md-2 col-6"><a class="summary-tile d-block text-decoration-none" href="/reports?period={period_to_date(p)}"><div class="label">本月收缴率</div><strong>{rate}%</strong></a></div>
                    <div class="col-md-2 col-6"><a class="summary-tile d-block text-decoration-none" href="/payments"><div class="label">今日收款</div><strong>{today_payment_cnt}</strong><span class="text-muted small"> 笔</span></a></div>
                    <div class="col-md-2 col-6"><a class="summary-tile d-block text-decoration-none" href="/invoices"><div class="label">待开票缴费</div><strong>{invoice_todo_cnt}</strong><span class="text-muted small"> 笔</span></a></div>
                    <div class="col-md-2 col-6"><a class="summary-tile d-block text-decoration-none" href="/auto_billing?preview_status=expiring"><div class="label">即将到期合同</div><strong>{len(expiring_contracts)}</strong><span class="text-muted small"> 户</span></a></div>
                </div>
            </div>
        </div>'''
        exception_cards = f'''
        <div class="card border-warning">
            <div class="card-header py-2 text-warning"><i class="bi bi-exclamation-triangle"></i> 异常提醒</div>
            <div class="card-body">
                <div class="row g-2">
                    <div class="col-md-3 col-6"><a class="summary-tile d-block text-decoration-none" href="/bills?period={period_to_date(p)}&keyword=0"><div class="label">零金额账单</div><strong>{zero_amount_cnt}</strong><span class="text-muted small"> 笔</span></a></div>
                    <div class="col-md-3 col-6"><a class="summary-tile d-block text-decoration-none" href="/rooms"><div class="label">过期合同</div><strong>{expired_contract_count}</strong><span class="text-muted small"> 户</span></a></div>
                    <div class="col-md-3 col-6"><a class="summary-tile d-block text-decoration-none" href="/meter_readings"><div class="label">待确认抄表</div><strong>{meter_needed}</strong><span class="text-muted small"> 项</span></a></div>
                    <div class="col-md-3 col-6"><a class="summary-tile d-block text-decoration-none" href="/system_health"><div class="label">异常账单</div><strong>检查</strong><span class="text-muted small"> 状态/金额</span></a></div>
                </div>
            </div>
        </div>'''

        self._html(self._page('收费工作台', f'''
        {self._default_password_warning_html()}
        <div class="workbench-hero d-flex justify-content-between align-items-center flex-wrap gap-3">
            <div>
                <div class="hero-kicker">今日收费工作台</div>
                <h2>当前账期：{p}</h2>
                <p>日常出账、收费、打印、对账、催缴和开票提醒统一集中在这里。</p>
            </div>
            <div class="workbench-primary-actions">
                <span class="badge status-info">先看待办</span>
                <span class="badge status-warning">再处理异常</span>
                <span class="badge status-neutral">最后核对报表</span>
            </div>
        </div>
        <div class="metric-grid">
            <div class="metric-card primary"><div class="metric-label"><i class="bi bi-receipt"></i> 本月应收</div><div class="metric-value money">¥{m(ta)}</div></div>
            <div class="metric-card success"><div class="metric-label"><i class="bi bi-credit-card"></i> 本月已收</div><div class="metric-value money money-paid">¥{m(tp)}</div></div>
            <div class="metric-card danger"><div class="metric-label"><i class="bi bi-exclamation-circle"></i> 本月欠费</div><div class="metric-value money money-due">¥{m(month_due)}</div></div>
            <div class="metric-card success"><div class="metric-label"><i class="bi bi-cash-stack"></i> 今日收款</div><div class="metric-value money money-paid">¥{m(today_paid)}</div></div>
        </div>
        <div class="row g-3 mb-3">
            <div class="col-md-4"><div class="card border-warning"><div class="card-body"><div class="text-muted small">即将到期合同</div><strong>{len(expiring_contracts)}</strong><span class="text-muted ms-2">30天内</span></div></div></div>
            <div class="col-md-4"><div class="card border-danger"><div class="card-body"><div class="text-muted small">已过期合同</div><strong>{expired_contract_count}</strong><span class="text-muted ms-2">需核对</span></div></div></div>
            <div class="col-md-4"><div class="card border-info"><div class="card-body"><div class="text-muted small">待确认抄表项目</div><strong>{meter_needed}</strong><span class="text-muted ms-2">本账期</span></div></div></div>
        </div>
        <div class="row g-3 mb-3">
            <div class="col-12">{todo_cards}</div>
            <div class="col-12">{exception_cards}</div>
        </div>
        {first_run}
        <div class="row g-3 mb-3">
            <div class="col-md-7">
                <div class="card"><div class="card-header py-2 d-flex justify-content-between"><span><i class="bi bi-list-check"></i> 待收费账单</span><a href="/bills?status=unpaid" class="btn btn-sm btn-outline-primary">查看全部</a></div>
                <div class="table-responsive"><table class="table table-hover mb-0 small"><thead><tr><th>编号</th><th>房间</th><th>业主</th><th>项目</th><th class="text-end">待收</th><th>操作</th></tr></thead>
                <tbody>{pending_rows or '<tr><td colspan="6" class="text-center text-muted py-3">暂无待收费账单</td></tr>'}</tbody></table></div></div>
            </div>
            <div class="col-md-5">
                <div class="card mb-3"><div class="card-header py-2"><i class="bi bi-calendar-check"></i> 即将到期合同</div><div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>房间</th><th>业主</th><th>到期</th><th></th></tr></thead><tbody>{contract_rows}</tbody></table></div></div>
                <div class="card"><div class="card-header py-2"><i class="bi bi-pie-chart"></i> 本月收费概况</div>
                <div class="card-body">
                    <div class="row text-center g-2">
                        <div class="col-6"><div class="summary-tile"><div class="label">待收费账单</div><strong>{pending_cnt}</strong><span class="text-muted small"> 笔</span></div></div>
                        <div class="col-6"><div class="summary-tile"><div class="label">收缴率</div><strong>{rate}%</strong></div></div>
                    </div>
                    <p class="small text-muted mt-3 mb-0">主操作入口已放在页面顶部，避免重复按钮干扰。</p>
                </div></div>
            </div>
        </div>
        <div class="row g-3">
            <div class="col-md-6">
                <div class="card"><div class="card-header py-2"><i class="bi bi-list-check"></i> 各收费项目 <small class="text-muted">({p})</small></div>
                <div class="table-responsive"><table class="table table-hover mb-0 small"><thead><tr><th>类型</th><th class="text-end">应收</th><th class="text-end">笔数</th></tr></thead>
                <tbody>{fs or '<tr><td colspan="3" class="text-center text-muted py-3">暂无</td></tr>'}</tbody></table></div></div>
            </div>
            <div class="col-md-6">
                <div class="card"><div class="card-header py-2"><i class="bi bi-graph-up"></i> 本月每日收款趋势 <small class="text-muted">（按实际收款日期实时汇总）</small></div>
                <div class="card-body"><canvas id="trendChart" height="200"></canvas></div></div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.min.js"></script>
        <script>
        var td = {trends_json};
        if(typeof Chart !== 'undefined'){{
            new Chart(document.getElementById('trendChart'), {{
                type: 'bar',
                data: {{
                    labels: td.map(function(d){{ return d.label; }}),
                    datasets: [
                        {{label:'每日实收',data:td.map(function(d){{return d.paid;}}),backgroundColor:'rgba(25,135,84,0.65)',borderRadius:4}}
                    ]
                }},
                options:{{
                    responsive:true, maintainAspectRatio:false,
                    scales:{{y:{{beginAtZero:true,ticks:{{callback:function(v){{return '¥'+v;}}}}}}}},
                    plugins:{{legend:{{position:'bottom',labels:{{boxWidth:12}}}}}}
                }}
            }});
        }}
        </script>
        ''', 'index', primary_actions))

    def _api_stats(self):
        db=get_db()
        tr=db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        to=db.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
        tb=db.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
        tu=db.execute("SELECT COUNT(*) FROM bills WHERE status IN('unpaid','overdue')").fetchone()[0]
        tp=db.execute("SELECT COUNT(*) FROM bills WHERE status='paid'").fetchone()[0]
        db.close()
        self._json({'total_rooms':tr,'total_owners':to,'total_bills':tb,'unpaid_bills':tu,'paid_bills':tp})

    def _api_search_rooms(self, q):
        kw = qs(q, 'q', '')
        db = get_db()
        if kw:
            rows = db.execute(
                "SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id "
                "WHERE r.building LIKE ? OR r.room_number LIKE ? OR o.name LIKE ? "
                "ORDER BY r.building,r.room_number LIMIT 50",
                (f'%{kw}%', f'%{kw}%', f'%{kw}%')
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id "
                "ORDER BY r.building,r.room_number LIMIT 50"
            ).fetchall()
        db.close()
        self._json([{'id': r['id'], 'building': r['building'], 'unit': r['unit'],
                      'room_number': r['room_number'], 'floor': r['floor'], 'category': r['category'],
                      'area': r['area'], 'owner_id': r['owner_id'], 'oname': r['oname'] or ''} for r in rows])

    def _api_search_owners(self, q):
        kw = qs(q, 'q', '')
        db = get_db()
        if kw:
            rows = db.execute("SELECT * FROM owners WHERE name LIKE ? OR phone LIKE ? ORDER BY name LIMIT 50",
                              (f'%{kw}%', f'%{kw}%')).fetchall()
        else:
            rows = db.execute("SELECT * FROM owners ORDER BY name LIMIT 50").fetchall()
        db.close()
        self._json([{'id': r['id'], 'name': r['name'], 'phone': r['phone'] or ''} for r in rows])
