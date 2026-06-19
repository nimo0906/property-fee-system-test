#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared password policy helpers for SaaS accounts."""

PASSWORD_MIN_LENGTH = 8


def password_meets_policy(password):
    return len(password or '') >= PASSWORD_MIN_LENGTH


def password_length_error(label):
    return f'{label}至少 {PASSWORD_MIN_LENGTH} 位'


def password_policy_summary():
    return [
        '密码策略',
        f'最少 {PASSWORD_MIN_LENGTH} 位',
        '个人改密不能与原密码相同',
        '管理员重置临时密码不能与当前密码相同',
        '密码不展示在页面、日志或审计明细',
    ]


def password_change_error(old_password, new_password):
    if old_password == new_password:
        return '新密码不能与原密码相同'
    return None


def password_reset_error(current_password_matches_new):
    if current_password_matches_new:
        return '临时密码不能与当前密码相同'
    return None
