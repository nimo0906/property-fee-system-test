#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Password hashing helpers with legacy SHA-256 compatibility."""

import hashlib
import hmac
import secrets

_ALGORITHM = 'pbkdf2_sha256'
_ITERATIONS = 260000


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', str(password).encode(), salt.encode(), _ITERATIONS)
    return f'{_ALGORITHM}${_ITERATIONS}${salt}${digest.hex()}'


def is_legacy_sha256_hash(encoded):
    text = str(encoded or '')
    return len(text) == 64 and all(ch in '0123456789abcdef' for ch in text.lower())


def verify_password(password, encoded):
    text = str(encoded or '')
    if text.startswith(_ALGORITHM + '$'):
        try:
            _, raw_iterations, salt, expected = text.split('$', 3)
            iterations = int(raw_iterations)
        except (ValueError, TypeError):
            return False
        digest = hashlib.pbkdf2_hmac('sha256', str(password).encode(), salt.encode(), iterations).hex()
        return hmac.compare_digest(digest, expected)
    if is_legacy_sha256_hash(text):
        digest = hashlib.sha256(str(password).encode()).hexdigest()
        return hmac.compare_digest(digest, text)
    return False
