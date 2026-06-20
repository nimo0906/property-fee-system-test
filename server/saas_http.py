#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal SaaS HTTP app shim for tenant/session/auth tests."""

from http.cookies import SimpleCookie
import secrets

from server.saas_service import PermissionDenied, SaasBackofficeService

def _percent(numerator, denominator):
    if not denominator:
        return '0.00%'
    return f'{(float(numerator or 0) / float(denominator) * 100):.2f}%'


def _report_summary_with_rates(report):
    due = float(report.get('bill_amount_total') or 0)
    result = dict(report)
    result['collection_rate'] = _percent(result.get('payment_amount_total'), due)
    result['arrears_rate'] = _percent(result.get('unpaid_amount_total'), due)
    return result



class SimpleResponse:
    def __init__(self, status_code=200, json_body=None, cookies=None):
        self.status_code = status_code
        self._json = json_body or {}
        self.cookies = cookies or {}

    def json(self):
        return self._json


class SimpleSaasHttpApp:
    def __init__(self):
        self.service = SaasBackofficeService.in_memory()
        self.sessions = {}
        self.cookies = {}

    def _session_user(self, cookie_header):
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        session_id = cookie.get('session_id')
        if not session_id:
            return None
        return self.sessions.get(session_id.value)

    def _json_response(self, status_code, body=None, cookies=None):
        return SimpleResponse(status_code=status_code, json_body=body or {}, cookies=cookies or {})

    def _headers_with_cookies(self, headers):
        headers = dict(headers or {})
        if self.cookies and 'Cookie' not in headers:
            headers['Cookie'] = '; '.join(f"{k}={v}" for k, v in self.cookies.items())
        return headers

    def post(self, path, json_body=None, headers=None, json=None):
        json_body = json if json is not None else json_body
        json_body = json_body or {}
        headers = self._headers_with_cookies(headers)
        if path == '/auth/login':
            tenant_name = json_body['tenant_name']
            project_name = json_body['project_name']
            username = json_body['username']
            role_code = json_body['role_code']
            tenant_id = self.service.create_tenant(tenant_name)
            project_id = self.service.create_project(tenant_id, project_name)
            user = self.service.create_user(tenant_id, username, role_code)
            user['tenant_name'] = tenant_name
            user['project_name'] = project_name
            user['project_id'] = project_id
            session_id = secrets.token_hex(16)
            self.sessions[session_id] = user
            self.cookies['session_id'] = session_id
            return self._json_response(200, {'ok': True}, {'session_id': session_id})
        user = self._session_user(headers.get('Cookie', ''))
        if not user:
            return self._json_response(401, {'detail': 'unauthenticated'})
        try:
            if path == '/charge-targets':
                target = self.service.create_charge_target(user, user['project_id'], json_body['building'], json_body.get('unit', ''), json_body['room_number'], json_body.get('category', '居民'), json_body.get('area', 0))
                return self._json_response(200, {'item': target})
            if path == '/users':
                item = self.service.create_staff_user(user, user['project_id'], json_body['username'], json_body['role_code'])
                return self._json_response(200, {'item': item})
            if path.startswith('/users/') and path.endswith('/active'):
                user_id = int(path.split('/')[2])
                item = self.service.set_user_active(user, user['project_id'], user_id, bool(json_body['is_active']))
                return self._json_response(200, {'item': item})
            if path.startswith('/users/') and path.endswith('/reset-password'):
                user_id = int(path.split('/')[2])
                item = self.service.reset_user_password(user, user_id, json_body['new_password'])
                return self._json_response(200, {'item': item})
            if path == '/fee-types':
                fee = self.service.create_fee_type(user, user['project_id'], json_body['name'], json_body['unit_price'])
                return self._json_response(200, {'item': fee})
            if path == '/imports/charge-targets/preview':
                preview = self.service.preview_charge_target_import(user, user['project_id'], json_body.get('rows', []))
                return self._json_response(200, preview)
            if path == '/imports/charge-targets/confirm':
                result = self.service.confirm_charge_target_import(user, user['project_id'], json_body['import_id'])
                return self._json_response(200, result)
            if path == '/bills/generate':
                self.service._require(user, 'billing')
                target = self.service.targets[json_body['target_id']]
                fee = self.service.fees[json_body['fee_type_id']]
                bill = self.service.generate_bill(user, user['project_id'], target, fee, json_body['billing_period'], json_body['service_start'], json_body['service_end'])
                return self._json_response(200, {'item': bill})
            if path.startswith('/bills/') and path.endswith('/approve'):
                bill_id = int(path.split('/')[2])
                bill = self.service.approve_bill(user, user['project_id'], bill_id)
                return self._json_response(200, {'item': bill})
            if path == '/payments':
                payment = self.service.record_payment(user, json_body['bill_id'], json_body['amount'], json_body.get('method', ''), json_body.get('idempotency_key'))
                return self._json_response(200, {'item': payment})
            if path == '/audit-logs':
                return self._json_response(200, {'items': self.service.list_audit_logs(user, user['project_id'])})
            if path == '/backups/create':
                return self._json_response(200, {'item': self.service.create_backup_marker(user, user['project_id'])})
        except PermissionDenied:
            return self._json_response(403, {'detail': 'forbidden'})
        return self._json_response(404, {'detail': 'not found'})

    def get(self, path, headers=None):
        headers = self._headers_with_cookies(headers)
        user = self._session_user(headers.get('Cookie', ''))
        if path == '/auth/me':
            if not user:
                return self._json_response(401, {'detail': 'unauthenticated'})
            return self._json_response(200, {'tenant_name': user['tenant_name'], 'project_name': user['project_name'], 'role_code': user['role_code']})
        if not user:
            return self._json_response(401, {'detail': 'unauthenticated'})
        if path == '/users':
            try:
                return self._json_response(200, {'items': self.service.list_staff_users(user, user['project_id'])})
            except PermissionDenied:
                return self._json_response(403, {'detail': 'forbidden'})
        if path == '/charge-targets':
            try:
                items = self.service.list_charge_targets(user, user['project_id'])
                return self._json_response(200, {'items': items})
            except PermissionDenied:
                return self._json_response(403, {'detail': 'forbidden'})
        if path.startswith('/bills'):
            try:
                query = path.split('?', 1)[1] if '?' in path else ''
                params = dict(part.split('=', 1) for part in query.split('&') if '=' in part)
                items = self.service.list_bills(user, user['project_id'], params.get('period') or None, params.get('status') or None)
                return self._json_response(200, {'items': items})
            except PermissionDenied:
                return self._json_response(403, {'detail': 'forbidden'})
        if path == '/audit-logs':
            try:
                return self._json_response(200, {'items': self.service.list_audit_logs(user, user['project_id'])})
            except PermissionDenied:
                return self._json_response(403, {'detail': 'forbidden'})
        if path.startswith('/reports/summary'):
            period = ''
            if '?' in path:
                for part in path.split('?', 1)[1].split('&'):
                    if part.startswith('period='):
                        period = part.split('=', 1)[1]
            report = self.service.report(user, user['project_id'], period)
            return self._json_response(200, _report_summary_with_rates(report))
        if path.startswith('/reports/breakdown'):
            return self._json_response(200, {'by_building': [], 'by_unit': [], 'by_fee_type': [], 'by_category': []})
        return self._json_response(404, {'detail': 'not found'})


class FastApiLikeApp(SimpleSaasHttpApp):
    pass


def create_saas_http_app():
    return FastApiLikeApp()
