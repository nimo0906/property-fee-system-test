#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Electronic invoice request boundary for future provider integrations."""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import secrets

from server.db import get_db


class InvoiceRequestError(Exception):
    """Invoice request business error safe for UI/API responses."""


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _request_no():
    return 'IR' + datetime.now().strftime('%Y%m%d%H%M%S') + secrets.token_hex(3).upper()


class InvoiceRequestService:
    def create_request(self, request):
        bill_id = int(request.get('bill_id') or 0)
        idempotency_key = str(request.get('idempotency_key') or '').strip()
        db = get_db()
        try:
            existing = None
            if idempotency_key:
                existing = db.execute(
                    'SELECT * FROM invoice_requests WHERE idempotency_key=?',
                    (idempotency_key,),
                ).fetchone()
            if not existing:
                existing = db.execute('SELECT * FROM invoice_requests WHERE bill_id=?', (bill_id,)).fetchone()
            if existing:
                return self._format(existing)
            bill = db.execute('SELECT * FROM bills WHERE id=?', (bill_id,)).fetchone()
            if not bill:
                raise InvoiceRequestError('账单不存在')
            if bill['status'] != 'paid':
                raise InvoiceRequestError('仅已缴清账单可申请电子票据')
            amount = _money(bill['amount'])
            cur = db.execute(
                'INSERT INTO invoice_requests(request_no,bill_id,owner_id,amount,buyer_name,buyer_tax_id,idempotency_key,status,provider,updated_at) '
                "VALUES(?,?,?,?,?,?,?,'pending','manual',datetime('now','localtime'))",
                (
                    _request_no(), bill_id, bill['owner_id'], float(amount),
                    request.get('buyer_name') or '', request.get('buyer_tax_id') or '', idempotency_key or None,
                ),
            )
            db.commit()
            row = db.execute('SELECT * FROM invoice_requests WHERE id=?', (cur.lastrowid,)).fetchone()
            return self._format(row)
        finally:
            db.close()


    def create_owner_request(self, owner_session, request):
        bill_id = int(request.get('bill_id') or 0)
        db = get_db()
        try:
            row = db.execute('SELECT owner_id FROM bills WHERE id=?', (bill_id,)).fetchone()
            if not row or row['owner_id'] != owner_session['owner_id']:
                raise InvoiceRequestError('账单不存在')
        finally:
            db.close()
        return self.create_request(request)

    def list_requests(self, filters=None):
        filters = filters or {}
        db = get_db()
        try:
            sql = 'SELECT * FROM invoice_requests WHERE 1=1'
            params = []
            if filters.get('owner_id'):
                sql += ' AND owner_id=?'
                params.append(int(filters['owner_id']))
            if filters.get('status'):
                sql += ' AND status=?'
                params.append(filters['status'])
            sql += ' ORDER BY id DESC'
            rows = db.execute(sql, params).fetchall()
            return {'items': [self._format(r) for r in rows]}
        finally:
            db.close()

    def get_request(self, request_no):
        db = get_db()
        try:
            row = db.execute('SELECT * FROM invoice_requests WHERE request_no=?', (request_no,)).fetchone()
            if not row:
                raise InvoiceRequestError('电子票据请求不存在')
            return self._format(row)
        finally:
            db.close()

    def _format(self, row):
        data = dict(row)
        return {
            'request_no': data['request_no'],
            'bill_id': data['bill_id'],
            'owner_id': data['owner_id'],
            'amount': str(_money(data['amount'])),
            'buyer_name': data.get('buyer_name') or '',
            'buyer_tax_id': data.get('buyer_tax_id') or '',
            'status': data['status'],
            'provider': data.get('provider') or 'manual',
            'external_invoice_id': data.get('external_invoice_id') or '',
            'failure_reason': data.get('failure_reason') or '',
            'created_at': data.get('created_at') or '',
        }
