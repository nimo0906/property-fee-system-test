#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee rule repository methods."""

from sqlalchemy import text

from server.saas_fee_rules import normalize_billing_mode


def attach_fee_rule_repository_methods(cls):
    def create_fee_type(self, tenant_id, project_id, name, unit_price, billing_mode="area"):
        self._require_project_scope(tenant_id, project_id)
        mode = normalize_billing_mode(billing_mode)
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO fee_types(tenant_id,project_id,name,unit_price,billing_mode) VALUES(:tenant_id,:project_id,:name,:unit_price,:billing_mode)"),
                {"tenant_id": tenant_id, "project_id": project_id, "name": name, "unit_price": float(unit_price), "billing_mode": mode})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "project_id": project_id, "name": name, "unit_price": float(unit_price), "billing_mode": mode}

    def get_fee_type(self, tenant_id, project_id, fee_type_id):
        return self._row("""SELECT id,tenant_id,project_id,name,unit_price,billing_mode FROM fee_types
            WHERE tenant_id=:tenant_id AND project_id=:project_id AND id=:id""", {"tenant_id": tenant_id, "project_id": project_id, "id": fee_type_id})

    def list_fee_types(self, tenant_id, project_id):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            rows = conn.execute(text("""SELECT id,tenant_id,project_id,name,unit_price,billing_mode FROM fee_types
                WHERE tenant_id=:tenant_id AND project_id=:project_id ORDER BY id"""), {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
            return [dict(r) for r in rows]

    cls.create_fee_type = create_fee_type
    cls.get_fee_type = get_fee_type
    cls.list_fee_types = list_fee_types
