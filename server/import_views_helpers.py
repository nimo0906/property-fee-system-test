#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Views and helpers for import preview/result pages."""

import csv, io, urllib.parse

from server.db import h
from server.import_cache import load_import_file, save_import_file

def _safe_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _form_value(form, key, default=''):
    try:
        value = form.getvalue(key, default)
    except AttributeError:
        value = form.get(key, default)
        if isinstance(value, list):
            value = value[0] if value else default
    return default if value is None else str(value)


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default

__all__ = [name for name in globals() if not name.startswith('__')]
