#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trial/demo data reset page and action."""

import os
import shutil

import server.db as db_module
from server.backups import create_db_backup
from server.base import BaseHandler
from server.db import get_db, h, m

BUSINESS_TABLES = [
    'invoice_requests', 'notification_events', 'payment_callbacks', 'payment_orders',
    'payments', 'invoices', 'deposits', 'parking_spots', 'repairs', 'bill_adjustments',
    'meter_readings', 'bills', 'shared_expense_runs', 'closing_records', 'rooms', 'owners',
]

CONTRACT_TABLES = [
    'contract_attachments', 'contract_bill_runs', 'merchant_contracts', 'commercial_spaces',
]

SUMMARY_TABLES = [
    ('owners', '业主'), ('rooms', '房间'), ('bills', '账单'), ('payments', '缴费'),
    ('meter_readings', '抄表'), ('invoices', '发票'), ('invoice_requests', '票据请求'),
]

CONTRACT_SUMMARY_TABLES = [
    ('merchant_contracts', '合同档案'), ('commercial_spaces', '商业空间'),
    ('contract_attachments', '合同附件'), ('contract_bill_runs', '合同出账批次'),
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
        contract_items = []
        for table, label in CONTRACT_SUMMARY_TABLES:
            if table in tables:
                count = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                contract_items.append({'table': table, 'label': label, 'count': count})
        bill_amount = db.execute('SELECT COALESCE(SUM(amount),0) FROM bills').fetchone()[0] if 'bills' in tables else 0
        payment_amount = db.execute('SELECT COALESCE(SUM(amount_paid),0) FROM payments').fetchone()[0] if 'payments' in tables else 0
        buildings = ''
        if 'rooms' in tables:
            rows = db.execute("SELECT building FROM rooms WHERE building<>'' GROUP BY building ORDER BY COUNT(*) DESC, building LIMIT 5").fetchall()
            buildings = '、'.join(r['building'] for r in rows)
        return {
            'items': items, 'contract_items': contract_items,
            'bill_amount': bill_amount, 'payment_amount': payment_amount, 'buildings': buildings,
        }
    finally:
        db.close()


def _data_root():
    root = os.environ.get('PM_DATA_DIR')
    if root:
        return root
    db_dir = os.path.dirname(db_module.DB_PATH)
    return os.path.dirname(db_dir) if os.path.basename(db_dir) == 'database' else db_dir


def _remove_contract_attachment_files():
    path = os.path.join(_data_root(), 'contract_attachments')
    if not os.path.isdir(path):
        return False
    try:
        shutil.rmtree(path)
        return True
    except OSError:
        return False


def reset_trial_data(include_business=True, include_contracts=False):
    backup_name = create_db_backup('auto_before_trial_data_reset')
    db = get_db()
    try:
        tables = _table_names(db)
        db.execute('PRAGMA foreign_keys=OFF')
        deleted = {}
        if include_business:
            for table in BUSINESS_TABLES:
                if table in tables:
                    deleted[table] = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    db.execute(f'DELETE FROM {table}')
        if include_contracts:
            for table in CONTRACT_TABLES:
                if table in tables:
                    deleted[table] = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    db.execute(f'DELETE FROM {table}')
        db.execute('PRAGMA foreign_keys=ON')
        db.commit()
        files_removed = _remove_contract_attachment_files() if include_contracts else False
        return {'backup_name': backup_name, 'deleted': deleted, 'files_removed': files_removed}
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
        contract_rows = ''.join(
            f'<tr><td>{h(item["label"])}</td><td class="text-end">{item["count"]}</td></tr>'
            for item in summary['contract_items']
        ) or '<tr><td colspan="2" class="text-center text-muted">暂无合同档案数据</td></tr>'
        self._html(self._page('清空试用业务数据', f'''
        <div class="alert alert-warning"><strong>清空试用业务数据</strong>：仅用于内测/演示环境重新验证流程。它会真实删除数据库中的业务记录，不是隐藏数据。</div>
        <div class="alert alert-light border">
        <div><strong>默认会删除：</strong>业主、收费对象、账单、缴费、抄表、发票、结账、公摊等业务记录。</div>
        <div><strong>可选删除：</strong>合同档案、商业空间、合同附件、合同出账批次。</div>
        <div><strong>不会删除：</strong>操作员账号、收费项目/单价配置、备份文件、系统更新文件、程序文件。</div>
        <div><strong>安全保护：</strong>执行前会自动生成数据库备份，可通过数据备份页面恢复。</div>
        </div>
        <div class="card mb-3"><div class="card-header">将清理的数据摘要</div>
        <div class="card-body">
        <div class="row g-3 mb-3">
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">账单金额</div><strong>¥{m(summary['bill_amount'])}</strong></div></div>
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">缴费金额</div><strong>¥{m(summary['payment_amount'])}</strong></div></div>
        <div class="col-md-4"><div class="finance-summary"><div class="text-muted small">主要楼栋/区域</div><strong>{h(summary['buildings'] or '-')}</strong></div></div>
        </div>
        <div class="row g-3"><div class="col-lg-7">
        <div class="small text-muted mb-2">基础业务资料和收费记录</div>
        <table class="table table-sm"><thead><tr><th>类型</th><th class="text-end">数量</th></tr></thead><tbody>{rows}</tbody></table>
        </div><div class="col-lg-5">
        <div class="small text-muted mb-2">合同档案和商业空间</div>
        <table class="table table-sm"><thead><tr><th>类型</th><th class="text-end">数量</th></tr></thead><tbody>{contract_rows}</tbody></table>
        </div></div>
        </div></div>
        <form method="POST" action="/trial_data_reset" onsubmit="return confirm('确认按所选范围清空数据？执行前会自动备份，但所选记录会从数据库删除。')" class="card">
        <div class="card-body">
        <div class="mb-3"><label class="form-label fw-semibold">清空范围</label>
        <input type="hidden" name="scope_form" value="1">
        <div class="form-check"><input class="form-check-input" type="checkbox" name="include_business" checked id="scope_business">
        <label class="form-check-label" for="scope_business">基础业务资料和收费记录（业主、收费对象、账单、缴费等）</label></div>
        <div class="form-check mt-2"><input class="form-check-input" type="checkbox" name="include_contracts" id="include_contracts">
        <label class="form-check-label" for="include_contracts">同时清空合同档案和商业空间（含合同附件、合同出账批次）</label></div>
        <div class="form-text text-danger">如果你只想删除合同，可以取消“基础业务资料”，只勾选“合同档案和商业空间”。至少选择一个范围。</div></div>
        <label class="form-label">请输入 <code>RESET</code> 后执行</label>
        <input name="confirm_text" class="form-control" placeholder="RESET" autocomplete="off">
        <button class="btn btn-danger mt-3"><i class="bi bi-trash3"></i> 按所选范围清空</button>
        <a href="/" class="btn btn-outline-secondary mt-3">取消</a>
        </div></form>
        ''', 'trial_data_reset'))

    def _trial_data_reset_post(self, d):
        u = self._get_current_user() or {}
        if u.get('role') != 'admin':
            return self._redirect('/?flash=无权限执行清空试用数据')
        if (d.get('confirm_text') or [''])[0] != 'RESET':
            return self._redirect('/trial_data_reset?flash=请输入RESET后再执行')
        is_scope_form = (d.get('scope_form') or [''])[0] == '1'
        include_business = True if not is_scope_form else (d.get('include_business') or [''])[0] == 'on'
        include_contracts = (d.get('include_contracts') or [''])[0] == 'on'
        if not include_business and not include_contracts:
            return self._redirect('/trial_data_reset?flash=请至少选择一个清空范围')
        result = reset_trial_data(include_business=include_business, include_contracts=include_contracts)
        total = sum(result['deleted'].values())
        self._audit('trial_data_reset', 'system', None, None, result, '清空本机试用数据')
        scopes = []
        if include_business:
            scopes.append('基础业务')
        if include_contracts:
            scopes.append('合同档案')
        scope = '（' + '、'.join(scopes) + '）'
        return self._redirect('/trial_data_reset?flash=已清空试用数据' + str(total) + '条' + scope + '，备份：' + result['backup_name'])
