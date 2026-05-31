#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner portal identity service for H5/small-program access."""

import hashlib
import secrets
from datetime import datetime, timedelta

from server.db import get_db


class OwnerPortalError(Exception):
    """Owner portal business error safe for JSON responses."""


def _now():
    return datetime.now()


def _fmt(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def _parse(value):
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')


def _hash_code(phone, code):
    return hashlib.sha256(f'{phone}:{code}'.encode('utf-8')).hexdigest()


class OwnerPortalService:
    def send_code(self, phone):
        phone = str(phone or '').strip()
        db = get_db()
        try:
            owners = db.execute('SELECT id, name FROM owners WHERE phone=?', (phone,)).fetchall()
            if len(owners) > 1:
                raise OwnerPortalError('手机号绑定多个业主，请联系物业后台处理')
            code = f'{secrets.randbelow(1000000):06d}'
            db.execute(
                'INSERT INTO owner_portal_login_codes(phone, code_hash, expires_at) VALUES(?,?,?)',
                (phone, _hash_code(phone, code), _fmt(_now() + timedelta(minutes=5))),
            )
            db.commit()
            return {'message': '验证码已发送', 'debug_code': code}
        finally:
            db.close()

    def login(self, phone, code):
        phone = str(phone or '').strip()
        code = str(code or '').strip()
        db = get_db()
        try:
            owner = self._single_owner(db, phone)
            row = db.execute(
                'SELECT * FROM owner_portal_login_codes WHERE phone=? AND used_at IS NULL '
                'ORDER BY id DESC LIMIT 1',
                (phone,),
            ).fetchone()
            if not row or row['attempt_count'] >= 5:
                raise OwnerPortalError('验证码无效')
            if _parse(row['expires_at']) < _now():
                raise OwnerPortalError('验证码已过期')
            if row['code_hash'] != _hash_code(phone, code):
                db.execute(
                    'UPDATE owner_portal_login_codes SET attempt_count=attempt_count+1 WHERE id=?',
                    (row['id'],),
                )
                db.commit()
                raise OwnerPortalError('验证码错误')
            token = secrets.token_urlsafe(32)
            expires_at = _fmt(_now() + timedelta(days=7))
            db.execute(
                "UPDATE owner_portal_login_codes SET used_at=datetime('now','localtime') WHERE id=?",
                (row['id'],),
            )
            db.execute(
                'INSERT INTO owner_portal_sessions(token, owner_id, phone, expires_at) VALUES(?,?,?,?)',
                (token, owner['id'], phone, expires_at),
            )
            db.commit()
            return {'token': token, 'owner_id': owner['id'], 'name': owner['name'], 'expires_at': expires_at}
        finally:
            db.close()

    def get_session(self, token):
        db = get_db()
        try:
            row = db.execute(
                'SELECT s.*, o.name AS owner_name FROM owner_portal_sessions s '
                'JOIN owners o ON s.owner_id=o.id WHERE s.token=? AND s.revoked_at IS NULL',
                (token,),
            ).fetchone()
            if not row or _parse(row['expires_at']) < _now():
                raise OwnerPortalError('登录已失效')
            return {
                'token': row['token'],
                'owner_id': row['owner_id'],
                'phone': row['phone'],
                'name': row['owner_name'],
                'expires_at': row['expires_at'],
            }
        finally:
            db.close()

    def profile(self, session):
        db = get_db()
        try:
            owner = db.execute('SELECT * FROM owners WHERE id=?', (session['owner_id'],)).fetchone()
            if not owner:
                raise OwnerPortalError('登录已失效')
            return {
                'id': owner['id'],
                'name': owner['name'],
                'phone': owner['phone'] or '',
                'id_card_masked': self._mask_id_card(owner['id_card'] if 'id_card' in owner.keys() else ''),
            }
        finally:
            db.close()

    def rooms(self, session):
        db = get_db()
        try:
            rows = db.execute(
                'SELECT id, building, unit, room_number, floor, category, area FROM rooms '
                'WHERE owner_id=? ORDER BY building, unit, room_number',
                (session['owner_id'],),
            ).fetchall()
            return {'items': [dict(r) for r in rows]}
        finally:
            db.close()

    def bills(self, session, filters=None):
        filters = filters or {}
        cond = ['b.owner_id=?']
        vals = [session['owner_id']]
        if filters.get('status'):
            cond.append('b.status=?'); vals.append(filters['status'])
        if filters.get('period'):
            cond.append('b.billing_period=?'); vals.append(filters['period'])
        db = get_db()
        try:
            rows = db.execute(
                'SELECT b.*, r.building, r.unit, r.room_number, ft.name AS fee_type_name, '
                'COALESCE((SELECT SUM(amount_paid) FROM payments p WHERE p.bill_id=b.id),0) AS paid_amount '
                'FROM bills b LEFT JOIN rooms r ON b.room_id=r.id LEFT JOIN fee_types ft ON b.fee_type_id=ft.id '
                'WHERE ' + ' AND '.join(cond) + ' ORDER BY b.billing_period DESC, b.id DESC',
                vals,
            ).fetchall()
            return {'items': [self._bill_summary(r) for r in rows]}
        finally:
            db.close()

    def payments(self, session):
        db = get_db()
        try:
            rows = db.execute(
                'SELECT p.*, b.bill_number, b.billing_period, r.room_number FROM payments p '
                'JOIN bills b ON p.bill_id=b.id LEFT JOIN rooms r ON b.room_id=r.id '
                'WHERE b.owner_id=? ORDER BY p.payment_date DESC, p.id DESC',
                (session['owner_id'],),
            ).fetchall()
            return {'items': [{
                'id': r['id'],
                'bill_id': r['bill_id'],
                'bill_number': r['bill_number'],
                'period': r['billing_period'],
                'room_number': r['room_number'] or '',
                'amount': f"{float(r['amount_paid'] or 0):.2f}",
                'method': r['payment_method'] or '',
                'payment_date': r['payment_date'] or '',
            } for r in rows]}
        finally:
            db.close()

    def preview_payment(self, session, request):
        bill_id = int(request.get('bill_id') or 0)
        self._ensure_bill_owner(session, bill_id)
        from server.services import PaymentService
        return PaymentService().preview_payment(request)

    def _ensure_bill_owner(self, session, bill_id):
        db = get_db()
        try:
            row = db.execute('SELECT owner_id FROM bills WHERE id=?', (bill_id,)).fetchone()
            if not row:
                raise OwnerPortalError('账单不存在')
            if row['owner_id'] != session['owner_id']:
                raise OwnerPortalError('无权限访问该账单')
        finally:
            db.close()

    def _bill_summary(self, row):
        amount = float(row['amount'] or 0)
        paid = float(row['paid_amount'] or 0)
        return {
            'id': row['id'],
            'bill_number': row['bill_number'],
            'period': row['billing_period'],
            'status': row['status'],
            'amount': f'{amount:.2f}',
            'paid_amount': f'{paid:.2f}',
            'unpaid_amount': f'{max(0, amount - paid):.2f}',
            'due_date': row['due_date'],
            'fee_type': row['fee_type_name'] or '',
            'room': {
                'id': row['room_id'],
                'building': row['building'] or '',
                'unit': row['unit'] or '',
                'room_number': row['room_number'] or '',
            },
        }

    def _mask_id_card(self, value):
        text = str(value or '').strip()
        if len(text) <= 8:
            return text
        return text[:6] + '*' * (len(text) - 10) + text[-4:]

    def _single_owner(self, db, phone):
        owners = db.execute('SELECT id, name FROM owners WHERE phone=?', (phone,)).fetchall()
        if not owners:
            raise OwnerPortalError('验证码无效')
        if len(owners) > 1:
            raise OwnerPortalError('手机号绑定多个业主，请联系物业后台处理')
        return owners[0]
