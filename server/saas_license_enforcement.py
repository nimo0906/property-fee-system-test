#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""License enforcement helpers with sanitized audit logging."""

from server.saas_license_status import build_saas_license_status


class LicenseRequired(Exception):
    pass


def require_license_or_audit(user, module, license_service=None, service=None, repository=None):
    if license_service is None:
        return True
    status = build_saas_license_status(license_service, user.get('tenant_name') or '')
    if status.get('allowed'):
        return True
    detail = {
        'module': module,
        'license_status': status.get('status') or 'unknown',
        'blocked': True,
    }
    _write_audit(user, service, repository, detail)
    raise LicenseRequired('license_required')


def _write_audit(user, service, repository, detail):
    if repository:
        repository.create_audit_log(user['tenant_id'], user['project_id'], user.get('id'), 'license.write_blocked', 'license', 0, detail)
    elif service:
        service._log(user, user['project_id'], 'license.write_blocked', 'license', None, detail)
