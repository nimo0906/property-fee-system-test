#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary upload cache for import preview/confirm workflow."""

import os, secrets, tempfile, time

DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), 'property_import_cache')
MAX_AGE_SECONDS = 24 * 60 * 60


def _cache_dir():
    return os.environ.get('PM_IMPORT_CACHE_DIR') or DEFAULT_CACHE_DIR


def save_import_file(raw_data):
    os.makedirs(_cache_dir(), exist_ok=True)
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
    cache_dir = _cache_dir()
    if not os.path.exists(cache_dir):
        return
    now = time.time()
    for name in os.listdir(cache_dir):
        path = os.path.join(cache_dir, name)
        if os.path.isfile(path) and now - os.path.getmtime(path) > MAX_AGE_SECONDS:
            try:
                os.remove(path)
            except OSError:
                pass


def _cache_path(token):
    return os.path.join(_cache_dir(), token + '.bin')


def _valid_token(token):
    return bool(token) and all(ch.isalnum() or ch in ('_', '-') for ch in token)
