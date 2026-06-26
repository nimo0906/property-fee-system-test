#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for shared UI shell helpers."""

from server.ui_components import render_form, render_table


def test_render_table_wraps_headers_rows_and_responsive_container():
    html = render_table(
        ['姓名', ('面积', 'text-end'), '操作'],
        '<tr><td>张三</td><td class="text-end">59.4</td><td>编辑</td></tr>',
    )

    assert html.startswith('<div class="table-responsive">')
    assert '<table class="table table-hover align-middle">' in html
    assert '<th>姓名</th>' in html
    assert '<th class="text-end">面积</th>' in html
    assert '<tbody><tr><td>张三</td>' in html
    assert html.endswith('</table></div>')


def test_render_table_renders_empty_state_with_colspan():
    html = render_table(['项目', '金额'], '', empty_text='没有记录')

    assert '<td colspan="2" class="text-center text-muted py-3">没有记录</td>' in html


def test_render_table_allows_non_responsive_and_custom_class():
    html = render_table(['项目'], '<tr><td>物业费</td></tr>', responsive=False, table_class='table table-sm')

    assert not html.startswith('<div class="table-responsive">')
    assert '<table class="table table-sm">' in html


def test_render_form_builds_standard_post_form_without_duplicating_csrf():
    html = render_form(
        '<div class="col-md-4"><input name="name"></div>',
        action='/owners/create',
        submit_text='保存业主',
        cancel_url='/owners',
    )

    assert html.startswith('<form method="POST" action="/owners/create" class="row g-3">')
    assert '<input name="name">' in html
    assert '<button type="submit" class="btn btn-primary">保存业主</button>' in html
    assert '<a class="btn btn-outline-secondary" href="/owners">取消</a>' in html
    assert '_csrf_token' not in html
    assert 'X-CSRF-Token' not in html
