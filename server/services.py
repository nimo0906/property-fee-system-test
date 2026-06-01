#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable internal service interfaces for v2.0 expansion."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from server.db import get_db, room_active_in_period
from server.billing_engine import calculate_bill_amount, fee_applies_to_room


class ServiceError(Exception):
    """Business-level service error safe to show to operators."""


@dataclass(frozen=True)
class Actor:
    username: str = ''
    role: str = ''


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _mask_id_card(value):
    text = str(value or '').strip()
    if len(text) <= 8:
        return text
    return text[:6] + '*' * (len(text) - 10) + text[-4:]


class OwnerService:
    def get_owner(self, owner_id):
        db = get_db()
        try:
            owner = db.execute('SELECT * FROM owners WHERE id=?', (owner_id,)).fetchone()
            if not owner:
                raise ServiceError('业主不存在')
            rooms = db.execute(
                'SELECT id, building, unit, room_number, floor, category, area '
                'FROM rooms WHERE owner_id=? ORDER BY building, unit, room_number',
                (owner_id,),
            ).fetchall()
            return {
                'id': owner['id'],
                'name': owner['name'],
                'phone': owner['phone'] or '',
                'id_card_masked': _mask_id_card(owner['id_card'] if 'id_card' in owner.keys() else ''),
                'rooms': [dict(r) for r in rooms],
            }
        finally:
            db.close()


class RoomService:
    def get_room(self, room_id):
        db = get_db()
        try:
            room = db.execute(
                'SELECT r.*, o.name AS owner_name, o.phone AS owner_phone '
                'FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id WHERE r.id=?',
                (room_id,),
            ).fetchone()
            if not room:
                raise ServiceError('房间不存在')
            result = dict(room)
            owner_id = result.get('owner_id')
            result['owner'] = None
            if owner_id:
                result['owner'] = {
                    'id': owner_id,
                    'name': result.pop('owner_name', '') or '',
                    'phone': result.pop('owner_phone', '') or '',
                }
            else:
                result.pop('owner_name', None)
                result.pop('owner_phone', None)
            return result
        finally:
            db.close()


