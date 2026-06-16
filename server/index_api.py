#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Home page lightweight JSON APIs."""

from server.base import BaseHandler
from server.db import get_db, qs


class IndexApiMixin(BaseHandler):
    def _api_stats(self):
        db = get_db()
        tr = db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        to = db.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
        tb = db.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
        tu = db.execute("SELECT COUNT(*) FROM bills WHERE status IN('unpaid','overdue')").fetchone()[0]
        tp = db.execute("SELECT COUNT(*) FROM bills WHERE status='paid'").fetchone()[0]
        db.close()
        self._json({'total_rooms': tr, 'total_owners': to, 'total_bills': tb, 'unpaid_bills': tu, 'paid_bills': tp})

    def _api_search_rooms(self, q):
        kw = qs(q, 'q', '')
        db = get_db()
        if kw:
            rows = db.execute(
                "SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id "
                "WHERE r.building LIKE ? OR r.room_number LIKE ? OR o.name LIKE ? "
                "ORDER BY r.building,r.room_number LIMIT 50",
                (f'%{kw}%', f'%{kw}%', f'%{kw}%')
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT r.*,o.name oname FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id "
                "ORDER BY r.building,r.room_number LIMIT 50"
            ).fetchall()
        db.close()
        self._json([{'id': r['id'], 'building': r['building'], 'unit': r['unit'],
                      'room_number': r['room_number'], 'floor': r['floor'], 'category': r['category'],
                      'area': r['area'], 'owner_id': r['owner_id'], 'oname': r['oname'] or ''} for r in rows])

    def _api_search_owners(self, q):
        kw = qs(q, 'q', '')
        db = get_db()
        if kw:
            rows = db.execute("SELECT * FROM owners WHERE name LIKE ? OR phone LIKE ? ORDER BY name LIMIT 50",
                              (f'%{kw}%', f'%{kw}%')).fetchall()
        else:
            rows = db.execute("SELECT * FROM owners ORDER BY name LIMIT 50").fetchall()
        db.close()
        self._json([{'id': r['id'], 'name': r['name'], 'phone': r['phone'] or ''} for r in rows])
