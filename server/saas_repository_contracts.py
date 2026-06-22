#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract repository methods for SaaS module 13."""

from datetime import date
from sqlalchemy import text

from server.saas_repository_errors import TenantScopeError
from server.saas_repository_schema import insert_id_sql, inserted_id


def _monthly(area, rate):
    return round(float(area or 0) * float(rate or 0), 2)


def _check_period(contract, service_start, service_end):
    if date.fromisoformat(service_start) < date.fromisoformat(str(contract['start_date'])) or date.fromisoformat(service_end) > date.fromisoformat(str(contract['end_date'])):
        raise ValueError('outside contract period')


def _contract_select():
    return """SELECT c.id,c.tenant_id,c.project_id,c.charge_target_id,c.contract_no,c.merchant_name,c.shop_name,
        c.start_date,c.end_date,c.contract_area,c.rent_unit_price,c.property_rate,c.rent_cycle,c.property_cycle,
        c.deposit_amount,c.status,c.notes,ct.building,ct.unit,ct.room_number space_no
        FROM merchant_contracts c JOIN charge_targets ct ON ct.id=c.charge_target_id AND ct.tenant_id=c.tenant_id AND ct.project_id=c.project_id"""


def _decorate(row):
    item = dict(row)
    item['monthly_rent_amount'] = _monthly(item.get('contract_area'), item.get('rent_unit_price'))
    item['monthly_property_fee_amount'] = _monthly(item.get('contract_area'), item.get('property_rate'))
    return item


