#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Database connection, initialization, and utility functions."""

import sqlite3, json
from datetime import datetime, date, timedelta
import os
from server.money import money_display, money_float, number_display, unit_price_display

BASE = os.environ.get('PM_RESOURCE_DIR') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get('PM_DB_PATH') or os.path.join(BASE, 'property.db')
BACKUP_DIR = os.environ.get('PM_BACKUP_DIR') or (
    os.path.join(os.path.dirname(DB_PATH), 'backups')
    if os.environ.get('PM_DB_PATH') else os.path.join(BASE, 'backups')
)
HOST = os.environ.get('PM_HOST', '127.0.0.1')
PORT = int(os.environ.get('PM_PORT', '5001'))



def _dedupe_renamed_fee_type(cursor, old_name, new_name):
    new_row = cursor.execute(
        "SELECT id FROM fee_types WHERE name=? ORDER BY is_active DESC, id LIMIT 1",
        (new_name,),
    ).fetchone()
    if new_row:
        keeper_id = new_row[0]
        cursor.execute(
            "UPDATE fee_types SET is_active=0 WHERE name=?",
            (old_name,),
        )
    else:
        old_row = cursor.execute(
            "SELECT id FROM fee_types WHERE name=? ORDER BY is_active DESC, id LIMIT 1",
            (old_name,),
        ).fetchone()
        if not old_row:
            return
        keeper_id = old_row[0]
        cursor.execute(
            "UPDATE fee_types SET name=?, is_active=1 WHERE id=?",
            (new_name, keeper_id),
        )
    cursor.execute(
        "UPDATE fee_types SET is_active=0 WHERE name=? AND id<>?",
        (new_name, keeper_id),
    )

from server.db_migrations import _migrate_merchant_contract_room_nullable, _migrate_bills_room_nullable, _migrate_meter_readings_room_nullable

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


def db_init():
    from server.db_setup import run_db_init
    return run_db_init(get_db, cleanup_old_sessions, _dedupe_renamed_fee_type,
                       _migrate_merchant_contract_room_nullable, _migrate_bills_room_nullable,
                       _migrate_meter_readings_room_nullable)

def cleanup_old_sessions():
    """删除超过24小时未活动的会话。"""
    try:
        db = get_db()
        db.execute("DELETE FROM sessions WHERE created_at < datetime('now', '-1 day')")
        db.commit()
        db.close()
    except:
        pass  # 静默失败，不影响主流程


LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 5


def check_login_rate(ip):
    """检查 IP 是否因登录失败过多被锁定。返回剩余锁定分钟数，0表示未锁定。"""
    try:
        if os.environ.get("PM_DISABLE_LOGIN_RATE_LIMIT", "").lower() in ("1", "true", "yes", "on"):
            return 0
        if ip in ("127.0.0.1", "::1", "localhost"):
            return 0
        db = get_db()
        # 清理过期记录
        db.execute("DELETE FROM login_attempts WHERE attempt_time < datetime('now', '-' || ? || ' minutes')",
                   (str(LOGIN_LOCKOUT_MINUTES * 2),))
        db.commit()
        # 统计最近 N 分钟内的失败次数
        row = db.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE ip=? AND success=0 "
            "AND attempt_time > datetime('now', '-' || ? || ' minutes')",
            (ip, str(LOGIN_LOCKOUT_MINUTES))
        ).fetchone()
        db.close()
        if row and row[0] >= LOGIN_MAX_ATTEMPTS:
            return LOGIN_LOCKOUT_MINUTES  # 锁定中
        return 0
    except:
        return 0  # 出错时不阻拦


def record_login_attempt(ip, success):
    """记录一次登录尝试。"""
    try:
        db = get_db()
        db.execute("INSERT INTO login_attempts(ip, success) VALUES(?,?)", (ip, 1 if success else 0))
        db.commit()
        db.close()
    except:
        pass


def get_period():
    n = date.today(); return f"{n.year}-{n.month:02d}"


def add_months(dt, n):
    total = dt.year * 12 + (dt.month - 1) + n
    y = total // 12
    m = total % 12 + 1
    return date(y, m, min(dt.day, [31,29 if y%4==0 and (y%100!=0 or y%400==0) else 28,31,30,31,30,31,31,30,31,30,31][m-1]))


def calc_elevator_fee(floor, area):
    floor = int(floor or 1); area = float(area or 0)
    db = get_db()
    tier = db.execute("SELECT rate FROM elevator_fee_tiers WHERE ? BETWEEN floor_from AND floor_to ORDER BY id LIMIT 1", (floor,)).fetchone()
    db.close()
    rate = tier[0] if tier else 1.0
    return money_float(rate * area)


