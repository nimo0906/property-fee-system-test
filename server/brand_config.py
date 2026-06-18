#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime branding configuration for generic commercial delivery."""

import os

PRODUCT_NAME = os.environ.get("PM_PRODUCT_NAME", "物业收费管理系统")
PRODUCT_SHORT_NAME = os.environ.get("PM_PRODUCT_SHORT_NAME", "物业收费")
PRODUCT_SUBTITLE = os.environ.get("PM_PRODUCT_SUBTITLE", "本地财务控制台")
PRODUCT_KICKER = os.environ.get("PM_PRODUCT_KICKER", "PROPERTY FINANCE")
RECEIPT_COMPANY_NAME = os.environ.get("PM_RECEIPT_COMPANY_NAME", "物业服务有限公司")
RECEIPT_SERIAL_PREFIX = os.environ.get("PM_RECEIPT_SERIAL_PREFIX", "PF")
