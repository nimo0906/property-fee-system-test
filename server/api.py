#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSON API endpoints for stable v2.0 internal interfaces."""

import json
import re
import urllib.parse

from server.backups import create_db_backup
from server.invoice_requests import InvoiceRequestError, InvoiceRequestService
from server.notifications import NotificationService
from server.owner_portal import OwnerPortalError, OwnerPortalService
from server.payment_orders import PaymentOrderError, PaymentOrderService
from server.projects import ProjectError, ProjectService
from server.services import Actor, BillingService, OwnerService, PaymentService, RoomService, ServiceError


class ApiMixin:
    def _api_json(self, data, code=200):
        body = json.dumps({'ok': True, 'data': data}, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_error(self, code, error_code, message):
        body = json.dumps({
            'ok': False,
            'error': {'code': error_code, 'message': message},
        }, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


    def _owner_portal_token(self):
        cookie = self.headers.get('Cookie', '')
        if m := re.search(r'owner_portal_token=([^;]+)', cookie):
            return m.group(1)
        return ''

    def _owner_portal_session(self):
        token = self._owner_portal_token()
        if not token:
            raise OwnerPortalError('请先登录')
        return OwnerPortalService().get_session(token)

    def _api_get(self, path):
        if path.startswith('/api/v1/owner-portal/'):
            try:
                service = OwnerPortalService()
                session = self._owner_portal_session()
                if path == '/api/v1/owner-portal/profile':
                    return self._api_json(service.profile(session))
                if path == '/api/v1/owner-portal/rooms':
                    return self._api_json(service.rooms(session))
                if path == '/api/v1/owner-portal/bills':
                    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    filters = {key: values[0] for key, values in q.items() if values}
                    return self._api_json(service.bills(session, filters))
                if path == '/api/v1/owner-portal/payments':
                    return self._api_json(service.payments(session))
                if path == '/api/v1/owner-portal/notifications':
                    return self._api_json(NotificationService().list_events(owner_id=session['owner_id']))
                if path == '/api/v1/owner-portal/invoice-requests':
                    return self._api_json(InvoiceRequestService().list_requests({'owner_id': session['owner_id']}))
                if m := re.match(r'^/api/v1/owner-portal/invoice-requests/([^/]+)$', path):
                    item = InvoiceRequestService().get_request(m.group(1))
                    if item['owner_id'] != session['owner_id']:
                        return self._api_error(403, 'forbidden', '无权限查看该票据请求')
                    return self._api_json(item)
                if path == '/api/v1/owner-portal/payment-orders':
                    return self._api_json(PaymentOrderService().list_orders(session))
                if m := re.match(r'^/api/v1/owner-portal/payment-orders/([^/]+)$', path):
                    return self._api_json(PaymentOrderService().get_order(session, m.group(1)))
                return self._api_error(404, 'not_found', '接口不存在')
            except PaymentOrderError as exc:
                return self._api_error(404, 'not_found', str(exc))
            except OwnerPortalError as exc:
                return self._api_error(401, 'unauthorized', str(exc))
        if not self._get_current_user():
            return self._api_error(401, 'unauthorized', '请先登录')
        try:
            if path == '/api/v1/projects':
                return self._api_json(ProjectService().list_projects())
            if m := re.match(r'^/api/v1/projects/(\d+)$', path):
                return self._api_json(ProjectService().get_project(int(m.group(1))))
            if m := re.match(r'^/api/v1/owners/(\d+)$', path):
                return self._api_json(OwnerService().get_owner(int(m.group(1))))
            if m := re.match(r'^/api/v1/rooms/(\d+)$', path):
                return self._api_json(RoomService().get_room(int(m.group(1))))
            if m := re.match(r'^/api/v1/bills/(\d+)$', path):
                return self._api_json(BillingService().get_bill(int(m.group(1))))
            if path == '/api/v1/invoice-requests':
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                filters = {key: values[0] for key, values in q.items() if values}
                return self._api_json(InvoiceRequestService().list_requests(filters))
            if m := re.match(r'^/api/v1/invoice-requests/([^/]+)$', path):
                return self._api_json(InvoiceRequestService().get_request(m.group(1)))
            return self._api_error(404, 'not_found', '接口不存在')
        except (ServiceError, InvoiceRequestError, ProjectError) as exc:
            return self._api_error(404, 'not_found', str(exc))


    def _api_post(self, path, data):
        request = {key: values[0] if isinstance(values, list) and values else values for key, values in data.items()}
        if path == '/api/v1/payment-callbacks/mock':
            try:
                request['channel'] = 'mock'
                return self._api_json(PaymentOrderService().process_callback(request))
            except (PaymentOrderError, InvoiceRequestError) as exc:
                return self._api_error(400, 'validation_error', str(exc))
        if path.startswith('/api/v1/owner-portal/'):
            service = OwnerPortalService()
            try:
                if path == '/api/v1/owner-portal/send-code':
                    return self._api_json(service.send_code(request.get('phone')))
                if path == '/api/v1/owner-portal/login':
                    result = service.login(request.get('phone'), request.get('code'))
                    token = result.pop('token')
                    body = json.dumps({'ok': True, 'data': result}, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Set-Cookie', f'owner_portal_token={token}; HttpOnly; SameSite=Lax; Path=/')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers(); self.wfile.write(body)
                    return
                if path == '/api/v1/owner-portal/payments/preview':
                    session = self._owner_portal_session()
                    return self._api_json(service.preview_payment(session, request))
                if path == '/api/v1/owner-portal/payment-orders':
                    session = self._owner_portal_session()
                    return self._api_json(PaymentOrderService().create_order(session, request))
                if path == '/api/v1/owner-portal/invoice-requests':
                    session = self._owner_portal_session()
                    return self._api_json(InvoiceRequestService().create_owner_request(session, request))
                if m := re.match(r'^/api/v1/owner-portal/payment-orders/([^/]+)/mock-paid$', path):
                    session = self._owner_portal_session()
                    return self._api_json(PaymentOrderService().mark_mock_paid(session, m.group(1)))
                return self._api_error(404, 'not_found', '接口不存在')
            except (PaymentOrderError, InvoiceRequestError) as exc:
                return self._api_error(400, 'validation_error', str(exc))
            except OwnerPortalError as exc:
                code = 'forbidden' if '无权限' in str(exc) else 'unauthorized'
                status = 403 if code == 'forbidden' else 401
                return self._api_error(status, code, str(exc))
            except ServiceError as exc:
                return self._api_error(400, 'validation_error', str(exc))
        if not self._get_current_user():
            return self._api_error(401, 'unauthorized', '请先登录')
        try:
            if path == '/api/v1/payments/preview':
                return self._api_json(PaymentService().preview_payment(request))
            if path == '/api/v1/invoice-requests':
                user = self._get_current_user() or {}
                if user.get('role') == 'readonly':
                    return self._api_error(403, 'forbidden', '无权限执行写操作')
                return self._api_json(InvoiceRequestService().create_request(request))
            if path == '/api/v1/payments':
                user = self._get_current_user() or {}
                if user.get('role') == 'readonly':
                    return self._api_error(403, 'forbidden', '无权限执行写操作')
                backup_name = create_db_backup('auto_before_api_payment')
                result = PaymentService().create_payment(
                    request,
                    Actor(username=user.get('username') or '', role=user.get('role') or ''),
                )
                result['backup_name'] = backup_name
                result['idempotency_key'] = request.get('idempotency_key') or ''
                self._audit(
                    'api_payment_create', 'payment', result['payment_id'],
                    new_value=result, reason='JSON API payment create',
                )
                return self._api_json(result)
            return self._api_error(404, 'not_found', '接口不存在')
        except (ServiceError, InvoiceRequestError, ProjectError) as exc:
            return self._api_error(400, 'validation_error', str(exc))
