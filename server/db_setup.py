#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Database schema creation, migrations, seeds, and indexes."""

import os
from server.passwords import hash_password
from server.bill_snapshots import backfill_bill_snapshots
from server.contract_amendments import ensure_contract_amendment_tables
from server.special_rent import ensure_special_rent_tables

def run_db_init(get_db, cleanup_old_sessions, dedupe_renamed_fee_type,
                migrate_merchant_contract_room_nullable, migrate_bills_room_nullable,
                migrate_meter_readings_room_nullable):
    conn = get_db(); c = conn.cursor()
    SQL = """
        CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS owners (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, id_card TEXT, move_in_date TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS rooms (id INTEGER PRIMARY KEY AUTOINCREMENT, building TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '1单元', room_number TEXT NOT NULL, floor INTEGER DEFAULT 1, category TEXT DEFAULT '居民', area REAL NOT NULL DEFAULT 0, owner_id INTEGER REFERENCES owners(id), custom_rate REAL, contract_start TEXT, contract_end TEXT, id_card TEXT, id_card_front TEXT, id_card_back TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS commercial_spaces (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL DEFAULT 1, space_no TEXT NOT NULL UNIQUE, floor INTEGER DEFAULT 1, area REAL NOT NULL DEFAULT 0, shop_name TEXT, merchant_name TEXT, business_type TEXT, water_rate_type TEXT DEFAULT '非居民', status TEXT NOT NULL DEFAULT 'active', notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS fee_types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, calc_method TEXT NOT NULL DEFAULT 'fixed', unit_price REAL NOT NULL DEFAULT 0, unit TEXT, billing_cycle TEXT NOT NULL DEFAULT 'monthly', is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS meter_readings (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER REFERENCES rooms(id), commercial_space_id INTEGER REFERENCES commercial_spaces(id), fee_type_id INTEGER NOT NULL REFERENCES fee_types(id), period TEXT NOT NULL, previous_reading REAL DEFAULT 0, current_reading REAL DEFAULT 0, consumption REAL DEFAULT 0, reading_date TEXT, status TEXT DEFAULT 'draft', notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS bills (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER REFERENCES rooms(id), commercial_space_id INTEGER REFERENCES commercial_spaces(id), owner_id INTEGER REFERENCES owners(id), fee_type_id INTEGER NOT NULL REFERENCES fee_types(id), billing_period TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0, due_date TEXT, status TEXT DEFAULT 'unpaid', bill_number TEXT UNIQUE, paid_at TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
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
        CREATE TABLE IF NOT EXISTS notification_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, channel TEXT NOT NULL DEFAULT 'in_app', target TEXT NOT NULL DEFAULT '', owner_id INTEGER REFERENCES owners(id), bill_id INTEGER REFERENCES bills(id), order_no TEXT, payload TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', error_message TEXT, created_at TEXT DEFAULT (datetime('now','localtime')), sent_at TEXT);
        CREATE TABLE IF NOT EXISTS auto_billing_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_no TEXT NOT NULL UNIQUE, operator TEXT, advance_days INTEGER DEFAULT 30, fee_ids TEXT, generated_count INTEGER DEFAULT 0, rollback_count INTEGER DEFAULT 0, status TEXT DEFAULT 'generated', service_start_min TEXT, service_end_max TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')), rolled_back_at TEXT);
        CREATE TABLE IF NOT EXISTS merchant_contracts (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL DEFAULT 1, room_id INTEGER REFERENCES rooms(id), commercial_space_id INTEGER REFERENCES commercial_spaces(id), owner_id INTEGER REFERENCES owners(id), contract_no TEXT NOT NULL UNIQUE, merchant_name TEXT NOT NULL, shop_name TEXT, rent_amount REAL NOT NULL DEFAULT 0, rent_cycle TEXT NOT NULL DEFAULT 'monthly', property_rate REAL NOT NULL DEFAULT 0, property_cycle TEXT NOT NULL DEFAULT 'monthly', deposit_amount REAL NOT NULL DEFAULT 0, contract_area REAL NOT NULL DEFAULT 0, building_area REAL NOT NULL DEFAULT 0, start_date TEXT NOT NULL, end_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS contract_bill_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL DEFAULT 1, contract_id INTEGER NOT NULL REFERENCES merchant_contracts(id), billing_period TEXT NOT NULL, generated_count INTEGER NOT NULL DEFAULT 0, total_amount REAL NOT NULL DEFAULT 0, operator TEXT, created_at TEXT DEFAULT (datetime('now','localtime')), UNIQUE(contract_id,billing_period));
        CREATE TABLE IF NOT EXISTS contract_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL REFERENCES merchant_contracts(id), attachment_type TEXT, original_name TEXT NOT NULL, stored_name TEXT NOT NULL, file_ext TEXT NOT NULL, mime_type TEXT, file_size INTEGER NOT NULL DEFAULT 0, uploaded_by TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
    """
    c.executescript(SQL)
    ensure_contract_amendment_tables(conn)
    ensure_special_rent_tables(conn)
    for col in ['contract_start','contract_end','id_card','id_card_front','id_card_back','business_type','water_rate_type','shop_name','tenant_name','tenant_phone','tenant_id_card','tenant_id_card_front','tenant_id_card_back','payment_cycle']:
        try: c.execute(f"ALTER TABLE rooms ADD COLUMN {col} TEXT")
        except: pass
    try: c.execute("ALTER TABLE fee_types ADD COLUMN reminder_advance_days INTEGER DEFAULT 30")
    except: pass
    for table in ['owners','rooms','commercial_spaces','fee_types','bills','payments','invoices','invoice_requests','notification_events']:
        try: c.execute(f"ALTER TABLE {table} ADD COLUMN project_id INTEGER DEFAULT 1")
        except: pass
    for col_sql in [
        "ALTER TABLE bills ADD COLUMN customer_name_snapshot TEXT",
        "ALTER TABLE bills ADD COLUMN customer_phone_snapshot TEXT",
        "ALTER TABLE bills ADD COLUMN object_label_snapshot TEXT",
        "ALTER TABLE bills ADD COLUMN contract_no_snapshot TEXT",
    ]:
        try: c.execute(col_sql)
        except: pass
    for col_sql in [
        "ALTER TABLE payments ADD COLUMN receipt_number TEXT",
        "ALTER TABLE bills ADD COLUMN commercial_space_id INTEGER REFERENCES commercial_spaces(id)",
        "ALTER TABLE bills ADD COLUMN source TEXT DEFAULT 'normal'",
        "ALTER TABLE bills ADD COLUMN source_ref TEXT",
        "ALTER TABLE bills ADD COLUMN service_start TEXT",
        "ALTER TABLE bills ADD COLUMN service_end TEXT",
        "ALTER TABLE bills ADD COLUMN auto_batch_no TEXT",
    ]:
        try: c.execute(col_sql)
        except: pass
    c.execute("INSERT OR IGNORE INTO projects(id,code,name,is_active,notes) VALUES(1,'default','默认项目',1,'单项目兼容默认项目')")
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
        ('物业费(商业)','area',5.0,'元/m²·月','monthly',30,'按商业合同/商铺面积×单价计算'),
        ('电费(商业)','meter',0.85,'元/度','monthly',31,'按用电量×单价计算，适用于商业用户'),
        ('垃圾清运费','household',30,'元/户','once',32,'商业垃圾清运服务费，一次性固定收取'),
        ('装修管理费','area',3.0,'元/m²','once',33,'装修期间管理服务费，一次性按面积收取'),
        ('装修押金','fixed',2000,'元','once',34,'装修完工验收合格后退还'),
        ('泄水费','area',1.5,'元/m²','once',35,'排水设施维护费，一次性按面积收取'),
        ('空调费(商业)','area',2.5,'元/m²·月','monthly',36,'中央空调使用费，按面积收取'),
        ('停车费','fixed',300,'元/月','monthly',37,'车位使用费，按户/按月收取'),
        ('临时收费','fixed',0,'元','monthly',38,'临时性收费项目，每次单独设定金额'),
    ]
    for cf in commercial_new:
        exists = c.execute("SELECT id FROM fee_types WHERE name=?", (cf[0],)).fetchone()
        if not exists:
            c.execute("INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes) VALUES(?,?,?,?,?,?,1,?)", cf)
    for one_time_name in ('垃圾清运费', '装修管理费', '装修押金', '泄水费', '临时收费'):
        try: c.execute("UPDATE fee_types SET billing_cycle='once' WHERE name=?", (one_time_name,))
        except: pass
    dedupe_renamed_fee_type(c, '空调费(商业)', '空调能源费')
    if c.execute("SELECT COUNT(*) FROM elevator_fee_tiers").fetchone()[0] == 0:
        for t in [(7,11,1.0,'7-11层'),(12,16,1.05,'12-16层'),(17,21,1.1,'17-21层'),(22,26,1.15,'22-26层')]:
            c.execute("INSERT INTO elevator_fee_tiers(floor_from,floor_to,rate,label) VALUES(?,?,?,?)", t)
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        default_pw = os.environ.get('PM_ADMIN_PASSWORD', 'admin123')
        admin_pw = hash_password(default_pw)
        c.execute("INSERT INTO users(username,password_hash,display_name,role) VALUES(?,?,?,?)", ('admin', admin_pw, '管理员', 'admin'))
    if c.execute("SELECT COUNT(*) FROM late_fee_config").fetchone()[0] == 0:
        c.execute("INSERT INTO late_fee_config(name,daily_rate,max_rate,grace_days,is_active) VALUES('滞纳金',0.001,0.05,0,1)")
    for col_sql in [
        "ALTER TABLE merchant_contracts ADD COLUMN commercial_space_id INTEGER REFERENCES commercial_spaces(id)",
        "ALTER TABLE merchant_contracts ADD COLUMN contract_area REAL NOT NULL DEFAULT 0",
        "ALTER TABLE merchant_contracts ADD COLUMN building_area REAL NOT NULL DEFAULT 0",
        "ALTER TABLE meter_readings ADD COLUMN commercial_space_id INTEGER REFERENCES commercial_spaces(id)",
    ]:
        try: c.execute(col_sql)
        except: pass
    migrate_merchant_contract_room_nullable(conn)
    migrate_bills_room_nullable(conn)
    migrate_meter_readings_room_nullable(conn)
    for idx_sql in ["CREATE INDEX IF NOT EXISTS idx_bills_period ON bills(billing_period)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_room ON bills(room_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_fee_type ON bills(fee_type_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_period_status ON bills(billing_period,status)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_period_room ON bills(billing_period,room_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_period_fee ON bills(billing_period,fee_type_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_due_status ON bills(due_date,status)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_service_period ON bills(room_id,fee_type_id,service_start,service_end)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_auto_batch ON bills(auto_batch_no)",
                     "CREATE INDEX IF NOT EXISTS idx_auto_billing_runs_batch ON auto_billing_runs(batch_no)",
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
                     "CREATE INDEX IF NOT EXISTS idx_invoice_requests_owner ON invoice_requests(owner_id,created_at,id)",
                     "CREATE INDEX IF NOT EXISTS idx_contracts_room ON merchant_contracts(room_id,status)",
                     "CREATE INDEX IF NOT EXISTS idx_contracts_end ON merchant_contracts(end_date,status)",
                     "CREATE INDEX IF NOT EXISTS idx_contract_runs_contract_period ON contract_bill_runs(contract_id,billing_period)",
                     "CREATE INDEX IF NOT EXISTS idx_contract_attachments_contract ON contract_attachments(contract_id,created_at,id)",
                     "CREATE INDEX IF NOT EXISTS idx_owners_project ON owners(project_id)",
                     "CREATE INDEX IF NOT EXISTS idx_spaces_no ON commercial_spaces(space_no)",
                     "CREATE INDEX IF NOT EXISTS idx_spaces_status ON commercial_spaces(status)",
                     "CREATE INDEX IF NOT EXISTS idx_meter_space_period ON meter_readings(commercial_space_id,fee_type_id,period)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_space ON bills(commercial_space_id,billing_period)",
                     "CREATE INDEX IF NOT EXISTS idx_rooms_project ON rooms(project_id)",
                     "CREATE INDEX IF NOT EXISTS idx_bills_project ON bills(project_id,status)",
                     "CREATE INDEX IF NOT EXISTS idx_payments_project ON payments(project_id)"]:
        try: c.execute(idx_sql)
        except: pass
    backfill_bill_snapshots(conn)
    conn.commit(); conn.close()
    cleanup_old_sessions()
