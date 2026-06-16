#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Database migration helpers."""

import re

def _migrate_merchant_contract_room_nullable(conn):
    """Allow archive contracts to exist without a room link in upgraded DBs."""
    info = conn.execute("PRAGMA table_info(merchant_contracts)").fetchall()
    room_col = next((col for col in info if col["name"] == "room_id"), None)
    if not room_col or not room_col["notnull"]:
        return
    existing = {col["name"] for col in info}
    target_cols = [
        "id", "project_id", "room_id", "commercial_space_id", "owner_id", "contract_no",
        "merchant_name", "shop_name", "rent_amount", "rent_cycle", "property_rate",
        "property_cycle", "deposit_amount", "contract_area", "building_area", "start_date",
        "end_date", "status", "notes", "created_at",
    ]

    def source_expr(col):
        defaults = {
            "project_id": "1",
            "commercial_space_id": "NULL",
            "owner_id": "NULL",
            "shop_name": "NULL",
            "rent_amount": "0",
            "rent_cycle": "'monthly'",
            "property_rate": "0",
            "property_cycle": "'monthly'",
            "deposit_amount": "0",
            "contract_area": "0",
            "building_area": "0",
            "status": "'active'",
            "notes": "NULL",
            "created_at": "datetime('now','localtime')",
        }
        return col if col in existing else defaults.get(col, "NULL")

    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("ALTER TABLE merchant_contracts RENAME TO merchant_contracts_old_room_required")
    conn.execute(
        """CREATE TABLE merchant_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL DEFAULT 1,
            room_id INTEGER REFERENCES rooms(id),
            commercial_space_id INTEGER REFERENCES commercial_spaces(id),
            owner_id INTEGER REFERENCES owners(id),
            contract_no TEXT NOT NULL UNIQUE,
            merchant_name TEXT NOT NULL,
            shop_name TEXT,
            rent_amount REAL NOT NULL DEFAULT 0,
            rent_cycle TEXT NOT NULL DEFAULT 'monthly',
            property_rate REAL NOT NULL DEFAULT 0,
            property_cycle TEXT NOT NULL DEFAULT 'monthly',
            deposit_amount REAL NOT NULL DEFAULT 0,
            contract_area REAL NOT NULL DEFAULT 0,
            building_area REAL NOT NULL DEFAULT 0,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )"""
    )
    select_cols = ", ".join(source_expr(col) for col in target_cols)
    conn.execute(
        f"""INSERT INTO merchant_contracts({", ".join(target_cols)})
            SELECT {select_cols} FROM merchant_contracts_old_room_required"""
    )
    conn.execute("DROP TABLE merchant_contracts_old_room_required")
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")


def _migrate_bills_room_nullable(conn):
    """Allow contract-space bills to exist without a room link in upgraded DBs."""
    info = conn.execute("PRAGMA table_info(bills)").fetchall()
    room_col = next((col for col in info if col["name"] == "room_id"), None)
    if not room_col or not room_col["notnull"]:
        return
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bills'").fetchone()
    create_sql = row["sql"] if row else ""
    relaxed_sql = _relax_bills_room_id_sql(create_sql)
    columns = [col["name"] for col in info]
    col_list = ", ".join(columns)

    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("ALTER TABLE bills RENAME TO bills_old_room_required")
    conn.execute(relaxed_sql)
    conn.execute(f"INSERT INTO bills({col_list}) SELECT {col_list} FROM bills_old_room_required")
    conn.execute("DROP TABLE bills_old_room_required")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_bills_bill_number_unique ON bills(bill_number)")
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")


def _migrate_meter_readings_room_nullable(conn):
    """Allow commercial-space meter readings to exist without a room link."""
    info = conn.execute("PRAGMA table_info(meter_readings)").fetchall()
    room_col = next((col for col in info if col["name"] == "room_id"), None)
    if not room_col or not room_col["notnull"]:
        return
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='meter_readings'").fetchone()
    create_sql = row["sql"] if row else ""
    relaxed_sql = _relax_meter_readings_room_id_sql(create_sql)
    columns = [col["name"] for col in info]
    col_list = ", ".join(columns)

    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("ALTER TABLE meter_readings RENAME TO meter_readings_old_room_required")
    conn.execute(relaxed_sql)
    conn.execute(f"INSERT INTO meter_readings({col_list}) SELECT {col_list} FROM meter_readings_old_room_required")
    conn.execute("DROP TABLE meter_readings_old_room_required")
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")


def _relax_bills_room_id_sql(create_sql):
    sql = re.sub(r'CREATE TABLE\s+"?bills"?', "CREATE TABLE bills", create_sql, count=1)
    relaxed = re.sub(
        r"room_id\s+INTEGER\s+NOT\s+NULL\s+REFERENCES\s+rooms\(id\)",
        "room_id INTEGER REFERENCES rooms(id)",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
    relaxed = re.sub(
        r"room_id\s+INTEGER\s+NOT\s+NULL",
        "room_id INTEGER",
        relaxed,
        count=1,
        flags=re.IGNORECASE,
    )
    if "ROOM_ID INTEGER NOT NULL" in relaxed.upper():
        raise RuntimeError("failed to relax bills.room_id NOT NULL")
    return relaxed


def _relax_meter_readings_room_id_sql(create_sql):
    sql = re.sub(r'CREATE TABLE\s+"?meter_readings"?', "CREATE TABLE meter_readings", create_sql, count=1)
    relaxed = re.sub(
        r"room_id\s+INTEGER\s+NOT\s+NULL\s+REFERENCES\s+rooms\(id\)",
        "room_id INTEGER REFERENCES rooms(id)",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
    relaxed = re.sub(
        r"room_id\s+INTEGER\s+NOT\s+NULL",
        "room_id INTEGER",
        relaxed,
        count=1,
        flags=re.IGNORECASE,
    )
    if "ROOM_ID INTEGER NOT NULL" in relaxed.upper():
        raise RuntimeError("failed to relax meter_readings.room_id NOT NULL")
    return relaxed
