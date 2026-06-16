#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backward-compatible imports for bill pagination."""

from server.pagination import clamp_page, page_url, parse_page, parse_per_page, render_pagination


def render_bill_pagination(query, page, total_pages, per_page, total_rows):
    return render_pagination("/bills", query, page, total_pages, per_page, total_rows, "账单分页")
