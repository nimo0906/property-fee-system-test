#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Home dashboard entrypoint."""

from server.index_shared import *
from server.index_dashboard import render_index_dashboard


class IndexMixinPart1(BaseHandler):
    def _index(self):
        update_overdue_bills()
        db = get_db()
        p = get_period()
        ta = db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM bills WHERE billing_period=?",
            (p,),
        ).fetchone()[0]
        tp = db.execute(
            "SELECT COALESCE(SUM(p.amount_paid),0) FROM payments p JOIN bills b ON p.bill_id=b.id WHERE b.billing_period=?",
            (p,),
        ).fetchone()[0]
        rate = round(tp / ta * 100, 1) if ta > 0 else 0
        enterprise = get_enterprise_dashboard_metrics(p)

        y, mo = [int(x) for x in p.split("-")]
        first_day = date(y, mo, 1)
        next_month = add_months(first_day, 1)
        month_start = first_day.isoformat()
        month_end = (next_month - date.resolution).isoformat()

        today_paid = db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE date(payment_date)=date('now','localtime')"
        ).fetchone()[0]
        pending_cnt = db.execute(
            "SELECT COUNT(*) FROM bills WHERE billing_period=? AND status IN('unpaid','overdue','partial')",
            (p,),
        ).fetchone()[0]
        today = date.today().isoformat()
        expiring_contracts = db.execute(
            """SELECT r.*,o.name owner_name FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
            WHERE r.contract_end IS NOT NULL AND r.contract_end<>'' AND r.contract_end BETWEEN ? AND date(?, '+30 days')
            ORDER BY r.contract_end LIMIT 8""",
            (today, today),
        ).fetchall()
        meter_needed = db.execute(
            """SELECT COUNT(*) FROM fee_types f WHERE f.is_active=1 AND f.calc_method='meter'
            AND NOT EXISTS (SELECT 1 FROM meter_readings m WHERE m.fee_type_id=f.id AND m.period=replace(?, '-', '') AND m.status='confirmed')""",
            (p,),
        ).fetchone()[0]
        overdue_cnt = db.execute(
            "SELECT COUNT(*) FROM bills WHERE billing_period=? AND status='overdue'",
            (p,),
        ).fetchone()[0]
        today_payment_cnt = db.execute(
            "SELECT COUNT(*) FROM payments WHERE date(payment_date)=date('now','localtime')"
        ).fetchone()[0]
        invoice_todo_cnt = db.execute(
            """SELECT COUNT(*) FROM bills b
            WHERE b.status='paid' AND b.id NOT IN (SELECT bill_id FROM invoices)
            AND b.id NOT IN (SELECT bill_id FROM invoice_requests WHERE status IN('pending','submitted','issued'))"""
        ).fetchone()[0]
        zero_amount_cnt = db.execute(
            "SELECT COUNT(*) FROM bills WHERE billing_period=? AND amount<=0",
            (p,),
        ).fetchone()[0]
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
            (p,),
        ).fetchall()
        fts = db.execute(
            "SELECT f.name,COUNT(b.id) cnt,COALESCE(SUM(b.amount),0) tot FROM fee_types f LEFT JOIN bills b ON b.fee_type_id=f.id AND b.billing_period=? WHERE f.is_active=1 GROUP BY f.id ORDER BY f.sort_order",
            (p,),
        ).fetchall()
        db.close()

        role = (self._get_current_user() or {}).get("role")
        can_finance_write = role_allows(role, "finance")
        can_customer_write = role_allows(role, "customer_service") and not can_finance_write
        pending_rows = "".join(
            f"""<tr><td><small>{h(b["bill_number"] or "-")}</small></td>
            <td>{h(b["building"] or "")}-{h(b["unit"] or "")}-{h(b["room_number"] or "")}</td>
            <td>{h(b["owner_name"] or "-")}</td>
            <td><span class="badge status-info">{h(b["ft"])}</span></td>
            <td class="text-end"><span class="money money-due">¥{m(float(b["amount"] or 0) - float(b["paid"] or 0))}</span></td>
            <td>{f'<a href="/bills/{b["id"]}/pay" class="btn btn-sm btn-outline-success">收费登记</a>' if can_finance_write else '<a href="/bills" class="btn btn-sm btn-outline-primary">查看账单</a>'}</td></tr>"""
            for b in pending_bills
        )
        contract_rows = "".join(
            f"""<tr><td>{h(r["building"])}-{h(r["room_number"])}</td>
            <td>{h(r["owner_name"] or "-")}</td><td>{h(r["contract_end"] or "-")}</td>
            <td><a class="btn btn-sm btn-outline-primary" href="/rooms/{r["id"]}/edit">处理</a></td></tr>"""
            for r in expiring_contracts
        ) or '<tr><td colspan="4" class="text-center text-muted py-3">30天内暂无到期合同</td></tr>'

        html, primary_actions = render_index_dashboard(
            self,
            role=role,
            can_finance_write=can_finance_write,
            can_customer_write=can_customer_write,
            ta=ta,
            tp=tp,
            rate=rate,
            enterprise=enterprise,
            p=p,
            month_start=month_start,
            month_end=month_end,
            today_paid=today_paid,
            pending_cnt=pending_cnt,
            overdue_cnt=overdue_cnt,
            today_payment_cnt=today_payment_cnt,
            invoice_todo_cnt=invoice_todo_cnt,
            zero_amount_cnt=zero_amount_cnt,
            meter_needed=meter_needed,
            pending_rows=pending_rows,
            contract_rows=contract_rows,
            fts=fts,
        )
        self._html(self._page("收费工作台", html, "index", primary_actions))