def calc_bill_late_fee(bill_id):
    db = get_db()
    bill = db.execute("SELECT id, amount, due_date, status FROM bills WHERE id=?", (bill_id,)).fetchone()
    if not bill or bill['status'] == 'paid':
        db.close(); return 0
    cfg = db.execute("SELECT * FROM late_fee_config WHERE is_active=1 LIMIT 1").fetchone()
    if not cfg or cfg['daily_rate'] <= 0:
        db.close(); return 0
    due = datetime.strptime(bill['due_date'], '%Y-%m-%d').date() if bill['due_date'] else date.today()
    days = (date.today() - due).days - (cfg['grace_days'] or 0)
    if days <= 0:
        db.close(); return 0
    fee = money_float(bill['amount'] * cfg['daily_rate'] * days)
    max_fee = money_float(bill['amount'] * cfg['max_rate'])
    db.close()
    return min(fee, max_fee)


def update_overdue_bills():
    db = get_db()
    today = date.today().isoformat()
    db.execute("UPDATE bills SET status='overdue' WHERE status='unpaid' AND due_date < ?", (today,))
    db.commit()
    db.close()


def is_period_closed(period):
    db = get_db()
    r = db.execute("SELECT status FROM closing_records WHERE period=? AND status='closed'", (period,)).fetchone()
    db.close()
    return r is not None


def get_fee_type_rate(fee_type_id, category='居民'):
    db = get_db()
    tier = db.execute("SELECT rate FROM fee_type_tiers WHERE fee_type_id=? AND category=? LIMIT 1", (fee_type_id, category)).fetchone()
    if tier:
        rate = tier[0]
    else:
        ft = db.execute("SELECT unit_price FROM fee_types WHERE id=?", (fee_type_id,)).fetchone()
        rate = ft[0] if ft else 0
    db.close()
    return rate


def log_audit(action, entity_type='', entity_id=None, username='', role='', ip='', old_value=None, new_value=None, reason=''):
    """Best-effort audit log. Values are JSON encoded and never raise to caller."""
    try:
        def enc(v):
            if v is None or isinstance(v, str):
                return v
            return json.dumps(v, ensure_ascii=False, sort_keys=True)
        db = get_db()
        db.execute(
            "INSERT INTO audit_logs(action,entity_type,entity_id,username,role,ip,old_value,new_value,reason) VALUES(?,?,?,?,?,?,?,?,?)",
            (action, entity_type, entity_id, username, role, ip, enc(old_value), enc(new_value), reason)
        )
        db.commit(); db.close()
    except Exception:
        pass


def room_active_in_period(room, period):
    """Return True when room contract overlaps the YYYY-MM billing period."""
    if not period or '~' in period:
        return True
    try:
        y, mo = [int(x) for x in period[:7].split('-')]
        period_start = date(y, mo, 1)
        period_end = add_months(period_start, 1) - timedelta(days=1)
    except Exception:
        return True
    start = room['contract_start'] if 'contract_start' in room.keys() else None
    end = room['contract_end'] if 'contract_end' in room.keys() else None
    try:
        if start and datetime.strptime(start[:10], '%Y-%m-%d').date() > period_end:
            return False
        if end and datetime.strptime(end[:10], '%Y-%m-%d').date() < period_start:
            return False
    except Exception:
        return True
    return True


def period_to_date(period):
    period = str(period or get_period())[:7]
    if len(period) == 7 and period[4] == '-':
        return period + '-01'
    return get_period() + '-01'


def date_to_period(value):
    value = str(value or '').strip()
    if len(value) >= 10 and value[4] == '-' and value[7] == '-':
        return value[:7]
    if len(value) >= 7 and value[4] == '-':
        return value[:7]
    return get_period()


def period_to_compact(value):
    return date_to_period(value).replace('-', '')


def qs(d, k, dfl=''):
    v = d.get(k); return v[0] if isinstance(v, list) else (v or dfl)


def h(s):
    if s is None: return ''
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&#x27;')


def m(v):
    return money_display(v)


def n(v, digits=2):
    return number_display(v, digits)


def price(v):
    return unit_price_display(v)


def _row_get(row, key):
    """Safe field access for sqlite3.Row / dict; returns None when column absent."""
    try:
        keys = row.keys()
    except AttributeError:
        return row.get(key) if isinstance(row, dict) else None
    return row[key] if key in keys else None


def customer_name(row, default='未知'):
    """Unified customer-name resolution across all bill/payment views.

    Priority: out-of-bill snapshot first (so renames don't alter historical
    records), then commercial merchant/shop, then tenant, then owner.
    Tolerates missing columns and the owner_name / oname alias difference.
    """
    return (
        _row_get(row, 'customer_name_snapshot')
        or _row_get(row, 'space_merchant')
        or _row_get(row, 'space_shop')
        or _row_get(row, 'tenant_name')
        or _row_get(row, 'owner_name')
        or _row_get(row, 'oname')
        or default
    )

