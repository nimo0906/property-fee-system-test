#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import basic room/owner information from spreadsheets."""

import re

from server.import_parser import clean_room_number, infer_building, infer_floor, normalize_date, split_contract_period


INVALID_ROOM_NAMES = {'业态', '东大的信息', '业主的信息', '东大空置', '业主空铺', '房号-业态'}


def import_basic_info(db, headers, data_rows, col_map):
    return _process_basic_info(db, headers, data_rows, col_map, dry_run=False)


def preview_basic_info_import(db, headers, data_rows, col_map):
    return _process_basic_info(db, headers, data_rows, col_map, dry_run=True)


def _process_basic_info(db, headers, data_rows, col_map, dry_run=False):
    imported_rooms = 0
    updated_rooms = 0
    imported_owners = 0
    skipped = 0
    errors = []
    invalid_contracts = []
    skip_examples = []
    changed_rooms = []
    problem_rows = []

    def gc(row, key, default=''):
        idx = col_map.get(key)
        if idx is not None and idx < len(row):
            return str(row[idx] or '').strip()
        return default

    for row_no, row in enumerate(data_rows, start=1):
        try:
            raw_room = gc(row, 'room_number')
            if not raw_room:
                skipped += 1
                if len(skip_examples) < 8:
                    skip_examples.append(f'第{row_no}行缺少房号')
                problem_rows.append(_problem_row(row_no, '缺少房号', row))
                continue
            building = gc(row, 'building') or infer_building(raw_room)
            unit = gc(row, 'unit', 'A座') or 'A座'
            room_number = clean_room_number(raw_room)
            if not room_number or room_number in INVALID_ROOM_NAMES:
                skipped += 1
                if len(skip_examples) < 8:
                    skip_examples.append(f'第{row_no}行房号无效: {raw_room}')
                problem_rows.append(_problem_row(row_no, f'房号无效: {raw_room}', row))
                continue
            floor = _to_int(gc(row, 'floor'), infer_floor(room_number))
            area = _to_float(gc(row, 'area'), 0)
            if not _looks_like_room_record(room_number, area):
                skipped += 1
                if len(skip_examples) < 8:
                    skip_examples.append(f'第{row_no}行非房间资料: {raw_room}')
                problem_rows.append(_problem_row(row_no, f'非房间资料: {raw_room}', row))
                continue
            category = _normalize_category(gc(row, 'category', '商户'))
            owner_name = gc(row, 'owner_name') or gc(row, 'tenant_name')
            owner_phone = gc(row, 'owner_phone')
            contract_start = normalize_date(gc(row, 'contract_start'))
            contract_end = normalize_date(gc(row, 'contract_end'))
            contract_period = gc(row, 'contract_period')
            if (not contract_start or not contract_end) and contract_period:
                period_start, period_end = split_contract_period(contract_period)
                contract_start = contract_start or period_start
                contract_end = contract_end or period_end
            invalid_contract_values = []
            if gc(row, 'contract_start') and not contract_start:
                invalid_contract_values.append(gc(row, 'contract_start'))
            if gc(row, 'contract_end') and not contract_end:
                invalid_contract_values.append(gc(row, 'contract_end'))
            if contract_period and not (contract_start and contract_end):
                invalid_contract_values.append(contract_period)
            if invalid_contract_values and len(invalid_contracts) < 8:
                raw_contract = ' / '.join(invalid_contract_values)
                invalid_contracts.append(f'第{row_no}行: {raw_contract}')
                problem_rows.append(_problem_row(row_no, f'合同日期异常: {raw_contract}', row))
            business_type = gc(row, 'business_type')
            notes = _build_notes(
                tenant=gc(row, 'tenant_name'),
                shop=gc(row, 'shop_name'),
                rent_period=gc(row, 'rent_period'),
            )

            owner_id = None
            if owner_name:
                owner = db.execute("SELECT id, phone FROM owners WHERE name=? LIMIT 1", (owner_name,)).fetchone()
                if owner:
                    owner_id = owner['id']
                    if owner_phone and not owner['phone'] and not dry_run:
                        db.execute("UPDATE owners SET phone=? WHERE id=?", (owner_phone, owner_id))
                else:
                    if dry_run:
                        owner_id = None
                    else:
                        cur = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", (owner_name, owner_phone))
                        owner_id = cur.lastrowid
                    imported_owners += 1

            room = db.execute(
                "SELECT * FROM rooms WHERE building=? AND room_number=? LIMIT 1",
                (building, room_number)
            ).fetchone()
            if room:
                if not dry_run:
                    db.execute(
                        "UPDATE rooms SET unit=?, floor=?, category=?, area=?, owner_id=COALESCE(?, owner_id), "
                        "contract_start=COALESCE(NULLIF(?, ''), contract_start), "
                        "contract_end=COALESCE(NULLIF(?, ''), contract_end), business_type=COALESCE(NULLIF(?, ''), business_type), notes=? WHERE id=?",
                        (unit, floor, category, area or room['area'], owner_id, contract_start, contract_end,
                         business_type, _merge_notes(room['notes'], notes), room['id'])
                    )
                updated_rooms += 1
                changed_rooms.append(_changed_room(
                    '更新', room['id'], building, unit, room_number, floor, category,
                    area or room['area'], owner_name, owner_phone, contract_start, contract_end, business_type, notes,
                ))
            else:
                room_id = None
                if not dry_run:
                    cur = db.execute(
                        "INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,contract_start,contract_end,business_type,notes) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (building, unit, room_number, floor, category, area, owner_id, contract_start, contract_end, business_type, notes)
                    )
                    room_id = cur.lastrowid
                imported_rooms += 1
                changed_rooms.append(_changed_room(
                    '新增', room_id, building, unit, room_number, floor, category,
                    area, owner_name, owner_phone, contract_start, contract_end, business_type, notes,
                ))
        except Exception as exc:
            errors.append(f'第{row_no}行: {exc}')
            problem_rows.append(_problem_row(row_no, f'处理错误: {exc}', row))
    return {
        'imported_rooms': imported_rooms,
        'updated_rooms': updated_rooms,
        'imported_owners': imported_owners,
        'skipped': skipped,
        'errors': errors,
        'invalid_contracts': invalid_contracts,
        'skip_examples': skip_examples,
        'changed_rooms': changed_rooms,
        'problem_rows': problem_rows,
    }


