#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Basic-info analysis for imported payment ledgers."""

import re

from server.money import money_float


FEE_RULES = {
    '物业费': ('matched_fee', '可识别为系统收费项目，金额需用户确认'),
    '垃圾费': ('matched_fee', '可识别为垃圾类收费，需确认住宅/商业口径'),
    '暖气费': ('unmatched_fee', '系统暂无暖气费费用类型'),
    '其它费用': ('amount_confirm', '金额含正负数，只做金额提示，不自动入账'),
    '物业保证金': ('deposit_hint', '可识别为押金类信息，金额需用户确认'),
    '电费': ('matched_fee', '可识别为电费类收费，金额需用户确认'),
    '水费': ('matched_fee', '可识别为水费类收费，金额需用户确认'),
    '装修押金': ('deposit_hint', '可识别为押金类信息，金额需用户确认'),
    '厨余垃圾清运票': ('matched_fee', '可识别为垃圾清运相关收费，需确认口径'),
    '广告费': ('unmatched_fee', '系统暂无广告费费用类型'),
    '广告电费': ('matched_fee', '可识别为电费相关收费，需确认口径'),
    '装修管理费': ('matched_fee', '可识别为系统收费项目，金额需用户确认'),
    '装修工人出入证': ('unmatched_fee', '系统暂无出入证费用类型'),
    '装修许可证': ('unmatched_fee', '系统暂无许可证费用类型'),
    '水表押金': ('deposit_hint', '可识别为押金类信息，金额需用户确认'),
    '电表押金': ('deposit_hint', '可识别为押金类信息，金额需用户确认'),
    '水卡押金': ('deposit_hint', '可识别为押金类信息，金额需用户确认'),
    '电卡押金': ('deposit_hint', '可识别为押金类信息，金额需用户确认'),
}

LEDGER_COLUMNS = [
    '物业费', '垃圾费', '暖气费', '其它费用', '物业保证金', '电费', '水费',
    '装修押金', '厨余垃圾清运票', '广告费', '广告电费', '装修管理费',
    '装修工人出入证', '装修许可证', '水表押金', '电表押金', '水卡押金', '电卡押金',
]


def analyze_payment_ledger(headers, data_rows, rooms):
    header_index = {str(h).strip(): i for i, h in enumerate(headers)}
    room_index = _build_room_index(rooms)
    room_col = header_index.get('房间号')
    owner_col = header_index.get('用户名称')
    company_col = header_index.get('工作单位')
    type_col = header_index.get('房间类型')
    paid_col = header_index.get('本期收款(合计)')
    amount_col = header_index.get('本期金额')
    matched_rooms = 0
    unmatched_rooms = 0
    rows_with_owner = 0
    rows_with_company = 0
    room_types = {}
    rows_with_payment = 0
    payment_total = 0.0
    amount_total = 0.0
    examples = []

    for row in data_rows:
        room_raw = _cell(row, room_col)
        if _cell(row, owner_col):
            rows_with_owner += 1
        if _cell(row, company_col):
            rows_with_company += 1
        room_type = _cell(row, type_col)
        if room_type:
            room_types[room_type] = room_types.get(room_type, 0) + 1
        if room_raw:
            if match_room_ref(room_raw, room_index):
                matched_rooms += 1
            else:
                unmatched_rooms += 1
                if len(examples) < 8:
                    examples.append(room_raw)
        paid = _number(_cell(row, paid_col))
        amount = _number(_cell(row, amount_col))
        if paid:
            rows_with_payment += 1
            payment_total += paid
        amount_total += amount

    fee_stats = []
    for name in LEDGER_COLUMNS:
        idx = header_index.get(name)
        if idx is None:
            continue
        pos = neg = zero = blank = 0
        total = 0.0
        for row in data_rows:
            raw = _cell(row, idx)
            if raw == '':
                blank += 1
                continue
            value = _number(raw)
            total += value
            if value > 0:
                pos += 1
            elif value < 0:
                neg += 1
            else:
                zero += 1
        if pos or neg:
            action, note = FEE_RULES.get(name, ('amount_confirm', '金额需用户确认'))
            fee_stats.append({
                'name': name,
                'action': action,
                'note': note,
                'positive': pos,
                'negative': neg,
                'zero': zero,
                'blank': blank,
                'total': money_float(total),
            })

    return {
        'total_rows': len(data_rows),
        'rows_with_payment': rows_with_payment,
        'payment_total': money_float(payment_total),
        'amount_total': money_float(amount_total),
        'matched_rooms': matched_rooms,
        'unmatched_rooms': unmatched_rooms,
        'unmatched_examples': examples,
        'rows_with_owner': rows_with_owner,
        'rows_with_company': rows_with_company,
        'room_types': sorted(room_types.items(), key=lambda x: x[1], reverse=True)[:8],
        'fee_stats': fee_stats,
    }


