#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner and charge target repository methods."""

from sqlalchemy import text
from server.saas_repository_schema import insert_id_sql, inserted_id

from server.saas_repository_errors import TenantScopeError

TARGET_EXTRA_FIELDS = ("floor", "shop_name", "tenant_name", "tenant_phone", "payment_cycle", "notes")


def _target_extras(kwargs):
    return {key: kwargs.get(key, "" if key != "floor" else None) for key in TARGET_EXTRA_FIELDS}


def _target_dict(base, extras):
    return {**base, **{key: extras.get(key) for key in TARGET_EXTRA_FIELDS}}


def _filter_clauses(filters):
    clauses = []
    params = {}
    for key in ("building", "unit", "room_number"):
        value = str((filters or {}).get(key) or "").strip()
        if value:
            clauses.append(f"{key} LIKE :{key}_filter")
            params[f"{key}_filter"] = f"%{value}%"
    category = str((filters or {}).get("category") or "").strip()
    if category:
        clauses.append("category=:category_filter")
        params["category_filter"] = category
    return clauses, params


def attach_owner_repository_methods(cls):
    def create_owner(self, tenant_id, project_id, name, phone="", owner_type="业主"):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            result = conn.execute(text(insert_id_sql("INSERT INTO owners(tenant_id,project_id,name,phone,owner_type) VALUES(:tenant_id,:project_id,:name,:phone,:owner_type)", self.engine.dialect.name)),
                {"tenant_id": tenant_id, "project_id": project_id, "name": name, "phone": phone, "owner_type": owner_type})
            owner_row_id = inserted_id(result, self.engine.dialect.name)
            return {"id": owner_row_id, "tenant_id": tenant_id, "project_id": project_id, "name": name, "phone": phone, "owner_type": owner_type}

    def get_owner(self, tenant_id, project_id, owner_id):
        return self._row("SELECT id,tenant_id,project_id,name,phone,owner_type FROM owners WHERE tenant_id=:tenant_id AND project_id=:project_id AND id=:id", {"tenant_id": tenant_id, "project_id": project_id, "id": owner_id})

    def list_owners(self, tenant_id, project_id):
        self._require_project_scope(tenant_id, project_id)
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT id,tenant_id,project_id,name,phone,owner_type FROM owners WHERE tenant_id=:tenant_id AND project_id=:project_id ORDER BY id"), {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
            return [dict(r) for r in rows]

    def create_charge_target(self, tenant_id, project_id, building, unit, room_number, category, area, owner_id=0, unit_price_override=None, **kwargs):
        self._require_project_scope(tenant_id, project_id)
        owner_id = int(owner_id or 0)
        owner = self.get_owner(tenant_id, project_id, owner_id) if owner_id else None
        if owner_id and not owner:
            raise TenantScopeError("owner does not belong to tenant")
        with self.engine.begin() as conn:
            price_override = float(unit_price_override) if unit_price_override not in (None, "") else None
            extras = _target_extras(kwargs)
            result = conn.execute(text(insert_id_sql("""INSERT INTO charge_targets(tenant_id,project_id,owner_id,building,unit,room_number,category,area,unit_price_override,floor,shop_name,tenant_name,tenant_phone,payment_cycle,notes)
                VALUES(:tenant_id,:project_id,:owner_id,:building,:unit,:room_number,:category,:area,:unit_price_override,:floor,:shop_name,:tenant_name,:tenant_phone,:payment_cycle,:notes)""", self.engine.dialect.name)),
                {"tenant_id": tenant_id, "project_id": project_id, "owner_id": owner_id or None, "building": building, "unit": unit, "room_number": room_number, "category": category, "area": float(area), "unit_price_override": price_override, **extras})
            target_row_id = inserted_id(result, self.engine.dialect.name)
            base = {"id": target_row_id, "tenant_id": tenant_id, "project_id": project_id, "owner_id": owner_id or None, "owner_name": owner.get("name") if owner else "", "owner_phone": owner.get("phone") if owner else "", "building": building, "unit": unit, "room_number": room_number, "category": category, "area": float(area), "unit_price_override": price_override}
            return _target_dict(base, extras)


    def batch_update_charge_targets(self, tenant_id, project_id, filters, updates):
        self._require_project_scope(tenant_id, project_id)
        allowed = {"category", "payment_cycle", "unit_price_override"}
        changes = {key: value for key, value in (updates or {}).items() if key in allowed}
        if not changes:
            return 0
        set_parts = [f"{key}=:{key}" for key in changes]
        clauses, params = _filter_clauses(filters)
        where = "tenant_id=:tenant_id AND project_id=:project_id"
        if clauses:
            where += " AND " + " AND ".join(clauses)
        with self.engine.begin() as conn:
            result = conn.execute(text(f"UPDATE charge_targets SET {', '.join(set_parts)} WHERE {where}"),
                {"tenant_id": tenant_id, "project_id": project_id, **params, **changes})
            return int(result.rowcount or 0)

    def get_charge_target(self, tenant_id, project_id, target_id):
        return self._row("""SELECT ct.id,ct.tenant_id,ct.project_id,ct.owner_id,o.name owner_name,o.phone owner_phone,ct.building,ct.unit,ct.room_number,ct.category,ct.area,ct.unit_price_override,ct.floor,ct.shop_name,ct.tenant_name,ct.tenant_phone,ct.payment_cycle,ct.notes FROM charge_targets ct LEFT JOIN owners o ON ct.owner_id=o.id AND ct.tenant_id=o.tenant_id AND ct.project_id=o.project_id
            WHERE ct.tenant_id=:tenant_id AND ct.project_id=:project_id AND ct.id=:id""", {"tenant_id": tenant_id, "project_id": project_id, "id": target_id})

    def list_charge_targets(self, tenant_id, project_id):
        with self.engine.begin() as conn:
            rows = conn.execute(text("""SELECT ct.id,ct.tenant_id,ct.project_id,ct.owner_id,o.name owner_name,o.phone owner_phone,ct.building,ct.unit,ct.room_number,ct.category,ct.area,ct.unit_price_override,ct.floor,ct.shop_name,ct.tenant_name,ct.tenant_phone,ct.payment_cycle,ct.notes FROM charge_targets ct LEFT JOIN owners o ON ct.owner_id=o.id AND ct.tenant_id=o.tenant_id AND ct.project_id=o.project_id
                WHERE ct.tenant_id=:tenant_id AND ct.project_id=:project_id ORDER BY ct.id"""), {"tenant_id": tenant_id, "project_id": project_id}).mappings().all()
            return [dict(r) for r in rows]

    cls.create_owner = create_owner
    cls.get_owner = get_owner
    cls.list_owners = list_owners
    cls.create_charge_target = create_charge_target
    cls.batch_update_charge_targets = batch_update_charge_targets
    cls.get_charge_target = get_charge_target
    cls.list_charge_targets = list_charge_targets
