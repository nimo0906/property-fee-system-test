#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared password policy helpers for SaaS accounts."""

PASSWORD_MIN_LENGTH = 8


def password_meets_policy(password):
    return len(password or '') >= PASSWORD_MIN_LENGTH


def password_length_error(label):
    return f'{label}至少 {PASSWORD_MIN_LENGTH} 位'


def password_change_error(old_password, new_password):
    if old_password == new_password:
        return '新密码不能与原密码相同'
    return None
