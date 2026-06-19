#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch billing repository methods."""

from sqlalchemy import text
from server.saas_repository_schema import insert_id_sql, inserted_id

from server.saas_batch_billing import build_batch_bill_rows


def attach_batch_billing_repository_methods(cls):
    def _bill_exists(self, tenant_id, project_id, bill_number):
        row = self._row(
            "SELECT id FROM bills WHERE tenant_id=:tenant_id AND project_id=:project_id AND bill_number=:bill_number",
            {'tenant_id': tenant_id, 'project_id': project_id, 'bill_number': bill_number},
        )
        return bool(row)

    def batch_generate_bills(self, tenant_id, project_id, fee_type_id, period, service_start, service_end, category='', building='', unit='', actor_user_id=None):
        self._require_project_scope(tenant_id, project_id)
        fee = self.get_fee_type(tenant_id, project_id, fee_type_id)
        targets = self.list_charge_targets(tenant_id, project_id)
        rows = build_batch_bill_rows(targets, fee, tenant_id, project_id, period, service_start, service_end, category, building, unit)
        created = skipped = 0
        created_ids = []
        with self.engine.begin() as conn:
            for row in rows:
                if self._bill_exists(tenant_id, project_id, row['bill_number']):
                    skipped += 1
                    continue
                result = conn.execute(text(insert_id_sql("""INSERT INTO bills(tenant_id,project_id,charge_target_id,fee_type_id,bill_number,billing_period,service_start,service_end,amount,status)
                    VALUES(:tenant_id,:project_id,:target_id,:fee_type_id,:bill_number,:billing_period,:service_start,:service_end,:amount,'pending_review')""", self.engine.dialect.name)), row)
                created += 1
                created_ids.append(inserted_id(result, self.engine.dialect.name))
        if actor_user_id:
            self.create_audit_log(tenant_id, project_id, actor_user_id, 'bill.batch_generate', 'bill', 0, {
                'billing_period': period, 'fee_type_id': fee_type_id, 'category': category, 'building': building, 'unit': unit, 'created_count': created, 'skipped_count': skipped,
            })
        return {'created_count': created, 'skipped_count': skipped, 'bill_ids': created_ids}

    cls._bill_exists = _bill_exists
    cls.batch_generate_bills = batch_generate_bills
