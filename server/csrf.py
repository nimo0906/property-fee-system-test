#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSRF token helpers for cookie-authenticated backend POST requests."""

import hmac
import hashlib
import os
import re

SECRET = os.environ.get('PM_CSRF_SECRET') or 'property-fee-system-local-csrf-v1'
SAFE_POST_PATHS = {'/login', '/register'}
TOKEN_FIELD = '_csrf_token'
TOKEN_HEADER = 'X-CSRF-Token'


def session_token_from_cookie(cookie):
    match = re.search(r'session_token=([^;]+)', cookie or '')
    return match.group(1) if match else ''


def csrf_token_for_session(session_token):
    if not session_token:
        return ''
    return hmac.new(SECRET.encode('utf-8'), session_token.encode('utf-8'), hashlib.sha256).hexdigest()


def csrf_token_for_handler(handler):
    return csrf_token_for_session(session_token_from_cookie(handler.headers.get('Cookie', '')))


def token_from_form(form):
    if hasattr(form, 'getfirst'):
        return form.getfirst(TOKEN_FIELD, '') or ''
    value = form.get(TOKEN_FIELD, ['']) if isinstance(form, dict) else ''
    if isinstance(value, list):
        return value[0] if value else ''
    return value or ''


def token_from_request(handler, form=None):
    return handler.headers.get(TOKEN_HEADER, '') or token_from_form(form or {})


def csrf_valid(handler, form=None):
    expected = csrf_token_for_handler(handler)
    supplied = token_from_request(handler, form)
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def inject_csrf_fields(html, token):
    if not token:
        return html
    hidden = f'<input type="hidden" name="{TOKEN_FIELD}" value="{token}">'
    pattern = re.compile(r'(<form\b(?=[^>]*\bmethod\s*=\s*(["\']?)post\2)[^>]*>)', re.I)
    return pattern.sub(lambda m: m.group(1) + hidden, html)
