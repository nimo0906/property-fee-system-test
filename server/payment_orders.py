#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment order service for backend payment callback reconciliation."""

from server.db import get_db
from server.payment_channels import PaymentChannelError, get_payment_channel
from server.notifications import NotificationService
from server.services import Actor, PaymentService, ServiceError


class PaymentOrderError(Exception):
    """Payment order business error safe for UI/API responses."""


def _money(value):
    return f'{float(value or 0):.2f}'


class PaymentOrderService:
    def process_callback(self, request):
        channel = request.get('channel') or 'mock'
        external_event_id = request.get('external_event_id') or ''
        order_no = request.get('order_no') or ''
        if not external_event_id:
            raise PaymentOrderError('回调事件ID不能为空')
        try:
            payment_channel = get_payment_channel(channel)
            payment_channel.verify_callback(request, request.get('headers') or {})
        except PaymentChannelError as exc:
            raise PaymentOrderError(str(exc))
        db = get_db()
        try:
            existing = db.execute(
                'SELECT status FROM payment_callbacks WHERE channel=? AND external_event_id=?',
                (channel, external_event_id),
            ).fetchone()
            if existing:
                return {'status': existing['status'], 'duplicate': True, 'order_no': order_no}
            row = db.execute('SELECT * FROM payment_orders WHERE order_no=?', (order_no,)).fetchone()
            if not row:
                raise PaymentOrderError('订单不存在')
            if row['channel'] != channel:
                raise PaymentOrderError('回调通道与订单不一致')
            db.execute(
                'INSERT INTO payment_callbacks(channel, external_event_id, order_no, status, raw_summary) '
                "VALUES(?,?,?,'received',?)",
                (channel, external_event_id, order_no, request.get('raw_summary') or ''),
            )
            db.commit()
        finally:
            db.close()
        payment_id = None
        if row['status'] != 'paid':
            try:
                result = PaymentService().create_payment(
                    {'bill_id': str(row['bill_id']), 'amount': _money(row['amount']), 'method': channel},
                    Actor(username='payment_callback', role='system'),
                )
                payment_id = result['payment_id']
            except ServiceError as exc:
                self._finish_callback(channel, external_event_id, 'failed', str(exc))
                raise PaymentOrderError(str(exc))
            db = get_db()
            try:
                db.execute(
                    "UPDATE payment_orders SET status='paid', paid_at=datetime('now','localtime'), "
                    "updated_at=datetime('now','localtime'), external_payment_id=? WHERE order_no=?",
                    (f'{channel}-{payment_id}', order_no),
                )
                db.commit()
            finally:
                db.close()
        if payment_id:
            NotificationService().enqueue('payment_success', channel='in_app', target=str(self._get_owner_phone(row['owner_id'])), owner_id=row['owner_id'], bill_id=row['bill_id'], order_no=order_no, payload={'channel': channel, 'order_no': order_no, 'payment_id': payment_id, 'amount': _money(row['amount'])})
        self._finish_callback(channel, external_event_id, 'processed', '')
        return {'status': 'processed', 'duplicate': row['status'] == 'paid', 'order_no': order_no, 'payment_id': payment_id}


    def reconcile_order(self, order_no):
        db = get_db()
        try:
            row = db.execute('SELECT * FROM payment_orders WHERE order_no=?', (order_no,)).fetchone()
            if not row:
                raise PaymentOrderError('订单不存在')
            payments = db.execute(
                "SELECT COUNT(*) count, COALESCE(SUM(amount_paid),0) total FROM payments WHERE bill_id=? AND payment_method=? AND operator='payment_callback'",
                (row['bill_id'], row['channel']),
            ).fetchone()
            callbacks = db.execute('SELECT COUNT(*) count FROM payment_callbacks WHERE order_no=?', (order_no,)).fetchone()
            expected = float(row['amount'] or 0)
            paid = float(payments['total'] or 0)
            payment_count = int(payments['count'] or 0)
            callback_count = int(callbacks['count'] or 0)
            amount_match = abs(paid - expected) <= 0.005
            if row['status'] == 'paid' and amount_match and payment_count >= 1:
                reconcile_status = 'matched'
            elif row['status'] == 'paid' and paid + 0.005 < expected:
                reconcile_status = 'underpaid'
            elif paid - expected > 0.005:
                reconcile_status = 'overpaid'
            else:
                reconcile_status = 'pending'
            return {
                'order_no': row['order_no'],
                'bill_id': row['bill_id'],
                'channel': row['channel'],
                'order_status': row['status'],
                'expected_amount': _money(expected),
                'paid_amount': _money(paid),
                'payment_count': payment_count,
                'callback_count': callback_count,
                'amount_match': amount_match,
                'reconcile_status': reconcile_status,
            }
        finally:
            db.close()

    def _finish_callback(self, channel, external_event_id, status, error_message):
        db = get_db()
        try:
            db.execute(
                "UPDATE payment_callbacks SET status=?, processed_at=datetime('now','localtime'), error_message=? "
                'WHERE channel=? AND external_event_id=?',
                (status, error_message, channel, external_event_id),
            )
            db.commit()
        finally:
            db.close()

    def _get_owner_phone(self, owner_id):
        db = get_db()
        try:
            row = db.execute('SELECT phone FROM owners WHERE id=?', (owner_id,)).fetchone()
            return row['phone'] if row else ''
        finally:
            db.close()

    def _format_order(self, row):
        data = dict(row)
        return {
            'order_no': data['order_no'],
            'bill_id': data['bill_id'],
            'amount': _money(data['amount']),
            'channel': data['channel'],
            'status': data['status'],
            'paid_at': data.get('paid_at') or '',
            'created_at': data.get('created_at') or '',
            'bill_number': data.get('bill_number') or '',
            'period': data.get('billing_period') or '',
            'room_number': data.get('room_number') or '',
        }
