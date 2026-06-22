#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Meter reading repository methods for SaaS module 11."""

from sqlalchemy import text

from server.saas_repository_errors import TenantScopeError
from server.saas_repository_schema import insert_id_sql, inserted_id


def _consumption(previous, current):
    value = round(float(current) - float(previous), 2)
    if value < 0:
        raise ValueError('current reading cannot be lower than previous reading')
    return value


def _meter_select():
    return """SELECT m.id,m.tenant_id,m.project_id,m.charge_target_id,m.fee_type_id,m.billing_period,
        m.previous_reading,m.current_reading,m.consumption,m.reading_date,m.status,m.notes,m.bill_id,
        ct.building,ct.unit,ct.room_number,ct.shop_name,ct.tenant_name,ft.name fee_name,ft.unit_price
        FROM meter_readings m
        JOIN charge_targets ct ON ct.id=m.charge_target_id AND ct.tenant_id=m.tenant_id AND ct.project_id=m.project_id
        JOIN fee_types ft ON ft.id=m.fee_type_id AND ft.tenant_id=m.tenant_id AND ft.project_id=m.project_id"""


def _bill_for_reading(conn, dialect, tenant_id, project_id, row, fee, actor_user_id=None):
    amount = round(float(row['consumption'] or 0) * float(fee['unit_price'] or 0), 2)
    existing = conn.execute(text("""SELECT id,bill_number FROM bills WHERE tenant_id=:tenant_id AND project_id=:project_id
        AND charge_target_id=:target_id AND fee_type_id=:fee_id AND billing_period=:period"""),
        {'tenant_id': tenant_id, 'project_id': project_id, 'target_id': row['charge_target_id'], 'fee_id': row['fee_type_id'], 'period': row['billing_period']}).mappings().first()
    if existing:
        conn.execute(text("UPDATE bills SET amount=:amount WHERE id=:id"), {'amount': amount, 'id': existing['id']})
        bill_id = int(existing['id']); bill_number = existing['bill_number']
    else:
        seq = conn.execute(text("SELECT COALESCE(MAX(id),0)+1 FROM bills")).scalar_one()
        bill_number = f"METER-{tenant_id}-{project_id}-{row['billing_period']}-{row['charge_target_id']}-{row['fee_type_id']}-{int(seq)}"
        result = conn.execute(text(insert_id_sql("""INSERT INTO bills(tenant_id,project_id,charge_target_id,fee_type_id,bill_number,billing_period,service_start,service_end,amount,status)
            VALUES(:tenant_id,:project_id,:target_id,:fee_id,:bill_number,:period,:service_start,:service_end,:amount,'pending_review')""", dialect)),
            {'tenant_id': tenant_id, 'project_id': project_id, 'target_id': row['charge_target_id'], 'fee_id': row['fee_type_id'], 'bill_number': bill_number, 'period': row['billing_period'], 'service_start': f"{row['billing_period']}-01", 'service_end': row.get('reading_date'), 'amount': amount})
        bill_id = inserted_id(result, dialect)
    conn.execute(text("UPDATE meter_readings SET bill_id=:bill_id WHERE id=:id"), {'bill_id': bill_id, 'id': row['id']})
    return {'id': bill_id, 'tenant_id': tenant_id, 'project_id': project_id, 'charge_target_id': row['charge_target_id'], 'fee_type_id': row['fee_type_id'], 'bill_number': bill_number, 'billing_period': row['billing_period'], 'amount': amount, 'status': 'pending_review'}


