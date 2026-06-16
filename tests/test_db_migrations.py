#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Database migration regression tests."""

import sqlite3

from server.db_migrations import _migrate_bills_room_nullable, _migrate_meter_readings_room_nullable


def test_bills_room_id_migration_allows_contract_space_bills(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE rooms (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE commercial_spaces (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE owners (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE fee_types (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            commercial_space_id INTEGER REFERENCES commercial_spaces(id),
            owner_id INTEGER REFERENCES owners(id),
            fee_type_id INTEGER NOT NULL REFERENCES fee_types(id),
            billing_period TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            due_date TEXT,
            status TEXT DEFAULT 'unpaid',
            bill_number TEXT UNIQUE,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            source TEXT DEFAULT 'normal',
            source_ref TEXT
        );
        INSERT INTO rooms(id) VALUES(1);
        INSERT INTO commercial_spaces(id) VALUES(2);
        INSERT INTO owners(id) VALUES(3);
        INSERT INTO fee_types(id) VALUES(4);
        INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,bill_number)
        VALUES(1,3,4,'2026-06',88,'OLD-001');
        """
    )
    _migrate_bills_room_nullable(conn)

    room_col = next(c for c in conn.execute("PRAGMA table_info(bills)") if c["name"] == "room_id")
    assert room_col["notnull"] == 0
    old = conn.execute("SELECT room_id,amount,bill_number FROM bills WHERE bill_number='OLD-001'").fetchone()
    assert dict(old) == {"room_id": 1, "amount": 88, "bill_number": "OLD-001"}

    conn.execute(
        """INSERT INTO bills(room_id,commercial_space_id,owner_id,fee_type_id,billing_period,amount,bill_number,source,source_ref)
        VALUES(NULL,2,3,4,'2026-07',99,'CONTRACT-001','merchant_contract','9')"""
    )
    inserted = conn.execute("SELECT room_id,commercial_space_id FROM bills WHERE bill_number='CONTRACT-001'").fetchone()
    assert inserted["room_id"] is None
    assert inserted["commercial_space_id"] == 2
    conn.close()


def test_meter_readings_room_id_migration_allows_commercial_space_readings(tmp_path):
    db_path = tmp_path / "old_meter.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE rooms (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE commercial_spaces (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE fee_types (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE meter_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            commercial_space_id INTEGER REFERENCES commercial_spaces(id),
            fee_type_id INTEGER NOT NULL REFERENCES fee_types(id),
            period TEXT NOT NULL,
            previous_reading REAL DEFAULT 0,
            current_reading REAL DEFAULT 0,
            consumption REAL DEFAULT 0,
            reading_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO rooms(id) VALUES(1);
        INSERT INTO commercial_spaces(id) VALUES(2);
        INSERT INTO fee_types(id) VALUES(3);
        INSERT INTO meter_readings(room_id,fee_type_id,period,current_reading,previous_reading,consumption,status)
        VALUES(1,3,'202606',10,0,10,'confirmed');
        """
    )
    _migrate_meter_readings_room_nullable(conn)

    room_col = next(c for c in conn.execute("PRAGMA table_info(meter_readings)") if c["name"] == "room_id")
    assert room_col["notnull"] == 0
    old = conn.execute("SELECT room_id,current_reading FROM meter_readings WHERE period='202606'").fetchone()
    assert dict(old) == {"room_id": 1, "current_reading": 10}

    conn.execute(
        """INSERT INTO meter_readings(room_id,commercial_space_id,fee_type_id,period,current_reading,previous_reading,consumption,status)
        VALUES(NULL,2,3,'202607',20,10,10,'draft')"""
    )
    inserted = conn.execute("SELECT room_id,commercial_space_id FROM meter_readings WHERE period='202607'").fetchone()
    assert inserted["room_id"] is None
    assert inserted["commercial_space_id"] == 2
    conn.close()
