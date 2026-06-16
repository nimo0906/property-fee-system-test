# -*- coding: utf-8 -*-
"""Compact report fee-type summary for the reports page."""

MAIN_FEE_KEYWORDS = (
    '物业费', '水费', '电费', '电梯费', '二次供水', '公摊',
    '生活垃圾', '垃圾清运', '租金', '商业物业费',
)


def _as_summary_row(row):
    return {
        'name': row['name'] or '未命名收费',
        'cnt': int(row['cnt'] or 0),
        'tot': float(row['tot'] or 0),
        'paid': float(row['paid'] or 0),
    }


def _has_amount(row):
    return bool(row['cnt'] or row['tot'] or row['paid'])


def _is_main_fee(name):
    text = str(name or '')
    return any(keyword in text for keyword in MAIN_FEE_KEYWORDS)


def compact_fee_summary_rows(rows):
    shown = []
    other = {'name': '其他收费', 'cnt': 0, 'tot': 0.0, 'paid': 0.0}
    for raw in rows:
        row = _as_summary_row(raw)
        if not _has_amount(row):
            continue
        if _is_main_fee(row['name']):
            shown.append(row)
        else:
            other['cnt'] += row['cnt']
            other['tot'] += row['tot']
            other['paid'] += row['paid']
    if _has_amount(other):
        shown.append(other)
    return shown