class BillingService:
    def get_bill(self, bill_id):
        db = get_db()
        try:
            row = db.execute(
                'SELECT b.*, ft.name AS fee_type_name, r.building, r.unit, r.room_number, '
                'r.area, o.name AS owner_name, o.phone AS owner_phone '
                'FROM bills b '
                'LEFT JOIN fee_types ft ON b.fee_type_id=ft.id '
                'LEFT JOIN rooms r ON b.room_id=r.id '
                'LEFT JOIN owners o ON b.owner_id=o.id '
                'WHERE b.id=?',
                (bill_id,),
            ).fetchone()
            if not row:
                raise ServiceError('账单不存在')
            paid = db.execute(
                'SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE bill_id=?',
                (bill_id,),
            ).fetchone()[0]
            amount = _money(row['amount'])
            paid_amount = _money(paid)
            return {
                'id': row['id'],
                'bill_number': row['bill_number'],
                'period': row['billing_period'],
                'status': row['status'],
                'amount': str(amount),
                'paid_amount': str(paid_amount),
                'unpaid_amount': str(max(Decimal('0.00'), amount - paid_amount)),
                'due_date': row['due_date'],
                'fee_type': {'id': row['fee_type_id'], 'name': row['fee_type_name'] or ''},
                'room': {
                    'id': row['room_id'],
                    'building': row['building'] or '',
                    'unit': row['unit'] or '',
                    'room_number': row['room_number'] or '',
                    'area': row['area'] or 0,
                },
                'owner': {'id': row['owner_id'], 'name': row['owner_name'] or '', 'phone': row['owner_phone'] or ''},
            }
        finally:
            db.close()

    def preview_generation(self, request):
        period = request.get('period') or ''
        due_date = request.get('due_date') or ''
        fee_type_ids = [int(x) for x in (request.get('fee_type_ids') or [])]
        filters = {
            'building': (request.get('building') or '').strip(),
            'category': (request.get('category') or '').strip(),
            'room_from': (request.get('room_from') or '').strip(),
            'room_to': (request.get('room_to') or '').strip(),
        }
        db = get_db()
        try:
            sql = 'SELECT * FROM rooms'
            cond = []
            vals = []
            if filters['building']:
                cond.append('building=?'); vals.append(filters['building'])
            if filters['category']:
                cond.append('category=?'); vals.append(filters['category'])
            if filters['room_from']:
                cond.append('room_number>=?'); vals.append(filters['room_from'])
            if filters['room_to']:
                cond.append('room_number<=?'); vals.append(filters['room_to'])
            if cond:
                sql += ' WHERE ' + ' AND '.join(cond)
            sql += ' ORDER BY building, unit, room_number'
            rooms = [r for r in db.execute(sql, vals).fetchall() if room_active_in_period(r, period)]
            fees = {r['id']: r for r in db.execute('SELECT * FROM fee_types WHERE is_active=1').fetchall()}
            existing = {row[0] for row in db.execute(
                "SELECT DISTINCT room_id || ':' || fee_type_id FROM bills WHERE billing_period=?",
                (period,),
            ).fetchall()}
            items = []
            skipped = 0
            for room in rooms:
                for fee_type_id in fee_type_ids:
                    fee = fees.get(fee_type_id)
                    if not fee or not fee_applies_to_room(fee['name'] or '', room):
                        continue
                    key = f"{room['id']}:{fee_type_id}"
                    if key in existing:
                        skipped += 1
                        continue
                    calc = calculate_bill_amount(db, room, fee, period)
                    amount = _money(calc['amount'])
                    if amount <= Decimal('0.00'):
                        continue
                    items.append({
                        'room_id': room['id'],
                        'fee_type_id': fee_type_id,
                        'period': period,
                        'due_date': due_date,
                        'amount': str(amount),
                        'formula': calc['formula'],
                    })
            return {'period': period, 'due_date': due_date, 'items': items, 'total_count': len(items), 'skipped': skipped}
        finally:
            db.close()


class PaymentService:
    def preview_payment(self, request):
        bill_id = int(request.get('bill_id') or 0)
        amount = _money(request.get('amount') or 0)
        bill = BillingService().get_bill(bill_id)
        unpaid = Decimal(bill['unpaid_amount'])
        if amount <= Decimal('0.00'):
            raise ServiceError('收款金额必须大于0')
        if amount > unpaid:
            raise ServiceError('收款金额不能超过欠费金额')
        return {
            'bill_id': bill_id,
            'amount': str(amount),
            'unpaid_before': str(unpaid),
            'unpaid_after': str(unpaid - amount),
            'will_mark_paid': amount == unpaid,
        }

    def create_payment(self, request, actor=None):
        actor = actor or Actor()
        preview = self.preview_payment(request)
        bill_id = preview['bill_id']
        amount = Decimal(preview['amount'])
        method = request.get('method') or 'cash'
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO payments (bill_id, amount_paid, payment_date, payment_method, operator, notes, receipt_number) "
                "VALUES (?, ?, datetime('now','localtime'), ?, ?, ?, ?)",
                (bill_id, float(amount), method, actor.username, request.get('notes') or '', request.get('receipt_number') or None),
            )
            new_status = 'paid' if preview['will_mark_paid'] else 'partial'
            if new_status == 'paid':
                db.execute("UPDATE bills SET status=?, paid_at=datetime('now','localtime') WHERE id=?", (new_status, bill_id))
            else:
                db.execute('UPDATE bills SET status=?, paid_at=NULL WHERE id=?', (new_status, bill_id))
            db.commit()
            return {
                'payment_id': cur.lastrowid,
                'bill_id': bill_id,
                'amount': str(amount),
                'method': method,
                'bill_status': new_status,
            }
        finally:
            db.close()
