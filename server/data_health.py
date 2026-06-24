#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""System health checks for schema and financial data consistency."""

from server.db import get_db, db_init, h, m
from server.money import money_float


EXPECTED_TABLES = [
    'projects', 'owners', 'rooms', 'fee_types', 'meter_readings', 'bills', 'payments',
    'elevator_fee_tiers', 'fee_type_tiers', 'late_fee_config', 'closing_records',
    'repairs', 'users', 'sessions', 'invoices', 'invoice_requests', 'deposits',
    'parking_spots', 'bill_adjustments', 'login_attempts', 'audit_logs',
    'shared_expense_runs',
    'notification_events',
]

EXPECTED_COLUMNS = {
    'owners': ['project_id'],
    'rooms': ['contract_start', 'contract_end', 'business_type', 'water_rate_type', 'shop_name', 'payment_cycle', 'project_id'],
    'bills': ['source', 'source_ref', 'project_id'],
    'payments': ['receipt_number', 'project_id'],
    'fee_types': ['reminder_advance_days', 'project_id'],
    'invoice_requests': ['project_id'],
    'notification_events': ['project_id'],
}


def _table_names(db):
    return {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _columns(db, table):
    try:
        return {r['name'] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def expected_schema_issues(db=None):
    """Return missing expected tables/columns for the current database."""
    own_conn = db is None
    db = db or get_db()
    try:
        tables = _table_names(db)
        missing_tables = [t for t in EXPECTED_TABLES if t not in tables]
        missing_columns = []
        for table, cols in EXPECTED_COLUMNS.items():
            if table not in tables:
                continue
            existing = _columns(db, table)
            for col in cols:
                if col not in existing:
                    missing_columns.append({'table': table, 'column': col})
        return {'missing_tables': missing_tables, 'missing_columns': missing_columns}
    finally:
        if own_conn:
            db.close()


def repair_schema():
    """Run idempotent schema creation/migration and return remaining issues."""
    db_init()
    return expected_schema_issues()


def financial_integrity_issues(db=None, limit=50):
    """Find bill/payment status mismatches that affect reconciliation."""
    own_conn = db is None
    db = db or get_db()
    try:
        bill_rows = db.execute(
            """SELECT b.id bill_id,b.bill_number,b.billing_period,b.amount,b.status,
                      COALESCE(SUM(p.amount_paid),0) paid,
                      r.building,r.unit,r.room_number,o.name owner_name
               FROM bills b
               LEFT JOIN payments p ON p.bill_id=b.id
               LEFT JOIN rooms r ON r.id=b.room_id
               LEFT JOIN owners o ON o.id=b.owner_id
               GROUP BY b.id
               ORDER BY b.id"""
        ).fetchall()
        paid_under = [r for r in bill_rows if r['status'] == 'paid' and money_float(r['amount']) > money_float(r['paid'])][:limit]
        unpaid_with_paid = [r for r in bill_rows if r['status'] in ('unpaid', 'overdue') and money_float(r['paid']) > 0][:limit]
        overpaid = [r for r in bill_rows if money_float(r['paid']) > money_float(r['amount'])][:limit]
        orphan_payments = db.execute(
            """SELECT p.id payment_id,p.bill_id,p.amount_paid,p.payment_date,p.created_at
               FROM payments p LEFT JOIN bills b ON b.id=p.bill_id
               WHERE b.id IS NULL
               ORDER BY p.id LIMIT ?""",
            (limit,),
        ).fetchall()
        stale_linked_payments = db.execute(
            """SELECT p.id payment_id,p.bill_id,p.amount_paid,p.payment_date,p.created_at,
                      b.bill_number,b.billing_period,b.created_at bill_created_at
               FROM payments p JOIN bills b ON b.id=p.bill_id
               WHERE p.created_at IS NOT NULL AND b.created_at IS NOT NULL
                 AND p.created_at < b.created_at
               ORDER BY p.id LIMIT ?""",
            (limit,),
        ).fetchall()
        return {
            'paid_status_but_underpaid': [dict(r) for r in paid_under],
            'unpaid_status_but_paid': [dict(r) for r in unpaid_with_paid],
            'overpaid_bills': [dict(r) for r in overpaid],
            'orphan_payments': [dict(r) for r in orphan_payments],
            'stale_linked_payments': [dict(r) for r in stale_linked_payments],
        }
    finally:
        if own_conn:
            db.close()


def cleanup_invalid_payments(db=None):
    """Remove payment rows that cannot safely belong to the current bill rows."""
    own_conn = db is None
    db = db or get_db()
    try:
        orphan_ids = [
            str(r['id']) for r in db.execute(
                "SELECT p.id FROM payments p LEFT JOIN bills b ON b.id=p.bill_id WHERE b.id IS NULL"
            ).fetchall()
        ]
        stale_ids = [
            str(r['id']) for r in db.execute(
                """SELECT p.id FROM payments p JOIN bills b ON b.id=p.bill_id
                   WHERE p.created_at IS NOT NULL AND b.created_at IS NOT NULL
                     AND p.created_at < b.created_at"""
            ).fetchall()
        ]
        ids = sorted(set(orphan_ids + stale_ids), key=int)
        if ids:
            db.execute(f"DELETE FROM payments WHERE id IN ({','.join('?' * len(ids))})", ids)
            db.commit()
        elif own_conn:
            db.commit()
        return {'deleted': len(ids), 'orphan': len(orphan_ids), 'stale_linked': len(stale_ids)}
    finally:
        if own_conn:
            db.close()


def repair_bill_payment_statuses(db=None):
    """Recompute bill status from payment sums for non-overpaid bills."""
    own_conn = db is None
    db = db or get_db()
    updated = 0
    try:
        cleanup = cleanup_invalid_payments(db)
        rows = db.execute(
            """SELECT b.id,b.amount,b.status,COALESCE(SUM(p.amount_paid),0) paid
               FROM bills b LEFT JOIN payments p ON p.bill_id=b.id
               GROUP BY b.id"""
        ).fetchall()
        for row in rows:
            amount = money_float(row['amount'])
            paid = money_float(row['paid'])
            if paid > amount:
                continue
            if paid >= amount and amount > 0:
                status = 'paid'
            elif paid > 0:
                status = 'partial'
            elif row['status'] == 'overdue':
                status = 'overdue'
            else:
                status = 'unpaid'
            if status != row['status']:
                db.execute(
                    "UPDATE bills SET status=?, paid_at=CASE WHEN ?='paid' THEN COALESCE(paid_at, datetime('now','localtime')) ELSE NULL END WHERE id=?",
                    (status, status, row['id']),
                )
                updated += 1
        if own_conn:
            db.commit()
        return {'updated': updated, 'invalid_payments_deleted': cleanup['deleted']}
    finally:
        if own_conn:
            db.close()


class DataHealthMixin:
    def _system_health(self, q=None):
        user = self._get_current_user()
        if not user or user.get('role') != 'admin':
            return self._redirect('/?flash=无权限访问系统健康检查')
        schema = expected_schema_issues()
        finance = financial_integrity_issues()
        missing_table_rows = ''.join(f'<tr><td><code>{h(x)}</code></td><td>缺失表</td></tr>' for x in schema['missing_tables'])
        missing_col_rows = ''.join(f'<tr><td><code>{h(x["table"])}.{h(x["column"])}</code></td><td>缺失字段</td></tr>' for x in schema['missing_columns'])
        schema_rows = missing_table_rows + missing_col_rows or '<tr><td colspan="2" class="text-center text-muted py-3">schema 完整</td></tr>'
        finance_rows = self._health_bill_rows(finance['paid_status_but_underpaid'], '已缴状态但收款不足')
        finance_rows += self._health_bill_rows(finance['unpaid_status_but_paid'], '未缴状态但已有收款')
        finance_rows += self._health_bill_rows(finance['overpaid_bills'], '收款超过应收')
        finance_rows += self._health_payment_rows(finance['orphan_payments'], '孤立收款记录')
        finance_rows += self._health_payment_rows(finance['stale_linked_payments'], '疑似串账收款')
        if not finance_rows:
            finance_rows = '<tr><td colspan="8" class="text-center text-muted py-3">账单/收款状态一致</td></tr>'
        self._html(self._page('系统健康检查', f'''
        <div class="alert alert-info"><strong>系统健康检查</strong>：用于检查数据库结构、账单状态和收款记录是否一致。修复前建议先备份。</div>
        <div class="row g-3 mb-3">
          <div class="col-md-6"><div class="metric-card"><div class="metric-label">Schema 问题</div><div class="metric-value">{len(schema['missing_tables']) + len(schema['missing_columns'])}</div></div></div>
          <div class="col-md-6"><div class="metric-card warning"><div class="metric-label">账单状态问题</div><div class="metric-value">{sum(len(v) for v in finance.values())}</div></div></div>
        </div>
        <div class="card mb-3"><div class="card-header d-flex justify-content-between"><span>数据库结构</span>
          <form method="POST" action="/system_health/repair"><input type="hidden" name="repair" value="schema"><button class="btn btn-sm btn-outline-primary">修复结构</button></form></div>
          <table class="table table-sm mb-0"><thead><tr><th>对象</th><th>问题</th></tr></thead><tbody>{schema_rows}</tbody></table></div>
        <div class="card"><div class="card-header d-flex justify-content-between"><span>账单/收款一致性</span>
          <form method="POST" action="/system_health/repair" onsubmit="return confirm('将按缴费记录重算账单状态，确认修复？')"><input type="hidden" name="repair" value="bill_status"><button class="btn btn-sm btn-outline-warning">修复账单状态</button></form></div>
          <table class="table table-sm mb-0"><thead><tr><th>问题</th><th>编号</th><th>房间</th><th>业主</th><th>账期</th><th class="text-end">应收</th><th class="text-end">已收</th><th>状态</th></tr></thead><tbody>{finance_rows}</tbody></table></div>
        ''', 'system_health'))

    def _health_bill_rows(self, rows, label):
        html = ''
        for r in rows:
            room = f'{r.get("building") or ""}-{r.get("unit") or ""}-{r.get("room_number") or ""}'
            html += f'<tr><td>{h(label)}</td><td><a href="/bills/{r["bill_id"]}">{h(r.get("bill_number") or r["bill_id"])}</a></td><td>{h(room)}</td><td>{h(r.get("owner_name") or "-")}</td><td>{h(r.get("billing_period") or "-")}</td><td class="text-end">¥{m(r.get("amount") or 0)}</td><td class="text-end">¥{m(r.get("paid") or 0)}</td><td>{h(r.get("status") or "")}</td></tr>'
        return html

    def _health_payment_rows(self, rows, label):
        html = ''
        for r in rows:
            target = h(r.get('bill_number') or r.get('bill_id') or '-')
            html += f'<tr><td>{h(label)}</td><td>{target}</td><td>-</td><td>-</td><td>{h(r.get("billing_period") or "-")}</td><td class="text-end">-</td><td class="text-end">¥{m(r.get("amount_paid") or 0)}</td><td>{h(r.get("payment_date") or r.get("created_at") or "")}</td></tr>'
        return html

    def _system_health_repair(self, d):
        user = self._get_current_user()
        if not user or user.get('role') != 'admin':
            return self._redirect('/?flash=无权限执行系统修复')
        action = self._form_first(d, 'repair')
        if action == 'schema':
            remaining = repair_schema()
            count = len(remaining['missing_tables']) + len(remaining['missing_columns'])
            self._audit('system_health_repair_schema', 'system', None, None, remaining, '系统健康检查修复结构')
            return self._redirect('/system_health?flash=结构修复完成，剩余问题' + str(count) + '个')
        if action == 'bill_status':
            db = get_db()
            try:
                result = repair_bill_payment_statuses(db)
                db.commit()
            finally:
                db.close()
            self._audit('system_health_repair_bill_status', 'bill', None, None, result, '按收款记录重算账单状态')
            return self._redirect('/system_health?flash=已修复账单状态 ' + str(result['updated']) + ' 条')
        return self._redirect('/system_health?flash=未知修复动作')

    def _form_first(self, data, key, default=''):
        value = data.get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value
