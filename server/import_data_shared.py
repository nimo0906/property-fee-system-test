#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data import from CSV/Excel files."""

import os
import io

import openpyxl

from server.db import get_db
from server.base import BaseHandler
from server.form_parser import parse_form_data
from server.import_parser import (
    SUPPORTED_EXTENSIONS,
    build_column_map,
    detect_data_type,
    detect_header_row,
    enrich_column_map_from_subheader,
    parse_rows,
)
from server.basic_import import import_basic_info
from server.backups import create_db_backup
from server.import_cache import load_import_file, save_import_file
from server.import_fee_mapping_views import ImportFeeMappingMixin
from server.import_preview_views import ImportPreviewMixin
from server.import_views import ImportViewMixin
from server.merchant_contract_import import _load_rows as load_commercial_contract_rows
from server.merchant_contract_import_view import render_contract_import_preview
from server.b_tower_contract_import import (
    import_b_tower_contract_rows, looks_like_b_tower_contract,
    parse_b_tower_contract_rows, render_b_tower_contract_preview, rows_from_b_tower_form,
)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = SUPPORTED_EXTENSIONS

def _has_commercial_contract_sheet(filename, raw_data):
    if not filename.lower().endswith('.xlsx'):
        return False
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw_data), read_only=True, data_only=True)
        found = '在租合同' in wb.sheetnames
        wb.close()
        return found
    except Exception:
        return False

__all__ = [name for name in globals() if not name.startswith('__')]
