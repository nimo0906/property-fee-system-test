#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable internal service interfaces for v2.0 expansion."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from server.db import get_db


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
