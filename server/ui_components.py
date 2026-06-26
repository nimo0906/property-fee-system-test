#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared HTML shell helpers for common tables and forms."""

import html


def _esc(value):
    return html.escape(str(value or ''), quote=True)


def render_table(headers, body_rows_html, *, table_class='table table-hover align-middle',
                 responsive=True, empty_text='暂无数据', col_count=None,
                 responsive_class='table-responsive'):
    """Render a common table shell while keeping row generation page-local."""
    col_count = col_count or len(headers)
    th_parts = []
    for item in headers:
        if isinstance(item, tuple):
            label, cls = item
            th_parts.append(f'<th class="{_esc(cls)}">{_esc(label)}</th>')
        else:
            th_parts.append(f'<th>{_esc(item)}</th>')
    rows = (body_rows_html or '').strip()
    if not rows:
        rows = f'<tr><td colspan="{int(col_count)}" class="text-center text-muted py-3">{_esc(empty_text)}</td></tr>'
    table = f'<table class="{_esc(table_class)}"><thead><tr>{"".join(th_parts)}</tr></thead><tbody>{rows}</tbody></table>'
    if responsive:
        return f'<div class="{_esc(responsive_class)}">{table}</div>'
    return table


def render_form(fields_html, *, action, method='POST', submit_text='保存', cancel_url=None,
                form_class='row g-3'):
    """Render a standard form shell; CSRF is injected later by BaseHandler._html()."""
    # submit_text is trusted static UI copy from server-side code; allow icon HTML.
    buttons = [f'<button type="submit" class="btn btn-primary">{submit_text or "保存"}</button>']
    if cancel_url:
        buttons.append(f'<a class="btn btn-outline-secondary" href="{_esc(cancel_url)}">取消</a>')
    return (
        f'<form method="{_esc(method).upper()}" action="{_esc(action)}" class="{_esc(form_class)}">'
        f'{fields_html or ""}'
        f'<div class="col-12 d-flex gap-2">{"".join(buttons)}</div>'
        '</form>'
    )


def render_kv_table(rows, *, table_class='table table-borderless mb-0', label_width='130px'):
    """Render a simple key/value detail table; values are trusted server-side HTML."""
    body = []
    first = True
    for label, value in rows:
        width = f' style="width:{_esc(label_width)}"' if first and label_width else ''
        body.append(
            f'<tr><td class="text-muted"{width}>{_esc(label)}</td><td>{str(value) if value is not None else ""}</td></tr>'
        )
        first = False
    return f'<table class="{_esc(table_class)}">{"".join(body)}</table>'
