#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard source tree hygiene for desktop release."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_PY_LINES = 300
MAX_CSS_LINES = 300
EXCLUDED_DIRS = {
    '.local_archive', '.pytest_cache', '__pycache__', '.git',
    'build', 'dist', 'release',
}
FORBIDDEN_NAMES = {'property.db', 'runtime_data'}
FORBIDDEN_SUFFIXES = {'.db-wal', '.db-shm', '.log'}
TEST_FILE_PREFIXES = ('tests/',)


def _skip(path):
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _line_count(path):
    with path.open(encoding='utf-8', errors='ignore') as fh:
        return sum(1 for _ in fh)


def main():
    failures = []
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if _skip(rel):
            continue
        if path.is_file() and (path.name in FORBIDDEN_NAMES or path.suffix in FORBIDDEN_SUFFIXES):
            failures.append(f'forbidden runtime file: {rel}')
        if path.is_dir() and path.name in FORBIDDEN_NAMES:
            failures.append(f'forbidden runtime dir: {rel}')
        if path.is_file() and path.suffix == '.py':
            lines = _line_count(path)
            if lines > MAX_PY_LINES:
                if str(rel).startswith(TEST_FILE_PREFIXES):
                    print(f'WARN python too large: {rel} has {lines} lines')
                else:
                    failures.append(f'python too large: {rel} has {lines} lines')
        if path.is_file() and path.match('static/*.css'):
            lines = _line_count(path)
            if lines > MAX_CSS_LINES:
                failures.append(f'css too large: {rel} has {lines} lines')
    if failures:
        for item in failures:
            print('FAIL', item)
        return 1
    print('PASS source tree hygiene')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
