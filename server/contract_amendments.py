#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contract amendment draft recognition and effective rate calculation."""

import os, re
from datetime import date, timedelta
from server.billing_proration import prorated_month_factor


def ensure_contract_amendment_tables(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS contract_amendment_drafts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, attachment_id INTEGER,
      effective_date TEXT, rent_unit_price REAL, rent_amount REAL, property_rate REAL,
      rent_cycle TEXT, property_cycle TEXT, confidence REAL DEFAULT 0, raw_text TEXT, notes TEXT,
      status TEXT DEFAULT 'draft', created_at TEXT DEFAULT (datetime('now','localtime')));
    CREATE TABLE IF NOT EXISTS contract_amendments(
      id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, attachment_id INTEGER,
      effective_date TEXT NOT NULL, rent_unit_price REAL, rent_amount REAL, property_rate REAL,
      rent_cycle TEXT, property_cycle TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
    CREATE INDEX IF NOT EXISTS idx_contract_amendments_contract_date ON contract_amendments(contract_id,effective_date,id);
    CREATE INDEX IF NOT EXISTS idx_contract_drafts_contract ON contract_amendment_drafts(contract_id,status,id);
    """)


def extract_local_text(path):
    data = open(path, 'rb').read()
    text = data.decode('utf-8', errors='ignore')
    return re.sub(r'\s+', ' ', text)


def recognize_amendment_text(text):
    lower = text.lower()
    date_match = re.search(r'(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})', text)
    effective = f"{int(date_match.group(1)):04d}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}" if date_match else ''
    rent_unit = _number_after(lower, ['rent unit price', '租金单价', '房租单价'])
    rent_amount = _number_after(lower, ['rent amount', '月租金', '租金总额'])
    prop_rate = _number_after(lower, ['property rate', '物业费单价', '物业单价'])
    cycle = 'monthly' if 'monthly' in lower or '月' in lower else ''
    confidence = 0.2 + (0.3 if effective else 0) + (0.2 if rent_unit or rent_amount else 0) + (0.2 if prop_rate else 0)
    return {'effective_date': effective, 'rent_unit_price': rent_unit, 'rent_amount': rent_amount,
            'property_rate': prop_rate, 'rent_cycle': cycle, 'property_cycle': cycle, 'confidence': min(confidence, 0.95)}


def _number_after(text, labels):
    for label in labels:
        idx = text.find(label.lower())
        if idx >= 0:
            m = re.search(r'([0-9]+(?:\.[0-9]+)?)', text[idx + len(label):idx + len(label) + 40])
            if m: return float(m.group(1))
    return None


def create_draft_from_attachment(db, contract_id, attachment_id, path):
    ensure_contract_amendment_tables(db)
    raw = extract_local_text(path)
    parsed = recognize_amendment_text(raw)
    cur = db.execute("""INSERT INTO contract_amendment_drafts(contract_id,attachment_id,effective_date,
        rent_unit_price,rent_amount,property_rate,rent_cycle,property_cycle,confidence,raw_text,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (contract_id, attachment_id, parsed['effective_date'], parsed['rent_unit_price'],
        parsed['rent_amount'], parsed['property_rate'], parsed['rent_cycle'], parsed['property_cycle'], parsed['confidence'], raw[:4000], '本地文本识别草案'))
    return cur.lastrowid


def confirm_draft(db, draft_id, values):
    ensure_contract_amendment_tables(db)
    draft = db.execute('SELECT * FROM contract_amendment_drafts WHERE id=?', (draft_id,)).fetchone()
    if not draft: return None
    cur = db.execute("""INSERT INTO contract_amendments(contract_id,attachment_id,effective_date,rent_unit_price,
        rent_amount,property_rate,rent_cycle,property_cycle,notes) VALUES(?,?,?,?,?,?,?,?,?)""",
        (draft['contract_id'], draft['attachment_id'], values.get('effective_date') or draft['effective_date'],
         _num(values.get('rent_unit_price'), draft['rent_unit_price']), _num(values.get('rent_amount'), draft['rent_amount']),
         _num(values.get('property_rate'), draft['property_rate']), values.get('rent_cycle') or draft['rent_cycle'],
         values.get('property_cycle') or draft['property_cycle'], values.get('notes') or draft['notes']))
    db.execute("UPDATE contract_amendment_drafts SET status='confirmed' WHERE id=?", (draft_id,))
    return cur.lastrowid


def _num(value, default=None):
    if value in (None, ''): return default
    return float(value)


def amount_for_period(db, contract, kind, start, end):
    ensure_contract_amendment_tables(db)
    segments = _segments(db, contract, kind, start, end)
    total = 0.0
    for seg_start, seg_end, monthly in segments:
        total += monthly * prorated_month_factor(seg_start.isoformat(), seg_end.isoformat())
    return round(total, 2)


def _segments(db, contract, kind, start, end):
    changes = db.execute("SELECT * FROM contract_amendments WHERE contract_id=? AND effective_date<=? ORDER BY effective_date,id",
                         (contract['id'], end.isoformat())).fetchall()
    points = [c for c in changes if c['effective_date'] and c['effective_date'] > start.isoformat()]
    bounds = [start] + [date.fromisoformat(c['effective_date']) for c in points] + [end + timedelta(days=1)]
    out = []
    for i in range(len(bounds) - 1):
        seg_start, seg_end = bounds[i], bounds[i + 1] - timedelta(days=1)
        active = _active_change(changes, seg_start)
        out.append((seg_start, seg_end, _monthly(contract, active, kind)))
    return out


def _active_change(changes, day):
    active = None
    for c in changes:
        if c['effective_date'] and c['effective_date'] <= day.isoformat(): active = c
    return active


def _monthly(contract, change, kind):
    area = float(contract['area'] if 'area' in contract.keys() else contract['contract_area'] or 0)
    if kind == 'rent':
        if change and change['rent_amount'] is not None: return float(change['rent_amount'])
        if change and change['rent_unit_price'] is not None: return area * float(change['rent_unit_price'])
        return float(contract['rent_amount'] or 0)
    rate = float(change['property_rate']) if change and change['property_rate'] is not None else float(contract['property_rate'] or 0)
    return area * rate
