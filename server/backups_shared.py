#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Database backup and restore."""

import os, shutil, sqlite3, urllib.parse
from datetime import datetime, date

import server.db as db_module
from server.db import get_db, h, m, db_init, qs
from server.base import BaseHandler


def create_db_backup(prefix='backup'):
    """Create a consistent SQLite database backup and return the backup file name."""
    if not os.path.exists(db_module.DB_PATH):
        raise FileNotFoundError('database file does not exist')
    os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
    safe_prefix = ''.join(ch if ch.isalnum() or ch in ('_', '-') else '_' for ch in prefix) or 'backup'
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    name = f'{safe_prefix}_{ts}.db'
    target = os.path.join(db_module.BACKUP_DIR, name)
    src = sqlite3.connect(db_module.DB_PATH)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return name


def ensure_startup_backups(keep=10):
    """Create one startup backup per process and one daily backup per day."""
    if os.environ.get('PM_SKIP_STARTUP_BACKUP') == '1' or not os.path.exists(db_module.DB_PATH):
        return []
    made = []
    try:
        os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
        marker = os.path.join(db_module.BACKUP_DIR, f'.daily_{date.today().isoformat()}')
        if not getattr(ensure_startup_backups, '_startup_done', False):
            made.append(create_db_backup('auto_startup'))
            ensure_startup_backups._startup_done = True
        if not os.path.exists(marker):
            made.append(create_db_backup('auto_daily'))
            with open(marker, 'w', encoding='utf-8') as f:
                f.write(datetime.now().isoformat())
        cleanup_automatic_backups(keep)
    except Exception:
        pass
    return made


def cleanup_automatic_backups(keep=10):
    plan = build_backup_cleanup_plan(keep)
    for item in plan['items']:
        if os.path.basename(item['path']).startswith('auto_') and os.path.exists(item['path']):
            try:
                os.remove(item['path'])
            except OSError:
                pass


BACKUP_TYPES = [
    ('startup', 'auto_startup_', '启动自动备份'),
    ('daily', 'auto_daily_', '每日自动备份'),
    ('bill_generation', 'auto_before_bill_generation_', '账单生成前'),
    ('batch_adjustment', 'auto_before_batch_adjustment_', '批量修正前'),
    ('bill_adjustment', 'auto_before_bill_adjustment_', '单笔修正前'),
    ('batch_payment', 'auto_before_batch_payment_', '批量收费前'),
    ('payment', 'auto_before_payment_', '单笔收费前'),
    ('import', 'auto_before_import_', '导入前'),
    ('restore', 'auto_before_restore_', '恢复前'),
    ('manual', 'backup_', '手动备份'),
]


def describe_backup_name(name):
    for key, prefix, label in BACKUP_TYPES:
        if name.startswith(prefix):
            return key, label
    return 'other', '其他备份'


def _parse_keep_count(raw_keep, default=10):
    try:
        keep = int(raw_keep)
    except (TypeError, ValueError):
        keep = default
    return max(1, min(100, keep))


def _format_size(size):
    if size >= 1024 * 1024:
        return f'{size / 1024 / 1024:.1f}MB'
    return f'{size / 1024:.1f}KB'


def _safe_backup_path(name):
    safe_name = urllib.parse.unquote(name or '')
    if not safe_name or safe_name != os.path.basename(safe_name):
        return None
    root = os.path.realpath(db_module.BACKUP_DIR)
    path = os.path.realpath(os.path.join(root, safe_name))
    if path == root or not path.startswith(root + os.sep):
        return None
    return path


def _automatic_backup_type_keys():
    return {key for key, prefix, _ in BACKUP_TYPES if prefix.startswith('auto_')}


