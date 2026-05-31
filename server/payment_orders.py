#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment order service for local mock online payment flow."""

from datetime import datetime
import secrets

from server.db import get_db
from server.owner_portal import OwnerPortalError, OwnerPortalService
from server.services import Actor, PaymentService, ServiceError


class PaymentOrderError(Exception):
    """Payment order business error safe for UI/API responses."""


def _now_compact():
    return datetime.now().strftime('%Y%m%d%H%M%S')


def _money(value):
    return f'{float(value or 0):.2f}'


class PaymentOrderService:
    def create_order(self, owner_session, request):
        bill_id = int(request.get('bill_id') or 0)
        amount = request.get('amount') or '0'
        channel = request.get('channel') or 'mock'
        if channel != 'mock':
            raise PaymentOrderError('当前仅支持模拟支付')
        try:
            OwnerPortalService().preview_payment(owner_session, {'bill_id': str(bill_id), 'amount': amount})
        except (OwnerPortalError, ServiceError) as exc:
            raise PaymentOrderError(str(exc))
        order_no = 'PO' + _now_compact() + secrets.token_hex(3).upper()
        db = get_db()
        try:
            db.execute(
                'INSERT INTO payment_orders(order_no, owner_id, bill_id, amount, channel, status, idempotency_key, updated_at) '
                "VALUES(?,?,?,?,?,'created',?,datetime('now','localtime'))",
                (order_no, owner_session['owner_id'], bill_id, float(amount), channel, request.get('idempotency_key') or ''),
            )
            db.commit()
            return {
                'order_no': order_no,
                'bill_id': bill_id,
                'amount': _money(amount),
                'channel': channel,
                'status': 'created',
            }
        finally:
            db.close()

    def get_order(self, owner_session, order_no):
        row = self._get_owned_order(owner_session, order_no)
        return self._format_order(row)

    def mark_mock_paid(self, owner_session, order_no):
        db = get_db()
        try:
            row = db.execute('SELECT * FROM payment_orders WHERE order_no=?', (order_no,)).fetchone()
            if not row or row['owner_id'] != owner_session['owner_id']:
                raise PaymentOrderError('订单不存在')
            if row['status'] == 'paid':
                raise PaymentOrderError('订单已支付')
            if row['status'] not in ('created', 'pending'):
                raise PaymentOrderError('订单状态不允许支付')
        finally:
            db.close()
        try:
            result = PaymentService().create_payment(
                {'bill_id': str(row['bill_id']), 'amount': _money(row['amount']), 'method': 'mock'},
                Actor(username='owner_portal', role='owner'),
            )
        except ServiceError as exc:
            raise PaymentOrderError(str(exc))
        db = get_db()
        try:
            db.execute(
                "UPDATE payment_orders SET status='paid', paid_at=datetime('now','localtime'), updated_at=datetime('now','localtime'), external_payment_id=? WHERE order_no=?",
                (f'mock-{result["payment_id"]}', order_no),
            )
            db.commit()
        finally:
            db.close()
        paid = self.get_order(owner_session, order_no)
        paid['payment_id'] = result['payment_id']
        return paid

    def _get_owned_order(self, owner_session, order_no):
        db = get_db()
        try:
            row = db.execute('SELECT * FROM payment_orders WHERE order_no=?', (order_no,)).fetchone()
            if not row or row['owner_id'] != owner_session['owner_id']:
                raise PaymentOrderError('订单不存在')
            return dict(row)
        finally:
            db.close()

    def _format_order(self, row):
        return {
            'order_no': row['order_no'],
            'bill_id': row['bill_id'],
            'amount': _money(row['amount']),
            'channel': row['channel'],
            'status': row['status'],
            'paid_at': row.get('paid_at') or '',
        }