def _changed_room(action, room_id, building, unit, room_number, floor, category, area,
                  owner_name, owner_phone, contract_start, contract_end, business_type, notes):
    return {
        'action': action,
        'room_id': room_id,
        'building': building,
        'unit': unit,
        'room_number': room_number,
        'floor': floor,
        'category': category,
        'area': area,
        'owner_name': owner_name,
        'owner_phone': owner_phone,
        'contract_start': contract_start,
        'contract_end': contract_end,
        'business_type': business_type,
        'notes': notes,
    }


def _problem_row(row_no, reason, row):
    return {
        'row_no': row_no,
        'reason': reason,
        'raw': ' | '.join(str(x or '') for x in row),
    }


def _normalize_category(value):
    text = str(value or '').strip()
    if text in ('居民', '住宅'):
        return '居民'
    if text in ('商户', '商业'):
        return text
    if text in ('非居民', '特行'):
        return '商户'
    return '商户'


def _looks_like_room_record(room_number, area):
    text = str(room_number or '').strip()
    if area and area > 0:
        return True
    return bool(
        re.search(r'\d{3,5}', text)
        or re.search(r'\d+F-\d+', text, re.I)
        or '大厅' in text
    )


def _to_float(value, default=0):
    try:
        return float(str(value).replace(',', ''))
    except ValueError:
        return default


def _to_int(value, default=1):
    try:
        return int(float(str(value).replace(',', '')))
    except ValueError:
        return default


def _build_notes(tenant='', shop='', rent_period=''):
    parts = []
    if tenant:
        parts.append(f'租户:{tenant}')
    if shop:
        parts.append(f'店铺:{shop}')
    if rent_period:
        parts.append(f'催缴租期:{rent_period}')
    return '；'.join(parts)


def _merge_notes(old, new):
    old = old or ''
    new = new or ''
    if not old:
        return new
    if not new or new in old:
        return old
    return old + '；' + new
