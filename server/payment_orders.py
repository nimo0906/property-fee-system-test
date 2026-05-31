#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment order service for local mock online payment flow."""

from datetime import datetime
import secrets

from server.db import get_db
from server.owner_portal import OwnerPortalError, OwnerPortalService
from server.payment_channels import PaymentChannelError, get_payment_channel
from server.services import Actor, PaymentService, ServiceError


class PaymentOrderError(Exception):
    """Payment order business error safe for UI/API responses."""


def _now_compact():
    return datetime.now().strftime('%Y%m%d%H%M%S')


def _money(value):
    return f'{float(value or 0):.2f}'


class PaymentOrderService:
    def list_orders(self, owner_session):
        db = get_db()
        try:
            rows = db.execute(
                'SELECT po.*, b.bill_number, b.billing_period, r.room_number '
                'FROM payment_orders po '
                'JOIN bills b ON po.bill_id=b.id '
                'LEFT JOIN rooms r ON b.room_id=r.id '
                'WHERE po.owner_id=? ORDER BY po.id DESC',
                (owner_session['owner_id'],),
            ).fetchall()
            return {'items': [self._format_order(r) for r in rows]}
        finally:
            db.close()

    def create_order(self, owner_session, request):
        bill_id = int(request.get('bill_id') or 0)
        amount = request.get('amount') or '0'
        channel = request.get('channel') or 'mock'
        try:
            payment_channel = get_payment_channel(channel)
        except PaymentChannelError as exc:
            raise PaymentOrderError(str(exc))
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
            result = {
                'order_no': order_no,
                'bill_id': bill_id,
                'amount': _money(amount),
                'channel': channel,
                'status': 'created',
            }
            result['channel_payload'] = payment_channel.prepare_order(result)
            return result
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

    def process_callback(self, request):
        channel = request.get('channel') or 'mock'
        external_event_id = request.get('external_event_id') or ''
        order_no = request.get('order_no') or ''
        if not external_event_id:
            raise PaymentOrderError('回调事件ID不能为空')
        try:
            get_payment_channel(channel)
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
        self._finish_callback(channel, external_event_id, 'processed', '')
        return {'status': 'processed', 'duplicate': row['status'] == 'paid', 'order_no': order_no, 'payment_id': payment_id}

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

    def _get_owned_order(self, owner_session, order_no):
        db = get_db()
        try:
            row = db.execute(
                'SELECT po.*, b.bill_number, b.billing_period, r.room_number '
                'FROM payment_orders po '
                'JOIN bills b ON po.bill_id=b.id '
                'LEFT JOIN rooms r ON b.room_id=r.id '
                'WHERE po.order_no=?',
                (order_no,),
            ).fetchone()
            if not row or row['owner_id'] != owner_session['owner_id']:
                raise PaymentOrderError('订单不存在')
            return dict(row)
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
