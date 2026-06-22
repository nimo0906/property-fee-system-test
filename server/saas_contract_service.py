#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-memory SaaS merchant contract methods."""

from datetime import date

from server.saas_service import PermissionDenied


def _monthly(area, rate):
    return round(float(area or 0) * float(rate or 0), 2)


def _period_ok(start, end, service_start, service_end):
    return date.fromisoformat(service_start) >= date.fromisoformat(start) and date.fromisoformat(service_end) <= date.fromisoformat(end)


def _decorated_contract(service, row):
    target = service.targets.get(row.get('charge_target_id'), {})
    return {
        **row,
        'space_no': target.get('room_number', ''),
        'building': target.get('building', ''),
        'unit': target.get('unit', ''),
        'target_shop_name': target.get('shop_name', ''),
        'monthly_rent_amount': _monthly(row.get('contract_area'), row.get('rent_unit_price')),
        'monthly_property_fee_amount': _monthly(row.get('contract_area'), row.get('property_rate')),
    }


def _effective_values(contract, amendments, service_start):
    effective = dict(contract)
    for item in sorted(amendments, key=lambda x: (x.get('effective_date') or '', x.get('id') or 0)):
        if item.get('status') == 'confirmed' and str(item.get('effective_date') or '') <= str(service_start):
            for key in ['rent_unit_price', 'property_rate', 'contract_area']:
                if item.get(key) not in (None, ''):
                    effective[key] = item[key]
    return effective


def attach_contract_methods(cls):
    def create_merchant_contract(self, user, project_id, target_id, contract_no, merchant_name, shop_name, start_date, end_date, area, rent_rate, property_rate, rent_cycle='monthly', property_cycle='monthly', deposit=0, status='active', notes=''):
        self._require(user, 'write')
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied('cross tenant project')
        target = self.targets.get(int(target_id))
        if not target or target['tenant_id'] != user['tenant_id'] or target['project_id'] != project_id:
            raise PermissionDenied('cross tenant target')
        if date.fromisoformat(end_date) < date.fromisoformat(start_date):
            raise ValueError('contract end before start')
        cid = self._id()
        row = {
            'id': cid, 'tenant_id': user['tenant_id'], 'project_id': project_id,
            'charge_target_id': int(target_id), 'contract_no': contract_no,
            'merchant_name': merchant_name, 'shop_name': shop_name,
            'start_date': start_date, 'end_date': end_date, 'contract_area': float(area),
            'rent_unit_price': float(rent_rate), 'property_rate': float(property_rate),
            'rent_cycle': rent_cycle or 'monthly', 'property_cycle': property_cycle or 'monthly',
            'deposit_amount': float(deposit or 0), 'status': status or 'active', 'notes': notes or '',
        }
        self.merchant_contracts[cid] = row
        self._log(user, project_id, 'merchant_contract.create', 'merchant_contract', cid, {'contract_no': contract_no})
        return _decorated_contract(self, row)

    def list_merchant_contracts(self, user, project_id):
        self._require(user, 'read')
        if not self._same_tenant_project(user, project_id):
            return []
        rows = [r for r in self.merchant_contracts.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == project_id]
        return [_decorated_contract(self, r) for r in sorted(rows, key=lambda x: x['id'])]

    def create_contract_amendment(self, user, project_id, contract_id, amendment_no, effective_date, rent_unit_price=None, property_rate=None, contract_area=None, status='confirmed', notes=''):
        self._require(user, 'write')
        contract = self.merchant_contracts.get(int(contract_id))
        if not contract or contract['tenant_id'] != user['tenant_id'] or contract['project_id'] != project_id:
            raise PermissionDenied('cross tenant contract')
        aid = self._id()
        row = {'id': aid, 'tenant_id': user['tenant_id'], 'project_id': project_id, 'contract_id': int(contract_id), 'amendment_no': amendment_no, 'effective_date': effective_date, 'rent_unit_price': rent_unit_price, 'property_rate': property_rate, 'contract_area': contract_area, 'status': status or 'confirmed', 'notes': notes or ''}
        self.contract_amendments[aid] = row
        self._log(user, project_id, 'contract_amendment.confirm', 'contract_amendment', aid, {'contract_id': int(contract_id), 'effective_date': effective_date})
        return row

    def list_contract_amendments(self, user, project_id, contract_id):
        self._require(user, 'read')
        return [r for r in self.contract_amendments.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == project_id and r['contract_id'] == int(contract_id)]

    def generate_contract_bill(self, user, project_id, contract_id, period, service_start, service_end):
        self._require(user, 'billing')
        contract = self.merchant_contracts.get(int(contract_id))
        if not contract or contract['tenant_id'] != user['tenant_id'] or contract['project_id'] != project_id:
            raise PermissionDenied('cross tenant contract')
        if not _period_ok(contract['start_date'], contract['end_date'], service_start, service_end):
            raise ValueError('outside contract period')
        amendments = self.list_contract_amendments(user, project_id, contract_id)
        effective = _effective_values(contract, amendments, service_start)
        rent = _monthly(effective['contract_area'], effective['rent_unit_price'])
        prop = _monthly(effective['contract_area'], effective['property_rate'])
        amount = round(rent + prop, 2)
        existing = next((b for b in self.bills.values() if b.get('source') == 'merchant_contract' and b.get('source_ref') == str(contract_id) and b.get('billing_period') == period and b.get('tenant_id') == user['tenant_id'] and b.get('project_id') == project_id), None)
        if existing:
            existing['amount'] = amount
            bill = existing
        else:
            bid = self._id()
            bill = {'id': bid, 'tenant_id': user['tenant_id'], 'project_id': project_id, 'charge_target_id': contract['charge_target_id'], 'fee_type_id': 0, 'bill_number': f"CONTRACT-{user['tenant_id']}-{project_id}-{period}-{contract_id}", 'billing_period': period, 'service_start': service_start, 'service_end': service_end, 'amount': amount, 'status': 'pending_review', 'source': 'merchant_contract', 'source_ref': str(contract_id), 'contract_id': int(contract_id)}
            self.bills[bid] = bill
        self._log(user, project_id, 'merchant_contract.bill_generate', 'bill', bill['id'], {'contract_id': int(contract_id), 'amount': amount})
        return bill

    cls.merchant_contracts = {}
    cls.contract_amendments = {}
    cls.create_merchant_contract = create_merchant_contract
    cls.list_merchant_contracts = list_merchant_contracts
    cls.create_contract_amendment = create_contract_amendment
    cls.list_contract_amendments = list_contract_amendments
    cls.generate_contract_bill = generate_contract_bill
