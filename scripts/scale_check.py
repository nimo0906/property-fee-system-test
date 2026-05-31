#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a temporary large dataset and time core billing queries."""

import os
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _configure_temp_db():
    fd, db_path = tempfile.mkstemp(prefix="property_scale_", suffix=".db")
    os.close(fd)
    os.environ["PM_DB_PATH"] = db_path
    os.environ["PM_BACKUP_DIR"] = tempfile.mkdtemp(prefix="property_scale_backups_")
    return db_path


def _seed_large_dataset(db, rooms, months, fee_limit):
    fee_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM fee_types WHERE is_active=1 ORDER BY sort_order LIMIT ?",
            (fee_limit,),
        ).fetchall()
    ]
    periods = [f"2035-{m:02d}" for m in range(1, months + 1)]
    start = time.perf_counter()
    db.execute("BEGIN")
    for i in range(rooms):
        cur = db.execute(
            "INSERT INTO owners(name,phone) VALUES(?,?)",
            (f"压力商户{i:04d}", f"139{i:08d}"[:11]),
        )
        owner_id = cur.lastrowid
        building = f"T{i % 12 + 1:02d}"
        room_number = f"{700 + i // 100}{i % 100:02d}"
        room = db.execute(
            "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (building, "A座", room_number, 7 + i % 20, "商户", 40 + (i % 160), owner_id),
        )
        room_id = room.lastrowid
        for period in periods:
            for fee_id in fee_ids:
                area = 40 + (i % 160)
                amount = round(area * (1 + fee_id * 0.17), 2)
                status = "paid" if (i + fee_id) % 5 == 0 else "overdue" if (i + fee_id) % 7 == 0 else "unpaid"
                db.execute(
                    "INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (room_id, owner_id, fee_id, period, amount, period + "-28", status, f"SCALE_{room_id}_{fee_id}_{period}"),
                )
    db.commit()
    return time.perf_counter() - start, len(periods), len(fee_ids)


def _timed(db, name, sql, vals=()):
    start = time.perf_counter()
    rows = db.execute(sql, vals).fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"{name}: rows={len(rows)} ms={elapsed_ms:.2f}")
    return elapsed_ms


def main():
    rooms = int(os.environ.get("SCALE_ROOMS", "3000"))
    months = int(os.environ.get("SCALE_MONTHS", "12"))
    fee_limit = int(os.environ.get("SCALE_FEE_LIMIT", "8"))
    db_path = _configure_temp_db()

    from server.db import db_init, get_db

    db_init()
    db = get_db()
    seed_seconds, period_count, fee_count = _seed_large_dataset(db, rooms, months, fee_limit)
    bill_count = db.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
    print(f"dataset: rooms={rooms} periods={period_count} fee_types={fee_count} bills={bill_count} seed_s={seed_seconds:.2f}")

    period = "2035-05" if months >= 5 else "2035-01"
    _timed(db, "bill_list_page", """SELECT b.*,r.building,r.unit,r.room_number,r.category,f.name ft,o.name owner_name,
        COALESCE((SELECT SUM(amount_paid) FROM payments WHERE bill_id=b.id),0) paid
        FROM bills b LEFT JOIN rooms r ON b.room_id=r.id
        LEFT JOIN fee_types f ON b.fee_type_id=f.id LEFT JOIN owners o ON b.owner_id=o.id
        WHERE b.billing_period=?
        ORDER BY r.building,r.unit,r.room_number,b.fee_type_id LIMIT 50 OFFSET 0""", (period,))
    _timed(db, "bill_list_count", """SELECT COUNT(*) FROM bills b
        LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types f ON b.fee_type_id=f.id
        LEFT JOIN owners o ON b.owner_id=o.id WHERE b.billing_period=?""", (period,))
    _timed(db, "building_filter", """SELECT b.id,r.building,r.room_number,b.amount,b.status
        FROM bills b JOIN rooms r ON b.room_id=r.id
        WHERE b.billing_period=? AND r.building=?
        ORDER BY r.room_number,b.fee_type_id LIMIT 100""", (period, "T03"))
    _timed(db, "status_summary", "SELECT status,COUNT(*) cnt,COALESCE(SUM(amount),0) total FROM bills WHERE billing_period=? GROUP BY status", (period,))
    _timed(db, "reports_building", """SELECT r.building,COUNT(b.id),COALESCE(SUM(b.amount),0)
        FROM bills b JOIN rooms r ON b.room_id=r.id
        WHERE b.billing_period=? GROUP BY r.building ORDER BY r.building""", (period,))
    print(f"db_path: {db_path}")
    db.close()


if __name__ == "__main__":
    main()
