#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trial/demo data reset page and action."""

from server.backups import create_db_backup
from server.base import BaseHandler
from server.db import get_db, h, m

BUSINESS_TABLES = [
    'invoice_requests', 'notification_events', 'payment_callbacks', 'payment_orders',
    'payments', 'invoices', 'deposits', 'parking_spots', 'repairs', 'bill_adjustments',
    'meter_readings', 'bills', 'shared_expense_runs', 'closing_records', 'rooms', 'owners',
]

SUMMARY_TABLES = [
    ('owners', '业主'), ('rooms', '房间'), ('bills', '账单'), ('payments', '缴费'),
    ('meter_readings', '抄表'), ('invoices', '发票'), ('invoice_requests', '票据请求'),
]


def _table_names(db):
    return {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def trial_data_summary():
    db = get_db()
    try:
        tables = _table_names(db)
        items = []
        for table, label in SUMMARY_TABLES:
            if table in tables:
                count = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                items.append({'table': table, 'label': label, 'count': count})
        bill_amount = db.execute('SELECT COALESCE(SUM(amount),0) FROM bills').fetchone()[0] if 'bills' in tables else 0
        payment_amount = db.execute('SELECT COALESCE(SUM(amount_paid),0) FROM payments').fetchone()[0] if 'payments' in tables else 0
        buildings = ''
        if 'rooms' in tables:
            rows = db.execute("SELECT building FROM rooms WHERE building<>'' GROUP BY building ORDER BY COUNT(*) DESC, building LIMIT 5").fetchall()
            buildings = '、'.join(r['building'] for r in rows)
        return {'items': items, 'bill_amount': bill_amount, 'payment_amount': payment_amount, 'buildings': buildings}
    finally:
        db.close()


def reset_trial_data():
    backup_name = create_db_backup('auto_before_trial_data_reset')
    db = get_db()
    try:
        tables = _table_names(db)
        db.execute('PRAGMA foreign_keys=OFF')
        deleted = {}
        for table in BUSINESS_TABLES:
            if table in tables:
                deleted[table] = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                db.execute(f'DELETE FROM {table}')
        db.execute('PRAGMA foreign_keys=ON')
        db.commit()
        return {'backup_name': backup_name, 'deleted': deleted}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class TrialDataResetMixin(BaseHandler):
    def _trial_data_reset(self, q=None):
        u = self._get_current_user() or {}
        if u.get('role') != 'admin':
            return self._redirect('/?flash=无权限访问清空试用数据')
        summary = trial_data_summary()
        rows = ''.join(
            f'<tr><td>{h(item["label"])}</td><td class="text-end">{item["count"]}</td></tr>'
            for item in summary['items']
        ) or '<tr><td colspan="2" class="text-center text-muted">暂无试用数据</td></tr>'
        self._html(self._page('清空试用业务数据', f'''
        <div class="alert alert-warning"><strong>清空试用业务数据</strong>：仅用于内测/演示环境重新验证流程。它会真实删除数据库中的业务记录，不是隐藏数据。</div>
        <div class="alert alert-light border">
        <div><strong>会删除：</strong>业主、房间、账单、缴费、抄表、发票、结账、公摊等业务记录。</div>
        <div><strong>不会删除：</strong>操作员账号、收费项目/单价配置、备份文件、系统更新文件、程序文件。</div>
        <div><strong>安全保护：</strong>执行前会自动生成数据库备份，可通过数据备份页面恢复。</div>
        </div>
        <div class="card mb-3"><div class="card-header">将清理的数据摘要</div>
        <div class="card-body">
        <div class="row g-3 mb-3">
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">账单金额</div><strong>¥{m(summary['bill_amount'])}</strong></div></div>
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">缴费金额</div><strong>¥{m(summary['payment_amount'])}</strong></div></div>
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">主要楼栋</div><strong>{h(summary['buildings'] or '-')}</strong></div></div>
        </div>
        <table class="table table-sm"><thead><tr><th>类型</th><th class="text-end">数量</th></tr></thead><tbody>{rows}</tbody></table>
        </div></div>
        <form method="POST" action="/trial_data_reset" onsubmit="return confirm('确认清空试用业务数据？执行前会自动备份，但当前业务记录会从数据库删除。')" class="card">
        <div class="card-body">
        <label class="form-label">请输入 <code>RESET</code> 后执行</label>
        <input name="confirm_text" class="form-control" placeholder="RESET">
        <button class="btn btn-danger mt-3"><i class="bi bi-trash3"></i> 清空试用业务数据</button>
        <a href="/" class="btn btn-outline-secondary mt-3">取消</a>
        </div></form>
        ''', 'trial_data_reset'))

    def _trial_data_reset_post(self, d):
        u = self._get_current_user() or {}
        if u.get('role') != 'admin':
            return self._redirect('/?flash=无权限执行清空试用数据')
        if (d.get('confirm_text') or [''])[0] != 'RESET':
            return self._redirect('/trial_data_reset?flash=请输入RESET后再执行')
        result = reset_trial_data()
        total = sum(result['deleted'].values())
        self._audit('trial_data_reset', 'system', None, None, result, '清空本机试用数据')
        return self._redirect('/trial_data_reset?flash=已清空试用数据' + str(total) + '条，备份：' + result['backup_name'])
