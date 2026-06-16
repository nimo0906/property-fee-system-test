#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base handler class with shared methods and URL routing."""

import csv, http.server, io, urllib.parse, re, json, os

from server.db import get_db, h, qs, log_audit
from server.page_layout import render_page

BASE = os.environ.get('PM_RESOURCE_DIR') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class BaseHttpHandler(http.server.BaseHTTPRequestHandler):
    pass

__all__ = [name for name in globals() if not name.startswith('__')]
