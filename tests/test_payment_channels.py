#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for online payment channel abstraction."""

import unittest


class TestPaymentChannels(unittest.TestCase):
    def test_get_payment_channel_returns_mock_channel(self):
        from server.payment_channels import get_payment_channel
        channel = get_payment_channel('mock')

        self.assertEqual(channel.name, 'mock')
        prepared = channel.prepare_order({
            'order_no': 'POTEST001',
            'amount': '88.00',
            'description': '测试账单',
        })
        self.assertEqual(prepared['channel'], 'mock')
        self.assertEqual(prepared['provider_status'], 'ready')
        self.assertIn('mock_pay_url', prepared)

    def test_unknown_payment_channel_is_rejected_before_real_integration(self):
        from server.payment_channels import PaymentChannelError, get_payment_channel

        with self.assertRaisesRegex(PaymentChannelError, '暂未启用该支付通道'):
            get_payment_channel('wechat')


if __name__ == '__main__':
    unittest.main()