def build_backup_cleanup_plan(keep=10, selected_type=''):
    """Return old automatic backups that can be deleted after confirmation."""
    keep = _parse_keep_count(keep)
    os.makedirs(db_module.BACKUP_DIR, exist_ok=True)
    groups = {}
    selected_type = selected_type or ''
    for name in os.listdir(db_module.BACKUP_DIR):
        fp = os.path.join(db_module.BACKUP_DIR, name)
        if not os.path.isfile(fp):
            continue
        type_key, type_label = describe_backup_name(name)
        if type_key not in _automatic_backup_type_keys():
            continue
        if selected_type:
            type_prefix = next((prefix for key, prefix, _ in BACKUP_TYPES if key == selected_type), '')
            if type_key != selected_type or not name.startswith(type_prefix):
                continue
        groups.setdefault(type_key, []).append({
            'name': name, 'path': fp, 'type_key': type_key, 'type_label': type_label,
            'size_bytes': os.path.getsize(fp), 'mtime': os.path.getmtime(fp),
        })

    delete_items = []
    kept_by_type = {}
    for type_key, items in groups.items():
        items.sort(key=lambda item: (item['mtime'], item['name']), reverse=True)
        kept_by_type[type_key] = len(items[:keep])
        delete_items.extend(items[keep:])
    delete_items.sort(key=lambda item: (item['type_label'], item['mtime'], item['name']))
    return {
        'keep': keep,
        'items': delete_items,
        'total_count': len(delete_items),
        'total_size': sum(item['size_bytes'] for item in delete_items),
        'kept_by_type': kept_by_type,
        'selected_type': selected_type,
    }


def read_backup_data_summary(path):
    summary = {
        'ok': False, 'error': '', 'owners': 0, 'rooms': 0, 'bills': 0, 'payments': 0,
        'bill_amount': 0, 'payment_amount': 0, 'periods': '', 'buildings': '',
    }
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            tables = {
                row['name'] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for table, key in [('owners', 'owners'), ('rooms', 'rooms'), ('bills', 'bills'), ('payments', 'payments')]:
                if table in tables:
                    summary[key] = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            if 'bills' in tables:
                summary['bill_amount'] = conn.execute('SELECT COALESCE(SUM(amount),0) FROM bills').fetchone()[0]
                rows = conn.execute(
                    "SELECT billing_period FROM bills WHERE billing_period IS NOT NULL AND billing_period<>'' "
                    "GROUP BY billing_period ORDER BY billing_period DESC LIMIT 5"
                ).fetchall()
                summary['periods'] = '、'.join(row['billing_period'] for row in rows)
            if 'payments' in tables:
                summary['payment_amount'] = conn.execute('SELECT COALESCE(SUM(amount_paid),0) FROM payments').fetchone()[0]
            if 'rooms' in tables:
                rows = conn.execute(
                    "SELECT building FROM rooms WHERE building IS NOT NULL AND building<>'' "
                    "GROUP BY building ORDER BY COUNT(*) DESC, building LIMIT 5"
                ).fetchall()
                summary['buildings'] = '、'.join(row['building'] for row in rows)
            summary['ok'] = True
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        summary['error'] = '备份文件不是有效数据库，无法读取摘要'
    except OSError:
        summary['error'] = '备份文件无法读取'
    return summary


def _backup_summary_html(summary):
    if not summary['ok']:
        return f'<div class="alert alert-warning"><strong>备份数据摘要读取失败</strong>：{h(summary["error"])}</div>'
    return f'''
        <div class="card"><div class="card-header">备份数据摘要</div>
        <div class="card-body">
        <div class="row g-3 mb-3">
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">房间数</div><div class="fs-4 fw-bold">{summary['rooms']}</div></div></div>
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">业主数</div><div class="fs-4 fw-bold">{summary['owners']}</div></div></div>
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">账单数</div><div class="fs-4 fw-bold">{summary['bills']}</div></div></div>
            <div class="col-md-3"><div class="border rounded p-3 text-center"><div class="text-muted">缴费记录数</div><div class="fs-4 fw-bold">{summary['payments']}</div></div></div>
        </div>
        <table class="table table-sm mb-0">
            <tr><td class="text-muted" style="width:140px">账单金额合计</td><td>{m(summary['bill_amount'])}</td></tr>
            <tr><td class="text-muted">缴费金额合计</td><td>{m(summary['payment_amount'])}</td></tr>
            <tr><td class="text-muted">最近账期</td><td>{h(summary['periods'] or '无')}</td></tr>
            <tr><td class="text-muted">主要楼栋</td><td>{h(summary['buildings'] or '无')}</td></tr>
        </table></div></div>'''

__all__ = [name for name in globals() if not name.startswith('__')]
