#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable pagination helpers for list pages."""

import urllib.parse

from server.db import h


DEFAULT_PER_PAGE = 50
PER_PAGE_OPTIONS = (50, 100, 200)


def business_area_order_sql(building_expr, unit_expr):
    """SQL CASE for peer business areas that should not be buried by pagination."""
    return (
        f"CASE "
        f"WHEN COALESCE({unit_expr},'')='商场' OR COALESCE({building_expr},'')='商场' THEN 0 "
        f"WHEN COALESCE({unit_expr},'')='B座' OR COALESCE({building_expr},'') LIKE 'B%' THEN 1 "
        f"WHEN COALESCE({unit_expr},'')='A座' OR COALESCE({building_expr},'') LIKE 'A%' THEN 2 "
        f"ELSE 3 END"
    )


def parse_per_page(value, default=DEFAULT_PER_PAGE):
    try:
        per_page = int(value or default)
    except Exception:
        per_page = default
    return per_page if per_page in PER_PAGE_OPTIONS else default


def parse_page(value):
    try:
        page = int(value or 1)
    except Exception:
        page = 1
    return max(1, page)


def clamp_page(page, total_pages):
    return min(max(1, int(page or 1)), max(1, int(total_pages or 1)))


def page_url(base_path, query, page, per_page):
    items = []
    for key, value in query:
        if key in ("page", "per_page") or value in (None, ""):
            continue
        items.append((key, value))
    items.extend([("page", page), ("per_page", per_page)])
    return base_path + "?" + urllib.parse.urlencode(items)


def page_window(page, total_pages, radius=2):
    pages = {1, total_pages}
    for offset in range(-radius, radius + 1):
        pages.add(page + offset)
    return sorted(p for p in pages if 1 <= p <= total_pages)


def render_pagination(base_path, query, page, total_pages, per_page, total_rows, aria_label="列表分页"):
    if total_pages <= 1:
        return f'<div class="text-center text-muted small my-2">当前筛选共 {total_rows} 条 / 1 页 / 每页 {per_page} 条</div>'
    parts = [f'<nav class="mt-2 list-pagination" aria-label="{h(aria_label)}">']
    parts.append(f'<div class="text-center text-muted small mb-2">当前筛选共 {total_rows} 条 / {total_pages} 页 / 每页 {per_page} 条</div>')
    parts.append('<ul class="pagination pagination-sm justify-content-center flex-wrap gap-1">')
    parts.append(_page_item(base_path, query, "首页", 1, page == 1, per_page))
    parts.append(_page_item(base_path, query, "上一页", max(1, page - 1), page == 1, per_page))
    last = 0
    for target in page_window(page, total_pages):
        if last and target - last > 1:
            parts.append('<li class="page-item disabled page-ellipsis"><span class="page-link">...</span></li>')
        parts.append(_page_item(base_path, query, str(target), target, False, per_page, active=(target == page)))
        last = target
    parts.append(_page_item(base_path, query, "下一页", min(total_pages, page + 1), page == total_pages, per_page))
    parts.append(_page_item(base_path, query, "尾页", total_pages, page == total_pages, per_page))
    parts.append("</ul>")
    parts.append(_jump_form(base_path, query, page, total_pages, per_page))
    parts.append("</nav>")
    return "".join(parts)


def pagination_state(q, total_rows):
    per_page = parse_per_page(_first_query_value(q, "per_page", str(DEFAULT_PER_PAGE)))
    total_pages = max(1, (int(total_rows or 0) + per_page - 1) // per_page)
    page = clamp_page(parse_page(_first_query_value(q, "page", "1")), total_pages)
    return page, per_page, total_pages


def query_items(q, keys):
    return [(key, _first_query_value(q, key, "")) for key in keys]


def _first_query_value(q, key, default=""):
    value = q.get(key, [default]) if hasattr(q, "get") else default
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def _page_item(base_path, query, label, target, disabled, per_page, active=False):
    state = " disabled" if disabled else (" active" if active else "")
    href = "#" if disabled else h(page_url(base_path, query, target, per_page))
    return f'<li class="page-item{state}"><a class="page-link" href="{href}">{h(label)}</a></li>'


def _jump_form(base_path, query, page, total_pages, per_page):
    hidden = []
    for key, value in query:
        if key in ("page", "per_page") or value in (None, ""):
            continue
        hidden.append(f'<input type="hidden" name="{h(key)}" value="{h(value)}">')
    options = "".join(
        f'<option value="{n}"{" selected" if per_page == n else ""}>每页 {n} 条</option>'
        for n in PER_PAGE_OPTIONS
    )
    return f'''<form method="GET" action="{h(base_path)}" class="d-flex flex-wrap justify-content-center align-items-center gap-2 small">
        {''.join(hidden)}
        <select name="per_page" class="form-select form-select-sm" style="width:auto" onchange="this.form.submit()">{options}</select>
        <label class="text-muted">跳转到第</label>
        <input name="page" type="number" min="1" max="{total_pages}" value="{page}" class="form-control form-control-sm" style="width:82px">
        <span class="text-muted">页</span>
        <button class="btn btn-sm btn-outline-primary">跳转</button>
    </form>'''
