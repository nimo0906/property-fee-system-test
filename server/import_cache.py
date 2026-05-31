#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary upload cache for import preview/confirm workflow."""

import os, secrets, tempfile, time

CACHE_DIR = os.environ.get('PM_IMPORT_CACHE_DIR') or os.path.join(tempfile.gettempdir(), 'property_import_cache')
MAX_AGE_SECONDS = 24 * 60 * 60


def save_import_file(raw_data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cleanup_import_cache()
    token = secrets.token_urlsafe(24)
    with open(_cache_path(token), 'wb') as f:
        f.write(raw_data)
    return token


def load_import_file(token):
    if not _valid_token(token):
        raise FileNotFoundError('invalid import token')
    path = _cache_path(token)
    with open(path, 'rb') as f:
        return f.read()


def cleanup_import_cache():
    if not os.path.exists(CACHE_DIR):
        return
    now = time.time()
    for name in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, name)
        if os.path.isfile(path) and now - os.path.getmtime(path) > MAX_AGE_SECONDS:
            try:
                os.remove(path)
            except OSError:
                pass


def _cache_path(token):
    return os.path.join(CACHE_DIR, token + '.bin')


def _valid_token(token):
    return bool(token) and all(ch.isalnum() or ch in ('_', '-') for ch in token)
