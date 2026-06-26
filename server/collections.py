#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Customer-facing arrears collection views."""

from datetime import date, datetime, timedelta

from server.db import get_db, h, add_months, date_to_period, period_to_date
from server.billing_periods import append_natural_date_range_filter
from server.pagination import pagination_state, query_items, render_pagination
from server.money import money_display


def _money(value):
    return money_display(value, comma=True)


def _parse_date(value):
    if not value:
        return None


def _first_value(q, key, default=""):
    value = q.get(key, [default])
    return (value[0] if isinstance(value, list) else value) or default


def _legacy_period_range(period):
    p = date_to_period(period)
    start = period_to_date(p)
    try:
        y, mo = [int(x) for x in start[:7].split('-')]
        end = (add_months(date(y, mo, 1), 1) - timedelta(days=1)).isoformat()
    except Exception:
        end = start
    return start, end
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


class CollectionMixin:
    def _collections(self, q):
        building = _first_value(q, "building").strip()
        period = _first_value(q, "period").strip()
        period_start = _first_value(q, "period_start").strip()
        period_end = _first_value(q, "period_end").strip()
        if period and not period_start and not period_end:
            period_start, period_end = _legacy_period_range(period)
        priority_filter = _first_value(q, "priority").strip()
        today = date.today()
        db = get_db()
        buildings = [r["building"] for r in db.execute(
            "SELECT DISTINCT building FROM rooms WHERE building<>'' ORDER BY building"
        ).fetchall()]
        params = []
        where = []
        if building:
            where.append("r.building=?"); params.append(building)
        if period_start or period_end:
            base_sql = "SELECT 1 FROM bills b WHERE 1=1"
            base_sql, period_params = append_natural_date_range_filter(base_sql, [], period_start, period_end, 'b.billing_period', 'b.service_start', 'b.service_end')
            clause = base_sql.split("WHERE 1=1 AND ", 1)[1]
            where.append(clause); params.extend(period_params)
        where_sql = (" AND " + " AND ".join(where)) if where else ""
        rows = db.execute(f"""
            SELECT b.id, b.billing_period, b.amount, b.due_date, b.status,
                   r.building, r.unit, r.room_number,
                   o.name AS owner_name, o.phone,
                   f.name AS fee_name,
                   COALESCE((SELECT SUM(amount_paid) FROM payments p WHERE p.bill_id=b.id),0) AS paid
            FROM bills b
            JOIN rooms r ON r.id=b.room_id
            LEFT JOIN owners o ON o.id=b.owner_id
            JOIN fee_types f ON f.id=b.fee_type_id
            WHERE b.amount - COALESCE((SELECT SUM(amount_paid) FROM payments p WHERE p.bill_id=b.id),0) > 0.005
            {where_sql}
        """, params).fetchall()
        db.close()

        items = []
        for r in rows:
            due = float(r["amount"] or 0) - float(r["paid"] or 0)
            due_date = _parse_date(r["due_date"])
            overdue_days = max((today - due_date).days, 0) if due_date else 0
            if due >= 1000 or overdue_days >= 60:
                priority, rank, badge = "高", 3, "danger"
            elif due >= 300 or overdue_days >= 30:
                priority, rank, badge = "中", 2, "warning"
            else:
                priority, rank, badge = "低", 1, "secondary"
            if priority_filter and priority != priority_filter:
                continue
            items.append((rank, due, overdue_days, r, priority, badge))
        items.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]["building"], x[3]["room_number"]))

        total_due = sum(x[1] for x in items)
        high_count = sum(1 for x in items if x[4] == "高")
        total_rows = len(items)
        pg, per_page, total_pages = pagination_state(q, total_rows)
        visible_items = items[(pg - 1) * per_page:pg * per_page]
        options = ''.join(
            f'<option value="{h(b)}"{" selected" if b == building else ""}>{h(b)}</option>'
            for b in buildings
        )
        pri_opts = ''.join(
            f'<option value="{p}"{" selected" if p == priority_filter else ""}>{label}</option>'
            for p, label in [("", "全部优先级"), ("高", "高优先级"), ("中", "中优先级"), ("低", "低优先级")]
        )
        body = f'''
        <div class="alert alert-info">
          <i class="bi bi-info-circle"></i>
          本页给客服部查看重点催费对象，只展示欠费信息，不提供财务修改入口。
        </div>
        <div class="row g-3 mb-3">
          <div class="col-md-4"><div class="card"><div class="card-body"><div class="text-muted small">欠费对象</div><div class="h4 mb-0">{len(items)}</div></div></div></div>
          <div class="col-md-4"><div class="card"><div class="card-body"><div class="text-muted small">欠费金额</div><div class="h4 mb-0">¥{_money(total_due)}</div></div></div></div>
          <div class="col-md-4"><div class="card"><div class="card-body"><div class="text-muted small">高优先级</div><div class="h4 mb-0 text-danger">{high_count}</div></div></div></div>
        </div>
        <form class="card card-body mb-3" method="GET" action="/collections">
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">楼栋</label><select name="building" class="form-select"><option value="">全部楼栋</option>{options}</select></div>
            <div class="col-md-3"><label class="form-label">起始日期</label><input type="date" name="period_start" class="form-control" value="{h(period_start)}"></div>
            <div class="col-md-3"><label class="form-label">截止日期</label><input type="date" name="period_end" class="form-control" value="{h(period_end)}"></div>
            <div class="col-md-3"><label class="form-label">优先级</label><select name="priority" class="form-select">{pri_opts}</select></div>
            <div class="col-md-3"><button class="btn btn-primary"><i class="bi bi-search"></i> 筛选</button> <a href="/collections" class="btn btn-outline-secondary">重置</a></div>
          </div>
        </form>
        '''
        rows_html = ""
        for _, due, overdue_days, r, priority, badge in visible_items:
            room = f'{r["building"] or ""}-{r["unit"] or ""}-{r["room_number"] or ""}'
            rows_html += f'''
            <tr>
              <td><strong>{h(room)}</strong></td>
              <td>{h(r["owner_name"] or "-")}</td>
              <td>{h(r["phone"] or "-")}</td>
              <td>{h(r["billing_period"])}</td>
              <td>{h(r["fee_name"])}</td>
              <td class="text-end">¥{_money(due)}</td>
              <td>{h(r["due_date"] or "-")}</td>
              <td>{overdue_days}</td>
              <td><span class="badge bg-{badge}">{priority}</span></td>
              <td><a class="btn btn-sm btn-outline-primary" href="/bills/{r['id']}">查看账单</a></td>
            </tr>'''
        if not rows_html:
            rows_html = '<tr><td colspan="10" class="text-center text-muted py-4">暂无欠费对象</td></tr>'
        body += f'''
        <div class="card"><div class="card-header"><i class="bi bi-telephone-outbound"></i> 客服催费对象</div>
        <div class="table-responsive"><table class="table table-hover align-middle mb-0">
          <thead><tr><th>房间</th><th>业主</th><th>电话</th><th>欠费账期</th><th>欠费项目</th><th class="text-end">欠费金额</th><th>截止日</th><th>欠费天数</th><th>优先级</th><th>操作</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table></div></div>
        {render_pagination('/collections', query_items(q, ['building', 'period_start', 'period_end', 'priority']), pg, total_pages, per_page, total_rows, '客服催收分页')}
        '''
        self._html(self._page("客服催费对象", body, "collections"))
