#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""License seat limit helpers for SaaS staff accounts."""

from server.saas_license_binding import license_customer_code_for_user
from server.saas_license_status import build_saas_license_status


class LicenseSeatsExceeded(Exception):
    pass


def active_staff_count(service, repository, user):
    if repository:
        users = repository.list_users_for_actor(user)
        return sum(1 for item in users if int(item.get('is_active', 1)) == 1)
    return sum(1 for item in service.users.values() if item.get('tenant_id') == user.get('tenant_id') and int(item.get('is_active', 1)) == 1)


def licensed_seats(license_service, user, service=None, repository=None):
    customer_code = license_customer_code_for_user(service, repository, user) if service else ''
    status = build_saas_license_status(license_service, customer_code)
    return int(status.get('seats') or 0)


def seats_available(license_service, service, repository, user, increment=1):
    if license_service is None:
        return True
    seats = licensed_seats(license_service, user, service, repository)
    if seats <= 0:
        return False
    return active_staff_count(service, repository, user) + int(increment) <= seats


def require_seat_available(user, module, license_service=None, service=None, repository=None, increment=1):
    if seats_available(license_service, service, repository, user, increment):
        return True
    detail = {
        'module': module,
        'licensed_seats': licensed_seats(license_service, user, service, repository),
        'active_staff_count': active_staff_count(service, repository, user),
        'blocked': True,
    }
    if repository:
        repository.create_audit_log(user['tenant_id'], user['project_id'], user.get('id'), 'license.seats_exceeded', 'license', 0, detail)
    elif service:
        service._log(user, user['project_id'], 'license.seats_exceeded', 'license', None, detail)
    raise LicenseSeatsExceeded('license_seats_exceeded')
