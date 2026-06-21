#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chinese RMB uppercase amount formatting."""

from decimal import Decimal, ROUND_HALF_UP

DIGITS = '零壹贰叁肆伍陆柒捌玖'
UNITS = ['', '拾', '佰', '仟']
GROUP_UNITS = ['', '万', '亿']


def rmb_uppercase(value):
    amount = Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    integer = int(amount)
    cents = int((amount - integer) * 100)
    prefix = '人民币'
    if integer == 0:
        integer_text = '零元'
    else:
        integer_text = _integer_upper(integer) + '元'
    if cents == 0:
        return prefix + integer_text + '整'
    jiao, fen = divmod(cents, 10)
    decimal_text = ''
    if jiao:
        decimal_text += DIGITS[jiao] + '角'
    elif integer and fen:
        decimal_text += '零'
    if fen:
        decimal_text += DIGITS[fen] + '分'
    return prefix + integer_text + decimal_text


def _integer_upper(number):
    groups = []
    while number:
        groups.append(number % 10000)
        number //= 10000
    parts = []
    need_zero = False
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if group == 0:
            need_zero = bool(parts)
            continue
        if need_zero or (parts and group < 1000):
            parts.append('零')
        parts.append(_group_upper(group) + GROUP_UNITS[index])
        need_zero = False
    return ''.join(parts).rstrip('零')


def _group_upper(group):
    chars = []
    zero = False
    for pos in range(3, -1, -1):
        unit_value = 10 ** pos
        digit = group // unit_value
        group %= unit_value
        if digit:
            if zero:
                chars.append('零')
                zero = False
            chars.append(DIGITS[digit] + UNITS[pos])
        elif chars:
            zero = True
    return ''.join(chars).rstrip('零')