def attach_contract_repository_methods(cls):
    def create_merchant_contract(self, tenant_id, project_id, target_id, contract_no, merchant_name, shop_name, start_date, end_date, contract_area, rent_unit_price, property_rate, rent_cycle='monthly', property_cycle='monthly', deposit_amount=0, status='active', actor_user_id=None, notes=''):
        self._require_project_scope(tenant_id, project_id)
        target = self.get_charge_target(tenant_id, project_id, target_id)
        if not target:
            raise TenantScopeError('contract target does not belong to tenant')
        if date.fromisoformat(end_date) < date.fromisoformat(start_date):
            raise ValueError('contract end before start')
        with self.engine.begin() as conn:
            result = conn.execute(text(insert_id_sql("""INSERT INTO merchant_contracts(tenant_id,project_id,charge_target_id,contract_no,merchant_name,shop_name,start_date,end_date,contract_area,rent_unit_price,property_rate,rent_cycle,property_cycle,deposit_amount,status,notes)
                VALUES(:tenant_id,:project_id,:target_id,:contract_no,:merchant_name,:shop_name,:start_date,:end_date,:area,:rent,:property_rate,:rent_cycle,:property_cycle,:deposit,:status,:notes)""", self.engine.dialect.name)),
                {'tenant_id': tenant_id, 'project_id': project_id, 'target_id': target_id, 'contract_no': contract_no, 'merchant_name': merchant_name, 'shop_name': shop_name, 'start_date': start_date, 'end_date': end_date, 'area': float(contract_area), 'rent': float(rent_unit_price), 'property_rate': float(property_rate), 'rent_cycle': rent_cycle or 'monthly', 'property_cycle': property_cycle or 'monthly', 'deposit': float(deposit_amount or 0), 'status': status or 'active', 'notes': notes or ''})
            contract_id = inserted_id(result, self.engine.dialect.name)
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'merchant_contract.create', 'merchant_contract', contract_id, {'contract_no': contract_no})
        return self.get_merchant_contract(tenant_id, project_id, contract_id)

    def get_merchant_contract(self, tenant_id, project_id, contract_id):
        row = self._row(_contract_select() + " WHERE c.tenant_id=:tenant_id AND c.project_id=:project_id AND c.id=:id", {'tenant_id': tenant_id, 'project_id': project_id, 'id': contract_id})
        return _decorate(row) if row else None

    def list_merchant_contracts(self, tenant_id, project_id):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            rows = conn.execute(text(_contract_select() + " WHERE c.tenant_id=:tenant_id AND c.project_id=:project_id ORDER BY c.id"), {'tenant_id': tenant_id, 'project_id': project_id}).mappings().all()
            return [_decorate(r) for r in rows]

    def create_contract_amendment(self, tenant_id, project_id, contract_id, amendment_no, effective_date, rent_unit_price=None, property_rate=None, contract_area=None, status='confirmed', actor_user_id=None, notes=''):
        self._require_project_scope(tenant_id, project_id)
        contract = self.get_merchant_contract(tenant_id, project_id, contract_id)
        if not contract:
            raise TenantScopeError('contract does not belong to tenant')
        with self.engine.begin() as conn:
            result = conn.execute(text(insert_id_sql("""INSERT INTO contract_amendments(tenant_id,project_id,contract_id,amendment_no,effective_date,rent_unit_price,property_rate,contract_area,status,notes)
                VALUES(:tenant_id,:project_id,:contract_id,:amendment_no,:effective_date,:rent,:property_rate,:area,:status,:notes)""", self.engine.dialect.name)),
                {'tenant_id': tenant_id, 'project_id': project_id, 'contract_id': contract_id, 'amendment_no': amendment_no, 'effective_date': effective_date, 'rent': rent_unit_price, 'property_rate': property_rate, 'area': contract_area, 'status': status or 'confirmed', 'notes': notes or ''})
            amendment_id = inserted_id(result, self.engine.dialect.name)
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'contract_amendment.confirm', 'contract_amendment', amendment_id, {'contract_id': contract_id, 'effective_date': effective_date})
        return self.get_contract_amendment(tenant_id, project_id, amendment_id)

    def get_contract_amendment(self, tenant_id, project_id, amendment_id):
        return self._row("SELECT id,tenant_id,project_id,contract_id,amendment_no,effective_date,rent_unit_price,property_rate,contract_area,status,notes FROM contract_amendments WHERE tenant_id=:tenant_id AND project_id=:project_id AND id=:id", {'tenant_id': tenant_id, 'project_id': project_id, 'id': amendment_id})

    def list_contract_amendments(self, tenant_id, project_id, contract_id):
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT id,tenant_id,project_id,contract_id,amendment_no,effective_date,rent_unit_price,property_rate,contract_area,status,notes FROM contract_amendments WHERE tenant_id=:tenant_id AND project_id=:project_id AND contract_id=:contract_id ORDER BY effective_date,id"), {'tenant_id': tenant_id, 'project_id': project_id, 'contract_id': contract_id}).mappings().all()
            return [dict(r) for r in rows]

    def _contract_effective_values(self, tenant_id, project_id, contract, service_start):
        effective = dict(contract)
        for amendment in self.list_contract_amendments(tenant_id, project_id, contract['id']):
            if amendment.get('status') == 'confirmed' and str(amendment.get('effective_date') or '') <= str(service_start):
                for key in ['rent_unit_price', 'property_rate', 'contract_area']:
                    if amendment.get(key) not in (None, ''):
                        effective[key] = amendment[key]
        return effective

    def generate_contract_bill(self, tenant_id, project_id, contract_id, period, service_start, service_end, actor_user_id=None):
        self._require_project_scope(tenant_id, project_id)
        contract = self.get_merchant_contract(tenant_id, project_id, contract_id)
        if not contract:
            raise TenantScopeError('contract does not belong to tenant')
        _check_period(contract, service_start, service_end)
        effective = self._contract_effective_values(tenant_id, project_id, contract, service_start)
        amount = round(_monthly(effective['contract_area'], effective['rent_unit_price']) + _monthly(effective['contract_area'], effective['property_rate']), 2)
        with self.engine.begin() as conn:
            existing = conn.execute(text("SELECT id,bill_number FROM bills WHERE tenant_id=:tenant_id AND project_id=:project_id AND source='merchant_contract' AND source_ref=:ref AND billing_period=:period"), {'tenant_id': tenant_id, 'project_id': project_id, 'ref': str(contract_id), 'period': period}).mappings().first()
            if existing:
                conn.execute(text("UPDATE bills SET amount=:amount WHERE id=:id"), {'amount': amount, 'id': existing['id']})
                bill_id = int(existing['id']); bill_number = existing['bill_number']
            else:
                seq = conn.execute(text("SELECT COALESCE(MAX(id),0)+1 FROM bills")).scalar_one()
                bill_number = f"CONTRACT-{tenant_id}-{project_id}-{period}-{contract_id}-{int(seq)}"
                result = conn.execute(text(insert_id_sql("""INSERT INTO bills(tenant_id,project_id,charge_target_id,fee_type_id,bill_number,billing_period,service_start,service_end,amount,status,source,source_ref)
                    VALUES(:tenant_id,:project_id,:target_id,0,:bill_number,:period,:service_start,:service_end,:amount,'pending_review','merchant_contract',:ref)""", self.engine.dialect.name)),
                    {'tenant_id': tenant_id, 'project_id': project_id, 'target_id': contract['charge_target_id'], 'bill_number': bill_number, 'period': period, 'service_start': service_start, 'service_end': service_end, 'amount': amount, 'ref': str(contract_id)})
                bill_id = inserted_id(result, self.engine.dialect.name)
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'merchant_contract.bill_generate', 'bill', bill_id, {'contract_id': contract_id, 'amount': amount})
        return {'id': bill_id, 'tenant_id': tenant_id, 'project_id': project_id, 'charge_target_id': contract['charge_target_id'], 'fee_type_id': 0, 'bill_number': bill_number, 'billing_period': period, 'service_start': service_start, 'service_end': service_end, 'amount': amount, 'status': 'pending_review', 'source': 'merchant_contract', 'source_ref': str(contract_id), 'contract_id': contract_id}

    cls.create_merchant_contract = create_merchant_contract
    cls.get_merchant_contract = get_merchant_contract
    cls.list_merchant_contracts = list_merchant_contracts
    cls.create_contract_amendment = create_contract_amendment
    cls.get_contract_amendment = get_contract_amendment
    cls.list_contract_amendments = list_contract_amendments
    cls._contract_effective_values = _contract_effective_values
    cls.generate_contract_bill = generate_contract_bill
