#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automated acceptance check for the local property fee desktop app.

Default target: packaged desktop app at http://127.0.0.1:5001
This script is intentionally read-mostly: it only POSTs to /login, then uses GET.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAGES = [
    '/', '/billing', '/commercial_billing', '/alert_center', '/reminders', '/import',
    '/merchant_contracts', '/owners', '/rooms', '/fee_types', '/meter_readings',
    '/backups', '/batch_ops', '/auto_billing', '/shared_expenses', '/bills',
    '/payments', '/collections', '/invoices', '/reports', '/closing', '/users',
    '/system_health', '/system_update', '/trial_data_reset',
]
ERROR_PATTERNS = [
    r'Traceback \(most recent call last\)', r'Internal Server Error', r'AttributeError:',
    r'NameError:', r'TypeError:', r'KeyError:', r'sqlite3\.OperationalError',
    r'jinja2\.exceptions', r'NotImplementedError',
]
PLACEHOLDER_RE = re.compile(r'\{[A-Z][A-Z0-9_]{2,}\}')
SKIP_PREFIXES = ('/logout', 'mailto:', 'tel:', 'javascript:', '#')
SKIP_EXTS = ('.xlsx', '.csv', '.zip', '.pdf', '.docx')


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.assets: list[str] = []
        self.forms: list[tuple[str, str]] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'a' and data.get('href'):
            self.links.append(data['href'])
        if tag in ('script', 'img') and data.get('src'):
            self.assets.append(data['src'])
        if tag == 'link' and data.get('href'):
            rel = (data.get('rel') or '').lower()
            if 'stylesheet' in rel or data['href'].startswith('/static/'):
                self.assets.append(data['href'])
        if tag == 'form':
            self.forms.append(((data.get('method') or 'GET').upper(), data.get('action') or ''))

    def handle_data(self, data):
        if data.strip():
            self.text_parts.append(data.strip())


@dataclass
class Result:
    ok: bool = True
    checked_pages: int = 0
    checked_assets: int = 0
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    visited: list[str] = field(default_factory=list)

    def fail(self, msg: str):
        self.ok = False
        self.failures.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)


class Client:
    def __init__(self, base_url: str, timeout: float = 8):
        self.base = base_url.rstrip('/')
        self.timeout = timeout
        self.cookie = ''

    def url(self, path_or_url: str) -> str:
        return urllib.parse.urljoin(self.base + '/', path_or_url)

    def request(self, path: str, data: dict[str, str] | None = None):
        body = None
        headers = {'User-Agent': 'PropertyAcceptanceCheck/1.0'}
        if self.cookie:
            headers['Cookie'] = self.cookie
        if data is not None:
            body = urllib.parse.urlencode(data).encode('utf-8')
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        req = urllib.request.Request(self.url(path), data=body, headers=headers, method='POST' if data is not None else 'GET')
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(req, timeout=self.timeout)
            content = resp.read()
            set_cookie = resp.headers.get('Set-Cookie')
            if set_cookie:
                self.cookie = set_cookie.split(';', 1)[0]
            return resp.status, dict(resp.headers), content
        except urllib.error.HTTPError as exc:
            content = exc.read()
            set_cookie = exc.headers.get('Set-Cookie')
            if set_cookie:
                self.cookie = set_cookie.split(';', 1)[0]
            return exc.code, dict(exc.headers), content


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decode_body(data: bytes) -> str:
    return data.decode('utf-8', errors='replace')


def normalize_internal(base_url: str, current_path: str, href: str) -> str | None:
    href = (href or '').strip()
    if not href or href.startswith(SKIP_PREFIXES):
        return None
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme and not href.startswith(base_url):
        return None
    path = urllib.parse.urljoin(current_path, href)
    parsed = urllib.parse.urlparse(path)
    if parsed.path.startswith('/static/'):
        return parsed.path + (('?' + parsed.query) if parsed.query else '')
    if parsed.path.endswith(SKIP_EXTS):
        return None
    if parsed.path == '/logout':
        return None
    return parsed.path + (('?' + parsed.query) if parsed.query else '')


def assert_page(path: str, status: int, body: str, result: Result):
    if status in (301, 302, 303):
        result.warn(f'{path} redirected; check target if unexpected')
        return
    if status >= 500:
        result.fail(f'{path} returned HTTP {status}')
        return
    if status in (401, 403, 404):
        result.fail(f'{path} returned HTTP {status}')
        return
    for pat in ERROR_PATTERNS:
        if re.search(pat, body):
            result.fail(f'{path} contains error pattern: {pat}')
    placeholders = sorted(set(PLACEHOLDER_RE.findall(body)))
    ignored = {'{FLASH}', '{CONTENT}', '{NAV}', '{TITLE}'}
    bad = [p for p in placeholders if p not in ignored]
    if bad:
        result.fail(f'{path} contains unreplaced placeholders: {", ".join(bad[:8])}')


