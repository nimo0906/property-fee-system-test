#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Period closing management."""

from datetime import date, timedelta

from server.base import BaseHandler
from server.billing_periods import natural_date_range_filter_clause
from server.db import add_months, date_to_period, get_db, h, is_period_closed, m, period_to_date, qs, customer_name


class ClosingMixin(BaseHandler):

    def _month_end(self, start_value):
        try:
            y, mo = [int(x) for x in str(start_value or '')[:7].split('-')]
            return (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
        except Exception:
            return str(start_value or '')

    def _range_from_period(self, period):
        text = str(period or '').strip()
        if not text:
            return '', '', ''
        if '~' in text:
            left, right = text.split('~', 1)
            start = period_to_date(left)
            end = self._month_end(right)
        else:
            start = period_to_date(text)
            end = self._month_end(start)
        return start, end, f'{start} 至 {end}'

    def _closing_range_from_form(self, d):
        period = qs(d, 'period').strip()
        start = qs(d, 'period_start').strip()
        end = qs(d, 'period_end').strip()
        if period and not start and not end:
            start, end, _ = self._range_from_period(period)
        if start and not end:
            end = start
        if end and not start:
            start = end
        if end < start:
            start, end = end, start
        if start and end:
            if start.endswith('-01') and end == self._month_end(start) and start[:7] == end[:7]:
                period = date_to_period(start)
            else:
                period = f'{start}~{end}'
        label = f'{start} 至 {end}' if start or end else period
        return period, start, end, label

    def _closing_filter_clause(self, period, start='', end=''):
        if not (start or end):
            start, end, _ = self._range_from_period(period)
        return natural_date_range_filter_clause(start, end, 'billing_period', 'service_start', 'service_end')

    def _closing(self):
        db = get_db()
        records = db.execute('SELECT * FROM closing_records ORDER BY period DESC').fetchall()
        db.close()
        rhtml = ''
        for r in records:
            redos = ''
            if r['status'] == 'closed':
                pval = h(str(r['period']))
                redos = '<form method=POST action="/closing/reopen" style=display:inline onsubmit="return confirm(\'确认反结账?\')"><input type=hidden name=period value="' + pval + '"><button class="btn btn-sm btn-outline-warning">反结账</button></form>'
            st = '<span class="badge bg-success">已结账</span>' if r['status'] == 'closed' else '<span class="badge bg-warning text-dark">已反结账</span>'
            rhtml += '<tr><td>' + h(r['period']) + '</td><td>' + st + '</td>'
            rhtml += '<td>' + (r['close_date'] or '-') + '</td><td>' + h(r['operator'] or '-') + '</td>'
            rhtml += '<td>' + str(r['paid_count'] or 0) + '笔</td><td class="text-end">¥' + m(r['total_amount'] or 0) + '</td><td>' + redos + '</td></tr>'
        html = '''<div class="alert alert-info"><i class="bi bi-info-circle"></i> 期末结账用于锁定某一日期范围，防止已缴账单被误改、误删或重复生成；它不会删除账单、不会自动收款、不会自动开发票。</div>'''
        html += '''<div class="row g-4"><div class="col-md-5"><div class="card"><div class="card-header">结账操作</div><div class="card-body"><form method=POST action="/closing/close" class="row g-3"><div class="col-12"><label>起始日期</label><input type="date" name="period_start" class="form-control" required></div><div class="col-12"><label>截止日期</label><input type="date" name="period_end" class="form-control" required></div><div class="col-12"><label>备注</label><input name="notes" class="form-control"></div><div class="col-12"><hr><button class="btn btn-outline-primary" name="preview" value="1"><i class="bi bi-search"></i> 提前预览</button> <button class="btn btn-primary" onclick="return confirm('确认结账?')"><i class="bi bi-lock"></i> 执行结账</button></div></form></div></div><p class="text-muted small mt-2">结账后：<br>- 已缴账单不可修改<br>- 不可生成新账单<br>- 反结账后可恢复</p></div>'''
        html += '''<div class="col-md-7"><div class="card"><div class="card-header">结账记录</div><div class="card-body p-0"><table class="table table-hover mb-0"><thead><tr><th>日期范围</th><th>状态</th><th>日期</th><th>操作员</th><th>笔数</th><th>金额</th><th>操作</th></tr></thead><tbody>''' + rhtml + '''</tbody></table></div></div></div></div>'''
        self._html(self._page('期末结账', html, 'closing'))

    def _closing_close(self, d):
        period, period_start, period_end, period_label = self._closing_range_from_form(d)
        if not period:
            return self._redirect('/closing?flash=请选择起始和截止日期')
        if is_period_closed(period):
            return self._redirect('/closing?flash=' + period + '已结账')
        db = get_db()
        stats = self._closing_period_stats(db, period, period_start, period_end)
        if qs(d, 'preview') == '1':
            db.close()
            return self._render_closing_precheck(period, qs(d, 'notes'), stats, True, period_start, period_end, period_label)
        if qs(d, 'confirm') != '1':
            db.close()
            return self._render_closing_precheck(period, qs(d, 'notes'), stats, False, period_start, period_end, period_label)
        close_clause, close_vals = self._closing_filter_clause(period, period_start, period_end)
        paid = db.execute("SELECT COUNT(*) cnt, COALESCE(SUM(amount),0) tot FROM bills WHERE " + close_clause + " AND status='paid'", close_vals).fetchone()
        db.execute("INSERT INTO closing_records(period,close_date,status,operator,notes,paid_count,total_amount) VALUES(?,datetime('now','localtime'),'closed','管理员',?,?,?)",
                   (period, qs(d, 'notes'), paid['cnt'] or 0, paid['tot'] or 0))
        db.commit(); db.close()
        self._redirect('/closing?flash=' + period + '结账成功')

    def _closing_period_stats(self, db, period, period_start=None, period_end=None):
        clause, vals = self._closing_filter_clause(period, period_start, period_end)
        row = db.execute("""
            SELECT COUNT(*) total_count,
                   COALESCE(SUM(amount),0) total_amount,
                   SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) paid_count,
                   SUM(CASE WHEN status='partial' THEN 1 ELSE 0 END) partial_count,
                   SUM(CASE WHEN status IN ('unpaid','overdue') THEN 1 ELSE 0 END) unpaid_count,
                   COALESCE(SUM(CASE WHEN status='paid' THEN amount ELSE 0 END),0) paid_amount,
                   COALESCE(SUM(CASE WHEN status='partial' THEN amount ELSE 0 END),0) partial_amount,
                   COALESCE(SUM(CASE WHEN status IN ('unpaid','overdue') THEN amount ELSE 0 END),0) unpaid_amount,
                   SUM(CASE WHEN amount<=0 OR room_id IS NULL OR fee_type_id IS NULL THEN 1 ELSE 0 END) abnormal_count
            FROM bills WHERE """ + clause, vals).fetchone()
        return dict(row)

    def _closing_period_bill_rows(self, db, period, period_start=None, period_end=None):
        clause, vals = self._closing_filter_clause(period, period_start, period_end)
        return db.execute("""
            SELECT b.bill_number,b.billing_period,b.amount,b.status,
                   b.customer_name_snapshot,r.building,r.unit,r.room_number,r.tenant_name,
                   o.name owner_name,f.name fee_name,
                   s.merchant_name space_merchant,s.shop_name space_shop,
                   COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
            FROM bills b
            LEFT JOIN rooms r ON b.room_id=r.id
            LEFT JOIN owners o ON b.owner_id=o.id
            LEFT JOIN fee_types f ON b.fee_type_id=f.id
            LEFT JOIN commercial_spaces s ON b.commercial_space_id=s.id
            WHERE """ + clause + """
            ORDER BY r.building,r.unit,r.room_number,f.name,b.id
        """, vals).fetchall()

    def _render_closing_precheck(self, period, notes, stats, preview=False, period_start=None, period_end=None, period_label=None):
        db = get_db()
        bill_rows = self._closing_period_bill_rows(db, period, period_start, period_end)
        db.close()
        warnings = []
        if (stats.get('unpaid_count') or 0) > 0:
            warnings.append('存在未缴账单')
        if (stats.get('partial_count') or 0) > 0:
            warnings.append('存在部分缴费账单')
        if (stats.get('abnormal_count') or 0) > 0:
            warnings.append('存在异常账单')
        warning_html = ''.join(f'<li>{h(x)}</li>' for x in warnings) or '<li>未发现明显异常</li>'
        status_names = {'paid': '已缴', 'unpaid': '未缴', 'overdue': '逾期', 'partial': '部分缴'}
        detail_rows = ''
        for b in bill_rows:
            room = '-'.join(x for x in [b['building'], b['unit'], b['room_number']] if x) or '-'
            payer = customer_name(b, default='-')
            detail_rows += f'''<tr><td>{h(b['bill_number'] or '-')}</td><td>{h(room)}</td><td>{h(payer)}</td>
                <td>{h(b['fee_name'] or '-')}</td><td>{h(b['billing_period'])}</td>
                <td class="text-end">¥{m(b['amount'] or 0)}</td><td class="text-end">¥{m(b['paid'] or 0)}</td>
                <td>{h(status_names.get(b['status'], b['status'] or '-'))}</td></tr>'''
        if not detail_rows:
            detail_rows = '<tr><td colspan="8" class="text-center text-muted">该日期范围暂无账单</td></tr>'
        details_html = f'''<div class="card"><div class="card-header">本次将结账的账单明细</div>
            <div class="card-body p-0"><div class="table-responsive"><table class="table table-sm table-hover mb-0">
            <thead><tr><th>编号</th><th>房间</th><th>租户/业主</th><th>收费项目</th><th>账期</th><th class="text-end">金额</th><th class="text-end">已缴</th><th>状态</th></tr></thead>
            <tbody>{detail_rows}</tbody></table></div></div></div>'''
        confirm_form = f'''<form method=POST action="/closing/close" class="d-inline">
            <input type=hidden name="period" value="{h(period)}"><input type=hidden name="period_start" value="{h(period_start or '')}"><input type=hidden name="period_end" value="{h(period_end or '')}"><input type=hidden name="notes" value="{h(notes)}"><input type=hidden name="confirm" value="1">
            <button class="btn btn-danger" onclick="return confirm('确认结账？结账后该日期范围将被锁定。')">确认结账</button>
        </form>'''
        actions = f'''<div class="d-flex flex-wrap gap-2">{confirm_form}
            <a class="btn btn-outline-primary" href="/bills?period_start={h(period_start or '')}&amp;period_end={h(period_end or '')}">查看账单</a>
            <a class="btn btn-outline-secondary" href="/closing">返回修改</a></div>'''
        title = '结账前预览' if preview else '结账前检查'
        self._html(self._page(title, f'''
        <div class="alert alert-warning"><strong>{title}</strong>：结账对象是日期范围 <code>{h(period_label or period)}</code> 下方明细里的账单。确认后只会锁定该日期范围，防止误改、误删和重复生成；不会删除账单、不会自动收款、不会自动开发票。</div>
        <div class="row text-center g-2 mb-3">
            <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">账单总数</div><strong>{stats.get('total_count') or 0}</strong></div></div>
            <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">已缴账单</div><strong>{stats.get('paid_count') or 0}</strong></div></div>
            <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">部分缴费</div><strong>{stats.get('partial_count') or 0}</strong></div></div>
            <div class="col-md-3"><div class="border rounded p-3"><div class="text-muted small">未缴账单</div><strong>{stats.get('unpaid_count') or 0}</strong></div></div>
        </div>
        <div class="card"><div class="card-header">金额核对</div><div class="card-body"><table class="table table-sm mb-0">
            <tr><td>应收合计</td><td class="text-end">¥{m(stats.get('total_amount') or 0)}</td></tr>
            <tr><td>已缴账单金额</td><td class="text-end">¥{m(stats.get('paid_amount') or 0)}</td></tr>
            <tr><td>部分缴费账单金额</td><td class="text-end">¥{m(stats.get('partial_amount') or 0)}</td></tr>
            <tr><td>未缴账单金额</td><td class="text-end">¥{m(stats.get('unpaid_amount') or 0)}</td></tr>
        </table></div></div>
        <div class="alert alert-light border"><strong>异常提醒</strong><ul class="mb-0">{warning_html}</ul></div>
        {details_html}
        {actions}
        ''', 'closing'))

    def _closing_reopen(self, d):
        period = qs(d, 'period')
        if not period:
            return self._redirect('/closing?flash=参数错误')
        if qs(d, 'confirm') != '1':
            return self._render_reopen_confirm(period)
        db = get_db()
        db.execute("UPDATE closing_records SET status='reopened' WHERE period=?", (period,))
        db.commit(); db.close()
        self._redirect(f'/closing?flash={period}已反结账')

    def _closing_reopen_confirm(self, q):
        return self._render_reopen_confirm(qs(q, 'period'))

    def _render_reopen_confirm(self, period):
        if not period:
            return self._redirect('/closing?flash=参数错误')
        db = get_db()
        rec = db.execute("SELECT * FROM closing_records WHERE period=? AND status='closed'", (period,)).fetchone()
        if not rec:
            db.close(); return self._redirect('/closing?flash=该账期未结账或已反结账')
        start, end, label = self._range_from_period(period)
        stats = self._closing_period_stats(db, period, start, end)
        db.close()
        self._html(self._page('反结账确认', f'''
        <div class="alert alert-danger"><strong>反结账确认</strong>：请确认要重新打开日期范围 <code>{h(label or period)}</code>。</div>
        <div class="card"><div class="card-header">原结账信息</div><div class="card-body"><table class="table table-borderless mb-0">
            <tr><td class="text-muted" style="width:130px">日期范围</td><td>{h(label or period)}</td></tr>
            <tr><td class="text-muted">结账时间</td><td>{h(rec['close_date'] or '-')}</td></tr>
            <tr><td class="text-muted">操作员</td><td>{h(rec['operator'] or '-')}</td></tr>
            <tr><td class="text-muted">已缴笔数</td><td>{rec['paid_count'] or 0}</td></tr>
            <tr><td class="text-muted">结账金额</td><td>¥{m(rec['total_amount'] or 0)}</td></tr>
            <tr><td class="text-muted">备注</td><td>{h(rec['notes'] or '-')}</td></tr>
        </table></div></div>
        <div class="card"><div class="card-header">当前账单摘要</div><div class="card-body"><table class="table table-sm mb-0">
            <tr><td>账单总数</td><td class="text-end">{stats.get('total_count') or 0}</td></tr>
            <tr><td>已缴账单</td><td class="text-end">{stats.get('paid_count') or 0}</td></tr>
            <tr><td>部分缴费</td><td class="text-end">{stats.get('partial_count') or 0}</td></tr>
            <tr><td>未缴账单</td><td class="text-end">{stats.get('unpaid_count') or 0}</td></tr>
            <tr><td>应收合计</td><td class="text-end">¥{m(stats.get('total_amount') or 0)}</td></tr>
        </table></div></div>
        <div class="alert alert-warning"><strong>风险提示</strong>：反结账后该日期范围将重新允许生成账单、收费、修改、删除和批量操作，请确认这是有意操作。</div>
        <form method=POST action="/closing/reopen" onsubmit="return confirm('确认反结账？该日期范围将重新开放修改。')">
            <input type=hidden name="period" value="{h(period)}"><input type=hidden name="confirm" value="1">
            <button class="btn btn-danger">确认反结账</button>
            <a class="btn btn-outline-primary" href="/bills?period_start={h(start)}&amp;period_end={h(end)}">查看账单</a>
            <a class="btn btn-outline-secondary" href="/closing">取消</a>
        </form>
        ''', 'closing'))
