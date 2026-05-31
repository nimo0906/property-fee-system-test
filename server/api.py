#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSON API endpoints for stable v2.0 internal interfaces."""

import json
import re

from server.services import BillingService, OwnerService, RoomService, ServiceError


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

    def _api_get(self, path):
        if not self._get_current_user():
            return self._api_error(401, 'unauthorized', '请先登录')
        try:
            if m := re.match(r'^/api/v1/owners/(\d+)$', path):
                return self._api_json(OwnerService().get_owner(int(m.group(1))))
            if m := re.match(r'^/api/v1/rooms/(\d+)$', path):
                return self._api_json(RoomService().get_room(int(m.group(1))))
            if m := re.match(r'^/api/v1/bills/(\d+)$', path):
                return self._api_json(BillingService().get_bill(int(m.group(1))))
            return self._api_error(404, 'not_found', '接口不存在')
        except ServiceError as exc:
            return self._api_error(404, 'not_found', str(exc))
