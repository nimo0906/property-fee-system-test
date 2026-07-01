#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Money rounding and formatting helpers.

Business amounts are kept to jiao (one decimal place). Unit prices, areas,
readings, and rates may keep their own precision; final payable amounts use
these helpers.
"""

from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANT = Decimal('0.1')
ZERO_MONEY = Decimal('0.0')


def money_decimal(value):
    return Decimal(str(value or 0)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def money_float(value):
    return float(money_decimal(value))


def money_str(value):
    return f"{money_decimal(value):.1f}"


def money_display(value, comma=False):
    amount = float(money_decimal(value))
    return f"{amount:,.1f}" if comma else f"{amount:.1f}"


def number_display(value, digits=2):
    return f"{float(value or 0):.{int(digits)}f}"

def unit_price_display(value, max_digits=6):
    """Display configurable rates without forcing final-money precision.

    Final receivable/payable amounts are rounded to jiao elsewhere. Unit prices
    are operator settings and may need two or more decimals, e.g. water 20.11.
    """
    try:
        dec = Decimal(str(value or 0))
    except Exception:
        dec = Decimal('0')
    quant = Decimal('1').scaleb(-int(max_digits))
    text = format(dec.quantize(quant, rounding=ROUND_HALF_UP), 'f')
    text = text.rstrip('0').rstrip('.')
    return text or '0'

