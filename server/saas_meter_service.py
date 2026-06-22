#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-memory SaaS meter reading methods."""

from server.saas_service import PermissionDenied


def _reading_dict(rid, user, project_id, target_id, fee_id, period, previous, current, reading_date, status, notes, bill_id=None):
    consumption = round(float(current) - float(previous), 2)
    if consumption < 0:
        raise ValueError('current reading cannot be lower than previous reading')
    return {
        'id': rid, 'tenant_id': user['tenant_id'], 'project_id': project_id,
        'charge_target_id': int(target_id), 'fee_type_id': int(fee_id), 'billing_period': period,
        'previous_reading': float(previous), 'current_reading': float(current), 'consumption': consumption,
        'reading_date': reading_date, 'status': status or 'draft', 'notes': notes or '', 'bill_id': bill_id,
    }


def attach_meter_methods(cls):
    def create_meter_reading(self, user, project_id, target_id, fee_id, period, previous, current, reading_date, status='draft', notes=''):
        self._require(user, 'write')
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied('cross tenant project')
        target = self.targets.get(int(target_id))
        fee = self.fees.get(int(fee_id))
        if not target or target['tenant_id'] != user['tenant_id'] or target['project_id'] != project_id:
            raise PermissionDenied('cross tenant target')
        if not fee or fee['tenant_id'] != user['tenant_id'] or fee['project_id'] != project_id:
            raise PermissionDenied('cross tenant fee')
        rid = self._id()
        row = _reading_dict(rid, user, project_id, target_id, fee_id, period, previous, current, reading_date, status, notes)
        self.meter_readings[rid] = row
        self._log(user, project_id, 'meter.create', 'meter_reading', rid, {'billing_period': period, 'consumption': row['consumption']})
        if row['status'] == 'confirmed':
            result = self.confirm_meter_reading(user, project_id, rid)
            return result
        return row

    def list_meter_readings(self, user, project_id, period=None, status=None):
        self._require(user, 'read')
        if not self._same_tenant_project(user, project_id):
            return []
        rows = [r for r in self.meter_readings.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == project_id]
        if period:
            rows = [r for r in rows if r['billing_period'] == period]
        if status:
            rows = [r for r in rows if r['status'] == status]
        return sorted([_decorate(self, r) for r in rows], key=lambda r: r['id'])

    def confirm_meter_reading(self, user, project_id, reading_id):
        self._require(user, 'write')
        row = self.meter_readings.get(int(reading_id))
        if not row or row['tenant_id'] != user['tenant_id'] or row['project_id'] != project_id:
            raise PermissionDenied('cross tenant reading')
        row['status'] = 'confirmed'
        fee = self.fees[row['fee_type_id']]
        amount = round(float(row['consumption']) * float(fee.get('unit_price') or 0), 2)
        existing = next((b for b in self.bills.values() if b.get('tenant_id') == user['tenant_id'] and b.get('project_id') == project_id and b.get('charge_target_id') == row['charge_target_id'] and b.get('fee_type_id') == row['fee_type_id'] and b.get('billing_period') == row['billing_period']), None)
        if existing:
            existing['amount'] = amount
            bill = existing
        else:
            bid = self._id()
            bill = {'id': bid, 'tenant_id': user['tenant_id'], 'project_id': project_id, 'charge_target_id': row['charge_target_id'], 'fee_type_id': row['fee_type_id'], 'bill_number': f"METER-{bid:06d}", 'billing_period': row['billing_period'], 'service_start': f"{row['billing_period']}-01", 'service_end': row.get('reading_date'), 'amount': amount, 'status': 'pending_review'}
            self.bills[bid] = bill
        row['bill_id'] = bill['id']
        self._log(user, project_id, 'meter.confirm', 'meter_reading', reading_id, {'bill_id': bill['id'], 'amount': amount})
        return {**_decorate(self, row), 'bill': bill}

    cls.meter_readings = {}
    cls.create_meter_reading = create_meter_reading
    cls.list_meter_readings = list_meter_readings
    cls.confirm_meter_reading = confirm_meter_reading


def _decorate(service, row):
    target = service.targets.get(row.get('charge_target_id'), {})
    fee = service.fees.get(row.get('fee_type_id'), {})
    return {**row, 'building': target.get('building', ''), 'unit': target.get('unit', ''), 'room_number': target.get('room_number', ''), 'shop_name': target.get('shop_name', ''), 'tenant_name': target.get('tenant_name', ''), 'fee_name': fee.get('name', ''), 'unit_price': fee.get('unit_price', 0)}
