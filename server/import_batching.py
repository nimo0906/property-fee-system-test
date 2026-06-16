#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small helpers for paged import previews."""

PREVIEW_BATCH_SIZE = 200


def parse_nonnegative_int(value, default=0):
    try:
        parsed = int(str(value or '').strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def batch_window(total, requested_offset, limit=PREVIEW_BATCH_SIZE):
    total = max(0, int(total or 0))
    offset = parse_nonnegative_int(requested_offset, 0)
    if total and offset >= total:
        offset = max(0, ((total - 1) // limit) * limit)
    end = min(total, offset + limit)
    return offset, end, max(0, end - offset), end < total


def continuation_from_form(form):
    token = form.getvalue('upload_token', '')
    next_offset = parse_nonnegative_int(form.getvalue('next_import_offset', ''), 0)
    total = parse_nonnegative_int(form.getvalue('preview_total_rows', ''), 0)
    if token and total and next_offset and next_offset < total:
        return {
            'upload_token': token,
            'next_offset': next_offset,
            'total': total,
            'data_type': form.getvalue('data_type', 'rooms'),
            'filename': form.getvalue('filename', ''),
        }
    return None
