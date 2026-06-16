#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for pure utility functions in server/db.py.

Tests are independent of the database — pure functions only.
"""

import unittest
from datetime import date
from server.db import h, m, qs, get_period, add_months
from server.pagination import clamp_page, page_url, parse_page, parse_per_page, render_pagination


class TestEscape(unittest.TestCase):
    """h() — HTML escaping"""

    def test_plain_text_unchanged(self):
        self.assertEqual(h('hello'), 'hello')
        self.assertEqual(h('123'), '123')
        self.assertEqual(h(''), '')

    def test_none_returns_empty(self):
        self.assertEqual(h(None), '')

    def test_escapes_ampersand(self):
        self.assertEqual(h('a&b'), 'a&amp;b')

    def test_escapes_lt(self):
        self.assertEqual(h('a<b'), 'a&lt;b')

    def test_escapes_gt(self):
        self.assertEqual(h('a>b'), 'a&gt;b')

    def test_escapes_double_quote(self):
        self.assertEqual(h('a"b'), 'a&quot;b')

    def test_escapes_single_quote(self):
        self.assertEqual(h("a'b"), 'a&#x27;b')

    def test_escapes_all_together(self):
        result = h('<script>alert("x&y")</script>')
        self.assertNotIn('<script>', result)
        self.assertNotIn('"', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertIn('alert(&quot;x&amp;y&quot;)', result)


class TestMoneyFormat(unittest.TestCase):
    """m() — money formatting to 2 decimal places"""

    def test_formats_integer(self):
        self.assertEqual(m(100), '100.00')

    def test_formats_float(self):
        self.assertEqual(m(123.456), '123.46')
        self.assertEqual(m(99.1), '99.10')

    def test_handles_none(self):
        self.assertEqual(m(None), '0.00')

    def test_handles_zero(self):
        self.assertEqual(m(0), '0.00')

    def test_handles_string_number(self):
        self.assertEqual(m('50.5'), '50.50')

    def test_rounds_up(self):
        self.assertEqual(m(0.005), '0.01')  # round half away from zero

    def test_large_number(self):
        self.assertEqual(m(1234567.89), '1234567.89')


class TestQueryString(unittest.TestCase):
    """qs() — query string value extraction"""

    def test_gets_first_value_from_list(self):
        self.assertEqual(qs({'k': ['v1', 'v2']}, 'k'), 'v1')

    def test_returns_scalar_value(self):
        self.assertEqual(qs({'k': 'v'}, 'k'), 'v')

    def test_returns_default_for_missing_key(self):
        self.assertEqual(qs({}, 'k', 'dfl'), 'dfl')

    def test_empty_string_default(self):
        self.assertEqual(qs({}, 'k'), '')

    def test_handles_none_value(self):
        self.assertEqual(qs({'k': None}, 'k'), '')

    def test_empty_string_treated_as_falsy(self):
        """qs() uses 'or' — empty string is falsy, returns default."""
        self.assertEqual(qs({'k': ''}, 'k', 'fallback'), 'fallback')


class TestPeriod(unittest.TestCase):
    """get_period() — current billing period"""

    def test_returns_yyyy_mm_format(self):
        p = get_period()
        self.assertRegex(p, r'^\d{4}-\d{2}$')

    def test_matches_current_year(self):
        p = get_period()
        today = date.today()
        expected = f"{today.year}-{today.month:02d}"
        self.assertEqual(p, expected)


class TestAddMonths(unittest.TestCase):
    """add_months() — date arithmetic"""

    def test_add_zero(self):
        d = date(2026, 5, 15)
        self.assertEqual(add_months(d, 0), d)

    def test_add_one_month(self):
        self.assertEqual(add_months(date(2026, 5, 15), 1), date(2026, 6, 15))

    def test_add_twelve_months(self):
        self.assertEqual(add_months(date(2026, 5, 15), 12), date(2027, 5, 15))

    def test_subtract_one_month(self):
        self.assertEqual(add_months(date(2026, 5, 15), -1), date(2026, 4, 15))

    def test_wrap_year_forward(self):
        self.assertEqual(add_months(date(2026, 11, 15), 3), date(2027, 2, 15))

    def test_wrap_year_backward(self):
        self.assertEqual(add_months(date(2026, 2, 15), -3), date(2025, 11, 15))

    def test_clamps_day_at_month_boundary(self):
        # Jan 31 + 1 month = Feb 28 (2026 is not a leap year)
        result = add_months(date(2026, 1, 31), 1)
        self.assertEqual(result, date(2026, 2, 28))

    def test_clamps_day_leap_year(self):
        # Jan 31 + 1 month in leap year 2024 = Feb 29
        result = add_months(date(2024, 1, 31), 1)
        self.assertEqual(result, date(2024, 2, 29))

    def test_handles_cross_year_boundary(self):
        self.assertEqual(add_months(date(2026, 12, 10), 1), date(2027, 1, 10))

    def test_handles_negative_resulting_in_previous_year(self):
        self.assertEqual(add_months(date(2026, 1, 10), -1), date(2025, 12, 10))


class TestPaginationHelpers(unittest.TestCase):
    """Reusable list pagination helpers."""

    def test_parse_page_and_per_page_use_safe_defaults(self):
        self.assertEqual(parse_page('abc'), 1)
        self.assertEqual(parse_page('-2'), 1)
        self.assertEqual(parse_per_page('999'), 50)
        self.assertEqual(parse_per_page('100'), 100)

    def test_clamp_page_keeps_page_inside_range(self):
        self.assertEqual(clamp_page(9, 3), 3)
        self.assertEqual(clamp_page(0, 3), 1)
        self.assertEqual(clamp_page(1, 0), 1)

    def test_page_url_preserves_filters_and_uses_base_path(self):
        url = page_url('/payments', [('keyword', '商户A'), ('page', '2'), ('per_page', '50')], 3, 100)
        self.assertTrue(url.startswith('/payments?'))
        self.assertIn('keyword=%E5%95%86%E6%88%B7A', url)
        self.assertIn('page=3', url)
        self.assertIn('per_page=100', url)
        self.assertNotIn('page=2', url)

    def test_render_pagination_is_not_bill_specific(self):
        html = render_pagination('/payments', [('method', 'cash')], 3, 9, 50, 430, '缴费分页')
        self.assertIn('aria-label="缴费分页"', html)
        self.assertIn('/payments?method=cash&amp;page=4&amp;per_page=50', html)
        self.assertIn('page-ellipsis', html)
        self.assertIn('当前筛选共 430 条 / 9 页 / 每页 50 条', html)


if __name__ == '__main__':
    unittest.main()
