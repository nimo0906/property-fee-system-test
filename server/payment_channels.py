#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment channel boundary for future online payment integrations."""


class PaymentChannelError(Exception):
    """Payment channel configuration or capability error safe for UI/API responses."""


class MockPaymentChannel:
    name = 'mock'

    def prepare_order(self, order):
        order_no = str(order.get('order_no') or '')
        return {
            'channel': self.name,
            'provider_status': 'ready',
            'mock_pay_url': '',
            'provider_order_no': f'mock-{order_no}',
        }

    def verify_callback(self, payload, headers=None):
        headers = headers or {}
        signature = (
            headers.get('X-Mock-Signature')
            or headers.get('x-mock-signature')
            or payload.get('signature')
            or ''
        )
        if signature != 'mock-signature':
            raise PaymentChannelError('回调签名校验失败')
        return True


def get_payment_channel(name):
    channel = str(name or 'mock').strip().lower()
    if channel == 'mock':
        return MockPaymentChannel()
    raise PaymentChannelError('暂未启用该支付通道')