def check_regressions(pages: dict[str, str], result: Result):
    bills = pages.get('/bills', '')
    if bills:
        for token in ('saveBillOpenState', 'restoreBillOpenState', 'bill-row-action'):
            if token not in bills:
                result.fail(f'/bills missing expand-state regression hook: {token}')
        action_links = re.findall(r'<a[^>]+class="[^"]*bill-row-action[^"]*"[^>]+href="([^"]+)"', bills)
        bad_action_links = [href for href in action_links if href.startswith('/bills/') and 'back=' not in href]
        if bad_action_links:
            result.fail('/bills action links missing back= parameter: ' + ', '.join(bad_action_links[:5]))
    owners = pages.get('/owners', '')
    if owners and 'owner-search-inline' not in owners:
        result.fail('/owners missing compact owner search bar')
    rooms = pages.get('/rooms', '')
    if rooms and 'room-search-inline' not in rooms:
        result.fail('/rooms missing compact room search bar')
    meter = pages.get('/meter_readings', '')
    if meter and '记录总数' in meter and 'summary-tile primary' not in meter:
        result.fail('/meter_readings summary tile markup changed unexpectedly')
    home = pages.get('/', '')
    if home and 'workbench-command-hero-compact' not in home:
        result.fail('/ missing compact home command bar')
    backups = pages.get('/backups', '')
    if backups and '备份记录' not in backups:
        result.fail('/backups should display title 备份记录')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run read-only acceptance checks against the local desktop app.')
    parser.add_argument('--base-url', default='http://127.0.0.1:5001')
    parser.add_argument('--username', default='admin')
    parser.add_argument('--password', default='admin123')
    parser.add_argument('--max-extra-links', type=int, default=80)
    parser.add_argument('--report', default=str(ROOT / 'acceptance-report.json'))
    args = parser.parse_args(argv)

    result = Result()
    client = Client(args.base_url)
    status, headers, body = client.request('/login', {'username': args.username, 'password': args.password})
    if status not in (200, 302, 303) or not client.cookie:
        result.fail(f'login failed: HTTP {status}, cookie={bool(client.cookie)}')
        print_report(result, args.report)
        return 1

    to_visit: list[str] = list(DEFAULT_PAGES)
    seen: set[str] = set()
    pages: dict[str, str] = {}
    assets: set[str] = set()
    extra_added = 0

    while to_visit:
        path = to_visit.pop(0)
        clean = urllib.parse.urlparse(path).path + (('?' + urllib.parse.urlparse(path).query) if urllib.parse.urlparse(path).query else '')
        if clean in seen:
            continue
        seen.add(clean)
        status, headers, raw = client.request(clean)
        body_text = decode_body(raw)
        result.checked_pages += 1
        result.visited.append(clean)
        assert_page(clean, status, body_text, result)
        if status >= 300:
            continue
        ctype = headers.get('Content-Type', '')
        if 'text/html' not in ctype and '<html' not in body_text[:300].lower():
            continue
        pages[urllib.parse.urlparse(clean).path] = body_text
        parser = LinkParser()
        parser.feed(body_text)
        for asset in parser.assets:
            norm = normalize_internal(args.base_url, clean, asset)
            if norm and norm.startswith('/static/'):
                assets.add(norm)
        for href in parser.links:
            norm = normalize_internal(args.base_url, clean, href)
            if not norm or norm.startswith('/static/'):
                continue
            if extra_added < args.max_extra_links and norm not in seen and norm not in to_visit:
                to_visit.append(norm)
                extra_added += 1
        for method, action in parser.forms:
            if method == 'GET':
                norm = normalize_internal(args.base_url, clean, action or clean)
                if norm and norm not in seen and norm not in to_visit and extra_added < args.max_extra_links:
                    to_visit.append(norm)
                    extra_added += 1

    for asset in sorted(assets):
        status, _, raw = client.request(asset)
        result.checked_assets += 1
        if status >= 400:
            result.fail(f'static asset failed HTTP {status}: {asset}')
        elif len(raw) == 0:
            result.fail(f'static asset is empty: {asset}')

    check_regressions(pages, result)
    print_report(result, args.report)
    return 0 if result.ok else 1


def print_report(result: Result, report_path: str):
    payload = {
        'ok': result.ok,
        'checked_pages': result.checked_pages,
        'checked_assets': result.checked_assets,
        'failures': result.failures,
        'warnings': result.warnings,
        'visited': result.visited,
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    Path(report_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('=' * 72)
    print('自动验收检查结果:', 'PASS' if result.ok else 'FAIL')
    print(f'页面: {result.checked_pages}  静态资源: {result.checked_assets}  报告: {report_path}')
    if result.failures:
        print('\n失败项:')
        for item in result.failures:
            print('  -', item)
    if result.warnings:
        print('\n提醒项:')
        for item in result.warnings[:20]:
            print('  -', item)
    print('=' * 72)


if __name__ == '__main__':
    raise SystemExit(main())
