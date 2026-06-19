#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sanitized license status adapter for SaaS staff backoffice."""

from server.saas_license_binding import license_customer_code_for_user

PRODUCT_CODE = 'property-saas-backoffice'
_ALLOWED_FIELDS = {'allowed', 'status', 'customer_code', 'product_code', 'seats', 'expires_at'}


def build_saas_license_status(license_service, customer_code, product_code=PRODUCT_CODE):
    if not license_service:
        return {
            'allowed': False,
            'status': 'not_configured',
            'customer_code': customer_code,
            'product_code': product_code,
            'seats': 0,
            'expires_at': '',
        }
    raw = license_service.check_license(customer_code, product_code)
    return {key: raw.get(key) for key in _ALLOWED_FIELDS}


def license_allows_write(license_service, customer_code):
    return bool(build_saas_license_status(license_service, customer_code).get('allowed'))


def render_saas_license_status(user, license_service=None, service=None, repository=None):
    customer_code = license_customer_code_for_user(service, repository, user) if service else ''
    status = build_saas_license_status(license_service, customer_code)
    label = '已授权' if status.get('allowed') else _status_label(status.get('status'))
    seats = int(status.get('seats') or 0)
    expires = status.get('expires_at') or '未配置'
    badge = 'ok' if status.get('allowed') else 'warn'
    binding = '<span class="badge">授权客户 '+_h(customer_code)+'</span>' if customer_code else '<span class="badge warn">未绑定授权客户</span>'
    restriction = '' if status.get('allowed') else '<div class="hint"><strong>授权限制：</strong>已限制出账、收费项目、收费对象、导入确认和备份创建等写入操作；只读查看仍可用于核对数据。</div>'
    return f'''<section class="card" style="margin-bottom:18px"><div class="card-h">授权状态</div><div class="card-b"><div class="actions"><span class="badge {badge}">{_h(label)}</span><span class="badge">席位 {seats}</span><span class="badge">到期 {_h(expires)}</span>{binding}</div><div class="hint">本区域只读取授权云服务返回结果，不展示授权库、业务库、内部租户编号或客户上传数据。</div>{restriction}</div></section>'''


def _status_label(value):
    return {'missing': '未授权', 'not_configured': '未接入授权服务', 'inactive': '已停用'}.get(str(value or ''), str(value or '未知'))


def _h(value):
    return str(value or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
