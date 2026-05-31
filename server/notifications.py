#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Notification event boundary for future SMS / WeChat / in-app delivery."""

import json

from server.db import get_db


class NotificationError(Exception):
    pass


class NotificationService:
    def enqueue(self, event_type, *, channel='in_app', target='', owner_id=None, bill_id=None, order_no=None, payload=None):
        db = get_db()
        try:
            payload_text = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
            cur = db.execute(
                'INSERT INTO notification_events(event_type, channel, target, owner_id, bill_id, order_no, payload, status) VALUES(?,?,?,?,?,?,?,\'pending\')',
                (event_type, channel, target, owner_id, bill_id, order_no, payload_text),
            )
            db.commit()
            return cur.lastrowid
        finally:
            db.close()

    def mark_sent(self, event_id):
        db = get_db()
        try:
            db.execute(
                "UPDATE notification_events SET status='sent', sent_at=datetime('now','localtime') WHERE id=?",
                (event_id,),
            )
            db.commit()
        finally:
            db.close()

    def list_events(self, *, owner_id=None, bill_id=None):
        db = get_db()
        try:
            sql = 'SELECT * FROM notification_events WHERE 1=1'
            params = []
            if owner_id is not None:
                sql += ' AND owner_id=?'
                params.append(owner_id)
            if bill_id is not None:
                sql += ' AND bill_id=?'
                params.append(bill_id)
            sql += ' ORDER BY id DESC'
            rows = db.execute(sql, params).fetchall()
            return {'items': [dict(r) for r in rows]}
        finally:
            db.close()
