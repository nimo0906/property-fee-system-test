#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Database connection, initialization, and utility functions."""

import sqlite3, hashlib, json
from datetime import datetime, date, timedelta
import os

BASE = os.environ.get('PM_RESOURCE_DIR') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get('PM_DB_PATH') or os.path.join(BASE, 'property.db')
BACKUP_DIR = os.environ.get('PM_BACKUP_DIR') or (
    os.path.join(os.path.dirname(DB_PATH), 'backups')
    if os.environ.get('PM_DB_PATH') else os.path.join(BASE, 'backups')
)
HOST = os.environ.get('PM_HOST', '127.0.0.1')
PORT = int(os.environ.get('PM_PORT', '5001'))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


def db_init():
    conn = get_db(); c = conn.cursor()
    SQL = """
        CREATE TABLE IF NOT EXISTS owners (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, id_card TEXT, move_in_date TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS rooms (id INTEGER PRIMARY KEY AUTOINCREMENT, building TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '1单元', room_number TEXT NOT NULL, floor INTEGER DEFAULT 1, category TEXT DEFAULT '居民', area REAL NOT NULL DEFAULT 0, owner_id INTEGER REFERENCES owners(id), custom_rate REAL, contract_start TEXT, contract_end TEXT, id_card TEXT, id_card_front TEXT, id_card_back TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS fee_types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, calc_method TEXT NOT NULL DEFAULT 'fixed', unit_price REAL NOT NULL DEFAULT 0, unit TEXT, billing_cycle TEXT NOT NULL DEFAULT 'monthly', is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS meter_readings (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL REFERENCES rooms(id), fee_type_id INTEGER NOT NULL REFERENCES fee_types(id), period TEXT NOT NULL, previous_reading REAL DEFAULT 0, current_reading REAL DEFAULT 0, consumption REAL DEFAULT 0, reading_date TEXT, status TEXT DEFAULT 'draft', notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS bills (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL REFERENCES rooms(id), owner_id INTEGER REFERENCES owners(id), fee_type_id INTEGER NOT NULL REFERENCES fee_types(id), billing_period TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0, due_date TEXT, status TEXT DEFAULT 'unpaid', bill_number TEXT UNIQUE, paid_at TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, bill_id INTEGER NOT NULL REFERENCES bills(id), amount_paid REAL NOT NULL DEFAULT 0, payment_date TEXT DEFAULT (datetime('now','localtime')), payment_method TEXT DEFAULT 'cash', operator TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS elevator_fee_tiers (id INTEGER PRIMARY KEY AUTOINCREMENT, floor_from INTEGER NOT NULL, floor_to INTEGER NOT NULL, rate REAL NOT NULL, label TEXT); CREATE TABLE IF NOT EXISTS fee_type_tiers (id INTEGER PRIMARY KEY AUTOINCREMENT, fee_type_id INTEGER NOT NULL REFERENCES fee_types(id), category TEXT NOT NULL, rate REAL NOT NULL, is_default INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS late_fee_config (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, daily_rate REAL DEFAULT 0.001, max_rate REAL DEFAULT 0.05, grace_days INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS closing_records (id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT NOT NULL UNIQUE, close_date TEXT, status TEXT DEFAULT 'closed', operator TEXT, notes TEXT, paid_count INTEGER DEFAULT 0, total_amount REAL DEFAULT 0, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS repairs (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER REFERENCES rooms(id), owner_name TEXT, phone TEXT, report_date TEXT NOT NULL, description TEXT NOT NULL, category TEXT, status TEXT DEFAULT 'pending', assignee TEXT, cost REAL DEFAULT 0, complete_date TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, display_name TEXT, role TEXT DEFAULT 'operator', is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, user_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY AUTOINCREMENT, bill_id INTEGER REFERENCES bills(id), invoice_number TEXT UNIQUE, amount REAL NOT NULL, issue_date TEXT, buyer_name TEXT, buyer_tax_id TEXT, status TEXT DEFAULT 'issued', notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS invoice_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, request_no TEXT NOT NULL UNIQUE, bill_id INTEGER NOT NULL UNIQUE REFERENCES bills(id), owner_id INTEGER REFERENCES owners(id), amount REAL NOT NULL, buyer_name TEXT, buyer_tax_id TEXT, status TEXT NOT NULL DEFAULT 'pending', provider TEXT NOT NULL DEFAULT 'manual', external_invoice_id TEXT, idempotency_key TEXT UNIQUE, failure_reason TEXT, created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT, submitted_at TEXT, issued_at TEXT);
        CREATE TABLE IF NOT EXISTS deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER REFERENCES rooms(id), owner_id INTEGER REFERENCES owners(id), amount REAL NOT NULL DEFAULT 0, deposit_date TEXT, refund_date TEXT, refund_amount REAL DEFAULT 0, status TEXT DEFAULT 'active', notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS parking_spots (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER REFERENCES rooms(id), spot_number TEXT NOT NULL, floor_zone TEXT, monthly_fee REAL DEFAULT 0, status TEXT DEFAULT 'occupied', notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS bill_adjustments (id INTEGER PRIMARY KEY AUTOINCREMENT, bill_id INTEGER NOT NULL REFERENCES bills(id), old_amount REAL NOT NULL, new_amount REAL NOT NULL, reason TEXT NOT NULL, approved_by TEXT DEFAULT '管理员', created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT NOT NULL, attempt_time TEXT DEFAULT (datetime('now','localtime')), success INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity_type TEXT, entity_id INTEGER, username TEXT, role TEXT, ip TEXT, old_value TEXT, new_value TEXT, reason TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS shared_expense_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT NOT NULL, fee_type_id INTEGER NOT NULL REFERENCES fee_types(id), total_amount REAL NOT NULL DEFAULT 0, allocation_method TEXT NOT NULL DEFAULT 'area', building TEXT, category TEXT, room_count INTEGER DEFAULT 0, generated_bill_ids TEXT, operator TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS owner_portal_login_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT, attempt_count INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS owner_portal_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, owner_id INTEGER NOT NULL REFERENCES owners(id), phone TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now','localtime')), expires_at TEXT NOT NULL, revoked_at TEXT);
        CREATE TABLE IF NOT EXISTS payment_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, order_no TEXT NOT NULL UNIQUE, owner_id INTEGER NOT NULL REFERENCES owners(id), bill_id INTEGER NOT NULL REFERENCES bills(id), amount REAL NOT NULL, channel TEXT NOT NULL DEFAULT 'mock', status TEXT NOT NULL DEFAULT 'created', external_payment_id TEXT, idempotency_key TEXT, created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT, paid_at TEXT, cancelled_at TEXT, failure_reason TEXT);
        CREATE TABLE IF NOT EXISTS payment_callbacks (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, external_event_id TEXT NOT NULL, order_no TEXT NOT NULL, received_at TEXT DEFAULT (datetime('now','localtime')), processed_at TEXT, status TEXT NOT NULL DEFAULT 'received', raw_summary TEXT, error_message TEXT, UNIQUE(channel, external_event_id));
        CREATE TABLE IF NOT EXISTS notification_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, channel TEXT NOT NULL DEFAULT 'in_app', target TEXT NOT NULL DEFAULT '', owner_id INTEGER REFERENCES owners(id), bill_id INTEGER REFERENCES bills(id), order_no TEXT, payload TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', error_message TEXT, created_at TEXT DEFAULT (datetime('now','localtime')), sent_at TEXT);
    """
    c.executescript(SQL)
    for col in ['contract_start','contract_end','id_card','id_card_front','id_card_back','business_type','water_rate_type']:
        try: c.execute(f"ALTER TABLE rooms ADD COLUMN {col} TEXT")
        except: pass
    try: c.execute("ALTER TABLE fee_types ADD COLUMN reminder_advance_days INTEGER DEFAULT 30")
    except: pass
    for col_sql in [
        "ALTER TABLE payments ADD COLUMN receipt_number TEXT",
        "ALTER TABLE bills ADD COLUMN source TEXT DEFAULT 'normal'",
        "ALTER TABLE bills ADD COLUMN source_ref TEXT",
    ]:
        try: c.execute(col_sql)
        except: pass
    if c.execute("SELECT COUNT(*) FROM fee_types").fetchone()[0] == 0:
        for f in [('物业费(居民)','area',1.9,'元/m²·月','monthly',1,'按建筑面积×1.9计算'),
                  ('物业费(商户)','area',5.0,'元/m²·月','monthly',2,'按建筑面积×5.0计算'),
                  ('电梯费','floor',1.0,'元/m²·月','monthly',3,'7-11层1.0，12-16层1.05，17-21层1.1，22-26层1.15元/m²'),
                  ('二次供水运行费','area',0.5,'元/m²·月','monthly',4,'按房屋平方计价'),
                  ('水费(非居民)','meter',5.8,'元/m³','monthly',5,'按用量×5.8计算'),
                  ('水费(特行)','meter',20.11,'元/m³','monthly',6,'按用量×20.11计算'),
                  ('公摊能耗费','household',10,'元/户·月','monthly',7,'按户计费'),
                  ('生活垃圾费','household',10,'元/户·月','monthly',8,'按户计费')]:
            c.execute("INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes) VALUES(?,?,?,?,?,?,1,?)", f)
    try: c.execute("UPDATE fee_types SET is_active=0 WHERE name IN ('物业费','水费') AND (SELECT COUNT(*) FROM fee_types WHERE name LIKE '物业费(%')>0")
    except: pass
    if c.execute("SELECT COUNT(*) FROM fee_types WHERE name='物业费(居民)'").fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes) SELECT '物业费(居民)','area',1.9,'元/m²·月','monthly',1,1,'按建筑面积×1.9计算' WHERE (SELECT COUNT(*) FROM fee_types WHERE name='物业费(居民)')=0")
        c.execute("INSERT OR IGNORE INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes) SELECT '物业费(商户)','area',5.0,'元/m²·月','monthly',2,1,'按建筑面积×5.0计算' WHERE (SELECT COUNT(*) FROM fee_types WHERE name='物业费(商户)')=0")
        c.execute("INSERT OR IGNORE INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes) SELECT '水费(非居民)','meter',5.8,'元/m³','monthly',5,1,'按用量×5.8计算' WHERE (SELECT COUNT(*) FROM fee_types WHERE name='水费(非居民)')=0")
        c.execute("INSERT OR IGNORE INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes) SELECT '水费(特行)','meter',20.11,'元/m³','monthly',6,1,'按用量×20.11计算' WHERE (SELECT COUNT(*) FROM fee_types WHERE name='水费(特行)')=0")
        for old_name in ['物业费','水费']:
            try: c.execute("UPDATE fee_types SET sort_order=sort_order+20 WHERE name=? AND (SELECT COUNT(*) FROM fee_types WHERE name LIKE ?||'(%')>0", (old_name, old_name))
            except: pass
    commercial_new = [
        ('电费(商业)','meter',0.85,'元/度','monthly',31,'按用电量×单价计算，适用于商业用户'),
        ('垃圾清运费','household',30,'元/户·月','monthly',32,'商业垃圾清运服务费'),
        ('装修管理费','area',3.0,'元/m²','monthly',33,'装修期间管理服务费，按面积收取'),
        ('装修押金','fixed',2000,'元','monthly',34,'装修完工验收合格后退还'),
        ('泄水费','area',1.5,'元/m²','monthly',35,'排水设施维护费，按面积收取'),
        ('空调费(商业)','area',2.5,'元/m²·月','monthly',36,'中央空调使用费，按面积收取'),
        ('停车费','fixed',300,'元/月','monthly',37,'车位使用费，按户/按月收取'),
        ('临时收费','fixed',0,'元','monthly',38,'临时性收费项目，每次单独设定金额'),
    ]
    for cf in commercial_new:
        exists = c.execute("SELECT id FROM fee_types WHERE name=?", (cf[0],)).fetchone()
        if not exists:
            c.execute("INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes) VALUES(?,?,?,?,?,?,1,?)", cf)
    if c.execute("SELECT COUNT(*) FROM elevator_fee_tiers").fetchone()[0] == 0:
        for t in [(7,11,1.0,'7-11层'),(12,16,1.05,'12-16层'),(17,21,1.1,'17-21层'),(22,26,1.15,'22-26层')]:
            c.execute("INSERT INTO elevator_fee_tiers(floor_from,floor_to,rate,label) VALUES(?,?,?,?)", t)
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        default_pw = os.environ.get('PM_ADMIN_PASSWORD', 'admin123')
        admin_pw = hashlib.sha256(default_pw.encode()).hexdigest()
        c.execute("INSERT INTO users(username,password_hash,display_name,role) VALUES(?,?,?,?)", ('admin', admin_pw, '管理员', 'admin'))
    if c.execute("SELECT COUNT(*) FROM late_fee_config").fetchone()[0] == 0:
        c.execute("INSERT INTO late_fee_config(name,daily_rate,max_rate,grace_days,is_active) VALUES('滞纳金',0.001,0.05,0,1)")
    for idx_sql in ["CREATE INDEX IF NOT EXISTS idx_bills_period ON bills(billing_period)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_room ON bills(room_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_fee_type ON bills(fee_type_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_period_status ON bills(billing_period,status)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_period_room ON bills(billing_period,room_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_period_fee ON bills(billing_period,fee_type_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_due_status ON bills(due_date,status)",
                     "CREATE INDEX IF NOT EXISTS idx_payments_bill ON payments(bill_id)",
                     "CREATE INDEX IF NOT EXISTS idx_payments_bill_date ON payments(bill_id,payment_date)",
                     "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)",
                     "CREATE INDEX IF NOT EXISTS idx_meter_period ON meter_readings(period)",
                     "CREATE INDEX IF NOT EXISTS idx_meter_room_period ON meter_readings(room_id,fee_type_id,period)",
                     "CREATE INDEX IF NOT EXISTS idx_rooms_building ON rooms(building)",
                     "CREATE INDEX IF NOT EXISTS idx_rooms_building_room ON rooms(building,room_number)",
                     "CREATE INDEX IF NOT EXISTS idx_rooms_owner ON rooms(owner_id)",
                     "CREATE INDEX IF NOT EXISTS idx_rooms_category ON rooms(category)",
                     "CREATE INDEX IF NOT EXISTS idx_owners_name ON owners(name)",
                     "CREATE INDEX IF NOT EXISTS idx_owners_phone ON owners(phone)",
                     "CREATE INDEX IF NOT EXISTS idx_repairs_status ON repairs(status)",
                     "CREATE INDEX IF NOT EXISTS idx_repairs_room ON repairs(room_id)",
                     "CREATE INDEX IF NOT EXISTS idx_deposits_status ON deposits(status)",
                     "CREATE INDEX IF NOT EXISTS idx_deposits_room ON deposits(room_id)",
                     "CREATE INDEX IF NOT EXISTS idx_parking_status ON parking_spots(status)",
                     "CREATE INDEX IF NOT EXISTS idx_parking_room ON parking_spots(room_id)",
                     "CREATE INDEX IF NOT EXISTS idx_fee_tiers_type ON fee_type_tiers(fee_type_id)",
                     "CREATE INDEX IF NOT EXISTS idx_adj_bill ON bill_adjustments(bill_id)",
                     "CREATE INDEX IF NOT EXISTS idx_adjustments_bill_created ON bill_adjustments(bill_id,created_at,id)",
                     "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at,id)",
                     "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type,entity_id)",
                     "CREATE INDEX IF NOT EXISTS idx_shared_runs_period ON shared_expense_runs(period,fee_type_id)",
                     "CREATE INDEX IF NOT EXISTS idx_payments_receipt ON payments(receipt_number)",
                     "CREATE INDEX IF NOT EXISTS idx_notification_status ON notification_events(status)",
                     "CREATE INDEX IF NOT EXISTS idx_notification_owner ON notification_events(owner_id,created_at,id)",
                     "CREATE INDEX IF NOT EXISTS idx_invoice_requests_status ON invoice_requests(status)",
                     "CREATE INDEX IF NOT EXISTS idx_invoice_requests_owner ON invoice_requests(owner_id,created_at,id)"]:
        try: c.execute(idx_sql)
        except: pass
    conn.commit(); conn.close()
    cleanup_old_sessions()


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
    return round(rate * area, 2)


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
    fee = round(bill['amount'] * cfg['daily_rate'] * days, 2)
    max_fee = round(bill['amount'] * cfg['max_rate'], 2)
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
    return f"{float(v or 0):.2f}"