def analyze_basic_info(headers, data_rows):
    header_index = {str(h).strip(): i for i, h in enumerate(headers)}
    fields = {
        'room_number': ['房号', '房间号', '房间'],
        'owner_name': ['业主姓名', '用户名称', '业主'],
        'owner_phone': ['联系电话', '电话', '手机'],
        'tenant_name': ['租户姓名', '租户'],
        'shop_name': ['店铺名称', '店铺'],
        'business_type': ['业态'],
        'area': ['面积㎡', '面积', '建筑面积'],
        'contract_period': ['合同缴租期', '合同日期', '合同期限', '租赁时间'],
        'rent_period': ['催缴租金租期', '租金租期'],
    }
    counts = {}
    examples = {}
    for key, names in fields.items():
        idx = next((header_index[n] for n in names if n in header_index), None)
        count = 0
        sample = []
        if idx is not None:
            for row in data_rows:
                value = _cell(row, idx)
                if value:
                    count += 1
                    if len(sample) < 5:
                        sample.append(value)
        counts[key] = count
        examples[key] = sample
    return {'total_rows': len(data_rows), 'field_counts': counts, 'examples': examples}


def match_room_ref(room_ref, room_index):
    keys = room_ref_keys(room_ref)
    for key in keys:
        if key in room_index:
            return room_index[key]
    return None


def room_ref_keys(room_ref):
    text = str(room_ref or '').strip().upper()
    text = text.replace('商用-', '').replace('住宅-', '').replace('写字楼-', '').replace('民用-', '')
    text = text.replace('商用', '').replace('住宅', '').replace('民用', '')
    text = text.replace(' ', '').replace('房', '').replace('室', '')
    text = re.sub(r'B座B(?=\d)', 'B座', text)
    range_match = re.search(r'([A-Z]?座?B?)(\d{3,5})-(\d{3,5})', text)
    keys = set()
    if range_match:
        prefix, start, end = range_match.groups()
        for number in _expand_room_range(start, end):
            keys.add(_normalize_room_token(number))
            keys.add(_normalize_room_token(prefix + number))
    parts = re.split(r'[-、,，/]+', text)
    for part in parts:
        if not part:
            continue
        keys.add(_normalize_room_token(part))
        match = re.search(r'([A-Z]?座?)(B?\d{2,5})', part)
        if match:
            token = match.group(2)
            keys.add(_normalize_room_token(token))
            keys.add(_normalize_room_token(token.lstrip('B')))
    return {k for k in keys if k}


def _expand_room_range(start, end):
    try:
        a = int(start)
        b = int(end)
    except ValueError:
        return [start, end]
    if len(start) != len(end) or b < a or b - a > 20:
        return [start, end]
    return [str(n).zfill(len(start)) for n in range(a, b + 1)]


def _build_room_index(rooms):
    index = {}
    for room in rooms:
        building = str(room.get('building') or '')
        room_number = str(room.get('room_number') or '')
        tokens = {
            _normalize_room_token(room_number),
            _normalize_room_token(building + room_number),
            _normalize_room_token(building + '-' + room_number),
        }
        for token in tokens:
            if token:
                index[token] = room
    return index


def _normalize_room_token(value):
    text = str(value or '').upper()
    text = text.replace('座', '').replace('栋', '').replace('-', '')
    text = re.sub(r'[^A-Z0-9一二三四五六七八九十百千万]+', '', text)
    return text


def _cell(row, idx):
    if idx is None or idx >= len(row):
        return ''
    return str(row[idx] or '').strip()


def _number(value):
    if value in ('', None):
        return 0.0
    try:
        return float(str(value).replace(',', ''))
    except ValueError:
        return 0.0
