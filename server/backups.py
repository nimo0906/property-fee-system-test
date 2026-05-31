#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Database backup and restore."""

import os, shutil, sqlite3
from datetime import datetime, date

import server.db as db_module
from server.db import get_db, h, m, db_init
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


class BackupMixin(BaseHandler):

    def _backups(self, q=None):
        q = q or {}
        selected_type = q.get('type', [''])[0] if isinstance(q.get('type'), list) else q.get('type', '')
        if not os.path.exists(db_module.BACKUP_DIR):
            os.makedirs(db_module.BACKUP_DIR)
        files = []
        for f in sorted(os.listdir(db_module.BACKUP_DIR), reverse=True):
            fp = os.path.join(db_module.BACKUP_DIR, f)
            if os.path.isfile(fp):
                type_key, type_label = describe_backup_name(f)
                if selected_type and type_key != selected_type:
                    continue
                size = os.path.getsize(fp)
                mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                files.append({'name': f, 'type': type_label, 'size': _format_size(size), 'time': mtime})
        type_opts = '<option value="">全部类型</option>' + ''.join(
            f'<option value="{key}"{" selected" if selected_type == key else ""}>{label}</option>'
            for key, _, label in BACKUP_TYPES
        )
        rows = ''.join(
            f'''<tr>
                <td><small>{h(f["name"])}</small></td>
                <td><span class="badge bg-info text-dark">{h(f["type"])}</span></td>
                <td>{f["size"]}</td>
                <td>{f["time"]}</td>
                <td>
                    <a class="btn btn-sm btn-warning" href="/backups/{h(f["name"])}/restore"><i class="bi bi-arrow-counterclockwise"></i> 恢复</a>
                    <a class="btn btn-sm btn-danger" href="/backups/{h(f["name"])}/delete"><i class="bi bi-trash"></i></a>
                </td>
            </tr>'''
            for f in files
        )
        self._html(self._page('数据备份', f'''
        <div class="alert alert-info">
            <i class="bi bi-info-circle"></i>
            备份文件保存在 <code>backups/</code> 目录。系统启动和每日首次使用会自动备份；
            结账或大批量修改前仍建议手动创建备份。
            恢复备份会<strong>覆盖当前数据库</strong>，操作不可撤销。
        </div>
        <div class="d-flex gap-2 mb-3">
            <form method=POST action="/backups/create">
                <button class="btn btn-primary"><i class="bi bi-cloud-arrow-up"></i> 创建备份</button>
            </form>
            <form method=GET action="/backups" class="d-flex gap-2">
                <select name="type" class="form-select">{type_opts}</select>
                <button class="btn btn-outline-primary">筛选</button>
            </form>
            <a class="btn btn-outline-danger" href="/backups/cleanup?keep=10"><i class="bi bi-trash3"></i> 清理自动备份</a>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle">
                <thead>
                    <tr><th>备份文件</th><th>类型</th><th>大小</th><th>创建时间</th><th style="width:180px">操作</th></tr>
                </thead>
                <tbody>
                    {rows or '<tr><td colspan="5" class="text-center text-muted py-4">暂无备份文件，点击"创建备份"生成</td></tr>'}
                </tbody>
            </table>
        </div>
        ''', 'closing'))

    def _backup_create(self):
        try:
            name = create_db_backup('backup')
            self._redirect('/backups?flash=备份创建成功: ' + name)
        except FileNotFoundError:
            self._redirect('/backups?flash=数据库文件不存在')

    def _backup_restore_confirm(self, name):
        bp = os.path.join(db_module.BACKUP_DIR, name)
        if not os.path.exists(bp):
            return self._redirect('/backups?flash=备份文件不存在')
        type_key, type_label = describe_backup_name(name)
        size = _format_size(os.path.getsize(bp))
        mtime = datetime.fromtimestamp(os.path.getmtime(bp)).strftime('%Y-%m-%d %H:%M:%S')
        summary = read_backup_data_summary(bp)
        if summary['ok']:
            summary_html = f'''
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
        else:
            summary_html = f'''
        <div class="alert alert-warning"><strong>备份数据摘要读取失败</strong>：{h(summary['error'])}</div>'''
        self._html(self._page('恢复备份确认', f'''
        <div class="alert alert-danger"><strong>恢复备份确认</strong>：恢复会覆盖当前数据库，请确认选择正确。</div>
        <div class="card"><div class="card-header">将恢复的备份</div>
        <div class="card-body"><table class="table table-borderless mb-0">
        <tr><td class="text-muted" style="width:130px">备份文件</td><td><code>{h(name)}</code></td></tr>
        <tr><td class="text-muted">备份类型</td><td>{h(type_label)}</td></tr>
        <tr><td class="text-muted">文件大小</td><td>{h(size)}</td></tr>
        <tr><td class="text-muted">创建时间</td><td>{h(mtime)}</td></tr>
        </table></div></div>
        {summary_html}
        <div class="alert alert-warning">当前数据会先自动备份为 <code>auto_before_restore_*.db</code>，恢复后如果发现选错，可以在备份页再恢复该自动备份。</div>
        <form method="POST" action="/backups/{h(name)}/restore" class="d-inline"
            onsubmit="return confirm('最后确认：恢复会覆盖当前数据，确定继续？')">
            <button class="btn btn-danger">确认恢复</button>
        </form>
        <a href="/backups" class="btn btn-outline-secondary">取消</a>
        ''', 'backups'))

    def _backup_restore(self, name):
        bp = os.path.join(db_module.BACKUP_DIR, name)
        if not os.path.exists(bp):
            return self._redirect('/backups?flash=备份文件不存在')
        restore_backup_name = ''
        if os.path.exists(db_module.DB_PATH):
            restore_backup_name = create_db_backup('auto_before_restore')
        shutil.copy2(bp, db_module.DB_PATH)
        db_init()
        self._audit('backup_restore', 'backup', None, {'backup': name}, {'restore_backup': restore_backup_name}, '恢复数据库备份')
        summary = read_backup_data_summary(db_module.DB_PATH)
        if summary['ok']:
            summary_html = f'''
        <div class="card"><div class="card-header">当前数据库摘要</div><div class="card-body">
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
        else:
            summary_html = f'<div class="alert alert-warning">当前数据库摘要读取失败：{h(summary["error"])}</div>'
        self._html(self._page('恢复完成', f'''
        <div class="alert alert-success"><strong>恢复完成</strong>：已从 <code>{h(name)}</code> 恢复数据。</div>
        <div class="card"><div class="card-header">恢复结果</div><div class="card-body">
        <table class="table table-borderless mb-0">
            <tr><td class="text-muted" style="width:150px">恢复的备份</td><td><code>{h(name)}</code></td></tr>
            <tr><td class="text-muted">恢复前自动备份</td><td><code>{h(restore_backup_name or '无')}</code></td></tr>
        </table></div></div>
        {summary_html}
        <div class="d-flex gap-2 flex-wrap">
            <a class="btn btn-primary" href="/">去首页</a>
            <a class="btn btn-outline-primary" href="/rooms">查看房间</a>
            <a class="btn btn-outline-primary" href="/bills">查看账单</a>
            <a class="btn btn-outline-secondary" href="/backups">返回备份</a>
        </div>
        ''', 'backups'))

    def _backup_cleanup_preview(self, q=None):
        q = q or {}
        raw_keep = q.get('keep', ['10'])[0] if isinstance(q.get('keep'), list) else q.get('keep', '10')
        selected_type = q.get('type', [''])[0] if isinstance(q.get('type'), list) else q.get('type', '')
        plan = build_backup_cleanup_plan(raw_keep, selected_type)
        rows = ''.join(
            f'''<tr>
                <td><small>{h(item["name"])}</small></td>
                <td><span class="badge bg-warning text-dark">{h(item["type_label"])}</span></td>
                <td>{h(_format_size(item["size_bytes"]))}</td>
                <td>{h(datetime.fromtimestamp(item["mtime"]).strftime('%Y-%m-%d %H:%M:%S'))}</td>
            </tr>'''
            for item in plan['items']
        )
        summary_rows = ''.join(
            f'<tr><td>{h(label)}</td><td>保留最近 {plan["keep"]} 个</td><td>{plan["kept_by_type"].get(key, 0)} 个</td></tr>'
            for key, _, label in BACKUP_TYPES
            if key in _automatic_backup_type_keys()
        )
        type_opts = '<option value="">全部自动备份类型</option>' + ''.join(
            f'<option value="{key}"{" selected" if selected_type == key else ""}>{label}</option>'
            for key, _, label in BACKUP_TYPES
            if key in _automatic_backup_type_keys()
        )
        self._html(self._page('自动备份清理预览', f'''
        <div class="alert alert-warning">
            <strong>自动备份清理预览</strong>：默认只清理自动备份（<code>auto_before_*.db</code>），
            手动备份 <code>backup_*.db</code> 永远不会被本功能自动删除。
        </div>
        <form method="GET" action="/backups/cleanup" class="row g-2 align-items-end mb-3">
            <div class="col-auto">
                <label class="form-label">每类保留最近</label>
                <input class="form-control" name="keep" value="{plan['keep']}" type="number" min="1" max="100">
            </div>
            <div class="col-auto">
                <label class="form-label">清理类型</label>
                <select class="form-select" name="type">{type_opts}</select>
            </div>
            <div class="col-auto"><button class="btn btn-outline-primary">重新预览</button></div>
        </form>
        <div class="card mb-3"><div class="card-header">清理统计</div><div class="card-body">
            <p class="mb-2">将删除 <strong>{plan['total_count']}</strong> 个旧自动备份，预计释放 <strong>{h(_format_size(plan['total_size']))}</strong>。</p>
            <table class="table table-sm mb-0"><thead><tr><th>类型</th><th>规则</th><th>当前保留数</th></tr></thead><tbody>{summary_rows}</tbody></table>
        </div></div>
        <div class="table-responsive"><table class="table table-hover align-middle">
            <thead><tr><th>将删除的备份文件</th><th>类型</th><th>大小</th><th>创建时间</th></tr></thead>
            <tbody>{rows or '<tr><td colspan="4" class="text-center text-muted py-4">没有超过保留数量的自动备份，无需清理</td></tr>'}</tbody>
        </table></div>
        <form method="POST" action="/backups/cleanup" class="d-inline" onsubmit="return confirm('确认清理这些旧自动备份？手动备份不会删除。')">
            <input type="hidden" name="keep" value="{plan['keep']}">
            <input type="hidden" name="type" value="{h(selected_type)}">
            <button class="btn btn-danger" {'disabled' if plan['total_count'] == 0 else ''}>确认清理</button>
        </form>
        <a href="/backups" class="btn btn-outline-secondary">返回备份列表</a>
        ''', 'backups'))

    def _backup_cleanup_apply(self, d):
        raw_keep = d.get('keep', ['10'])[0] if isinstance(d.get('keep'), list) else d.get('keep', '10')
        selected_type = d.get('type', [''])[0] if isinstance(d.get('type'), list) else d.get('type', '')
        plan = build_backup_cleanup_plan(raw_keep, selected_type)
        deleted_count = 0
        freed_size = 0
        for item in plan['items']:
            if not os.path.basename(item['path']).startswith('auto_before_'):
                continue
            if os.path.exists(item['path']):
                freed_size += os.path.getsize(item['path'])
                os.remove(item['path'])
                deleted_count += 1
        self._redirect(f'/backups?flash=已清理自动备份 {deleted_count} 个，释放空间 {_format_size(freed_size)}')

    def _backup_delete_confirm(self, name):
        fp = os.path.join(db_module.BACKUP_DIR, name)
        if not os.path.exists(fp):
            return self._redirect('/backups?flash=备份文件不存在')
        type_key, type_label = describe_backup_name(name)
        size = _format_size(os.path.getsize(fp))
        mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M:%S')
        self._html(self._page('删除备份确认', f'''
        <div class="alert alert-danger"><strong>删除备份确认</strong>：删除后无法从系统内恢复，请确认这个备份已经不需要。</div>
        <div class="card"><div class="card-header">将删除的备份</div>
        <div class="card-body"><table class="table table-borderless mb-0">
        <tr><td class="text-muted" style="width:130px">备份文件</td><td><code>{h(name)}</code></td></tr>
        <tr><td class="text-muted">备份类型</td><td>{h(type_label)}</td></tr>
        <tr><td class="text-muted">文件大小</td><td>{h(size)}</td></tr>
        <tr><td class="text-muted">创建时间</td><td>{h(mtime)}</td></tr>
        </table></div></div>
        <form method="POST" action="/backups/{h(name)}/delete" class="d-inline"
            onsubmit="return confirm('最后确认：删除后无法从系统内恢复，确定删除？')">
            <button class="btn btn-danger">确认删除</button>
        </form>
        <a href="/backups" class="btn btn-outline-secondary">取消</a>
        ''', 'backups'))

    def _backup_delete(self, name):
        fp = os.path.join(db_module.BACKUP_DIR, name)
        if os.path.exists(fp):
            os.remove(fp)
            self._audit('backup_delete', 'backup', None, {'backup': name}, None, '删除备份文件')
        self._redirect('/backups?flash=已删除')
