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

    def _single_owner(self, db, phone):
        owners = db.execute('SELECT id, name FROM owners WHERE phone=?', (phone,)).fetchall()
        if not owners:
            raise OwnerPortalError('验证码无效')
        if len(owners) > 1:
            raise OwnerPortalError('手机号绑定多个业主，请联系物业后台处理')
        return owners[0]
