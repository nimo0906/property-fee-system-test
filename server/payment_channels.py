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
            'mock_pay_url': f'/owner-portal/payment-orders/{order_no}',
            'provider_order_no': f'mock-{order_no}',
        }


def get_payment_channel(name):
    channel = str(name or 'mock').strip().lower()
    if channel == 'mock':
        return MockPaymentChannel()
    raise PaymentChannelError('暂未启用该支付通道')
