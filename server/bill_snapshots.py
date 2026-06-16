#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bill customer/object snapshot helpers."""

SNAPSHOT_COLUMNS = [
    ('customer_name_snapshot', 'TEXT'),
    ('customer_phone_snapshot', 'TEXT'),
    ('object_label_snapshot', 'TEXT'),
    ('contract_no_snapshot', 'TEXT'),
]


def ensure_bill_snapshot_columns(db):
    for name, typ in SNAPSHOT_COLUMNS:
        try:
            db.execute(f"ALTER TABLE bills ADD COLUMN {name} {typ}")
        except Exception:
            pass


def room_snapshot(db, room_id, owner_id=None):
    row = db.execute(
        """SELECT r.*,o.name owner_name,o.phone owner_phone
           FROM rooms r LEFT JOIN owners o ON o.id=COALESCE(?,r.owner_id)
           WHERE r.id=?""",
        (owner_id, room_id),
    ).fetchone()
    if not row:
        return {}
    return {
        'customer_name_snapshot': row['tenant_name'] or row['shop_name'] or row['owner_name'] or '',
        'customer_phone_snapshot': row['tenant_phone'] or row['owner_phone'] or '',
        'object_label_snapshot': f"{row['building'] or ''}-{row['unit'] or ''}-{row['room_number'] or ''}",
        'contract_no_snapshot': '',
    }


def contract_snapshot(db, contract_id):
    row = db.execute(
        """SELECT c.contract_no,c.merchant_name,c.shop_name,
                  s.space_no,s.shop_name space_shop,s.merchant_name space_merchant,
                  r.building,r.unit,r.room_number,r.tenant_name,r.tenant_phone,
                  o.name owner_name,o.phone owner_phone
           FROM merchant_contracts c
           LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
           LEFT JOIN rooms r ON c.room_id=r.id
           LEFT JOIN owners o ON c.owner_id=o.id
           WHERE c.id=?""",
        (contract_id,),
    ).fetchone()
    if not row:
        return {}
    if row['space_no']:
        label = f"商场-{row['space_no']}"
    else:
        label = f"{row['building'] or ''}-{row['unit'] or ''}-{row['room_number'] or ''}"
    customer = row['merchant_name'] or row['space_merchant'] or row['space_shop'] or row['tenant_name'] or row['owner_name'] or ''
    return {
        'customer_name_snapshot': customer,
        'customer_phone_snapshot': row['owner_phone'] or row['tenant_phone'] or '',
        'object_label_snapshot': label,
        'contract_no_snapshot': row['contract_no'] or '',
    }


def apply_snapshot(db, bill_id, snapshot):
    if not snapshot:
        return
    ensure_bill_snapshot_columns(db)
    db.execute(
        """UPDATE bills SET customer_name_snapshot=?,customer_phone_snapshot=?,
           object_label_snapshot=?,contract_no_snapshot=? WHERE id=?""",
        (
            snapshot.get('customer_name_snapshot') or '',
            snapshot.get('customer_phone_snapshot') or '',
            snapshot.get('object_label_snapshot') or '',
            snapshot.get('contract_no_snapshot') or '',
            bill_id,
        ),
    )


def backfill_bill_snapshots(db, limit=5000):
    """Fill missing snapshots for existing bills without overwriting populated rows."""
    ensure_bill_snapshot_columns(db)
    rows = db.execute(
        """SELECT id,room_id,owner_id,source,source_ref
           FROM bills
           WHERE COALESCE(customer_name_snapshot,'')=''
           ORDER BY id LIMIT ?""",
        (limit,),
    ).fetchall()
    count = 0
    for row in rows:
        snap = {}
        if row['source'] == 'merchant_contract' and row['source_ref']:
            try:
                snap = contract_snapshot(db, int(row['source_ref']))
            except Exception:
                snap = {}
        if not snap and row['room_id']:
            snap = room_snapshot(db, row['room_id'], row['owner_id'])
        if snap:
            apply_snapshot(db, row['id'], snap)
            count += 1
    return count
