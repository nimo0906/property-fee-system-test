#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Duplicate detection helpers for SaaS charge target imports."""


def target_key(row):
    return (
        str(row.get('building') or '').strip(),
        str(row.get('unit') or '').strip(),
        str(row.get('room_number') or '').strip(),
    )


def existing_target_keys(targets):
    return {target_key(row) for row in targets}


def split_new_and_duplicates(rows, targets):
    seen = existing_target_keys(targets)
    new_rows, duplicate_rows = [], []
    for row in rows:
        key = target_key(row)
        if key in seen:
            duplicate_rows.append(row)
            continue
        seen.add(key)
        new_rows.append(row)
    return new_rows, duplicate_rows