def attach_meter_repository_methods(cls):
    def create_meter_reading(self, tenant_id, project_id, target_id, fee_id, period, previous, current, reading_date, status='draft', actor_user_id=None, notes=''):
        self._require_project_scope(tenant_id, project_id)
        target = self.get_charge_target(tenant_id, project_id, target_id)
        fee = self.get_fee_type(tenant_id, project_id, fee_id)
        if not target or not fee:
            raise TenantScopeError('meter target or fee does not belong to tenant')
        usage = _consumption(previous, current)
        with self.engine.begin() as conn:
            existing = conn.execute(text("""SELECT id FROM meter_readings WHERE tenant_id=:tenant_id AND project_id=:project_id AND charge_target_id=:target_id AND fee_type_id=:fee_id AND billing_period=:period"""),
                {'tenant_id': tenant_id, 'project_id': project_id, 'target_id': target_id, 'fee_id': fee_id, 'period': period}).mappings().first()
            params = {'tenant_id': tenant_id, 'project_id': project_id, 'target_id': target_id, 'fee_id': fee_id, 'period': period, 'previous': float(previous), 'current': float(current), 'usage': usage, 'reading_date': reading_date, 'status': status or 'draft', 'notes': notes or ''}
            if existing:
                reading_id = int(existing['id'])
                conn.execute(text("""UPDATE meter_readings SET previous_reading=:previous,current_reading=:current,consumption=:usage,reading_date=:reading_date,status=:status,notes=:notes WHERE id=:id"""), {**params, 'id': reading_id})
            else:
                result = conn.execute(text(insert_id_sql("""INSERT INTO meter_readings(tenant_id,project_id,charge_target_id,fee_type_id,billing_period,previous_reading,current_reading,consumption,reading_date,status,notes)
                    VALUES(:tenant_id,:project_id,:target_id,:fee_id,:period,:previous,:current,:usage,:reading_date,:status,:notes)""", self.engine.dialect.name)), params)
                reading_id = inserted_id(result, self.engine.dialect.name)
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'meter.create', 'meter_reading', reading_id, {'billing_period': period, 'consumption': usage})
        row = self.get_meter_reading(tenant_id, project_id, reading_id)
        if status == 'confirmed':
            return self.confirm_meter_reading(tenant_id, project_id, reading_id, actor_user_id)
        return row

    def get_meter_reading(self, tenant_id, project_id, reading_id):
        return self._row(_meter_select() + " WHERE m.tenant_id=:tenant_id AND m.project_id=:project_id AND m.id=:id", {'tenant_id': tenant_id, 'project_id': project_id, 'id': reading_id})

    def list_meter_readings(self, tenant_id, project_id, period=None, status=None):
        self._require_project_scope(tenant_id, project_id)
        sql = _meter_select() + " WHERE m.tenant_id=:tenant_id AND m.project_id=:project_id"
        params = {'tenant_id': tenant_id, 'project_id': project_id}
        if period:
            sql += " AND m.billing_period=:period"; params['period'] = period
        if status:
            sql += " AND m.status=:status"; params['status'] = status
        sql += " ORDER BY m.id"
        with self.engine.begin() as conn:
            return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]

    def confirm_meter_reading(self, tenant_id, project_id, reading_id, actor_user_id=None):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            row = conn.execute(text(_meter_select() + " WHERE m.tenant_id=:tenant_id AND m.project_id=:project_id AND m.id=:id"), {'tenant_id': tenant_id, 'project_id': project_id, 'id': reading_id}).mappings().first()
            if not row:
                raise TenantScopeError('meter reading does not belong to tenant')
            row = dict(row)
            conn.execute(text("UPDATE meter_readings SET status='confirmed' WHERE id=:id"), {'id': reading_id})
            row['status'] = 'confirmed'
            fee = {'unit_price': row['unit_price']}
            bill = _bill_for_reading(conn, self.engine.dialect.name, tenant_id, project_id, row, fee, actor_user_id)
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'meter.confirm', 'meter_reading', reading_id, {'bill_id': bill['id'], 'amount': bill['amount']})
        return {**self.get_meter_reading(tenant_id, project_id, reading_id), 'status': 'confirmed', 'bill': bill}

    cls.create_meter_reading = create_meter_reading
    cls.get_meter_reading = get_meter_reading
    cls.list_meter_readings = list_meter_readings
    cls.confirm_meter_reading = confirm_meter_reading
