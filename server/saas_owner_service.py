#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner and charge target methods for in-memory SaaS service."""

from server.saas_service import PermissionDenied

TARGET_EXTRA_FIELDS = ("floor", "shop_name", "tenant_name", "tenant_phone", "payment_cycle", "notes")


def _target_extras(kwargs):
    return {key: kwargs.get(key, "" if key != "floor" else None) for key in TARGET_EXTRA_FIELDS}


def attach_owner_methods(cls):
    def create_owner(self, user, project_id, name, phone="", owner_type="业主"):
        self._require(user, "write")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        oid = self._id()
        owner = {"id": oid, "tenant_id": user["tenant_id"], "project_id": project_id, "name": name, "phone": phone, "owner_type": owner_type}
        self.owners[oid] = owner
        self._log(user, project_id, "owner.create", "owner", oid, {"name": name, "phone": phone, "owner_type": owner_type})
        return owner

    def list_owners(self, user, project_id):
        self._require(user, "read")
        if not self._same_tenant_project(user, project_id):
            return []
        return [o for o in self.owners.values() if o["tenant_id"] == user["tenant_id"] and o["project_id"] == project_id]

    def create_charge_target(self, user, project_id, building, unit, room_number, category, area, owner_id=0, unit_price_override=None, **kwargs):
        self._require(user, "write")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        owner_id = int(owner_id or 0)
        owner = self.owners.get(owner_id) if owner_id else None
        if owner_id and (not owner or owner["tenant_id"] != user["tenant_id"] or owner["project_id"] != project_id):
            raise PermissionDenied("cross tenant owner")
        tid = self._id()
        price_override = float(unit_price_override) if unit_price_override not in (None, "") else None
        target = {"id": tid, "tenant_id": user["tenant_id"], "project_id": project_id,
                  "owner_id": owner_id or None, "owner_name": owner.get("name") if owner else "", "owner_phone": owner.get("phone") if owner else "",
                  "building": building, "unit": unit, "room_number": room_number, "category": category, "area": float(area),
                  "unit_price_override": price_override, **_target_extras(kwargs)}
        self.targets[tid] = target
        self._log(user, project_id, 'charge_target.create', 'charge_target', tid, {'building': building, 'room_number': room_number})
        return target


    def batch_update_charge_targets(self, user, project_id, filters, updates):
        self._require(user, "write")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        changes = {key: value for key, value in (updates or {}).items() if key in {"category", "payment_cycle", "unit_price_override"}}
        if not changes:
            return 0
        count = 0
        for target in self.targets.values():
            if target["tenant_id"] != user["tenant_id"] or target["project_id"] != project_id:
                continue
            if filters.get("building") and filters["building"].lower() not in str(target.get("building", "")).lower():
                continue
            if filters.get("unit") and filters["unit"].lower() not in str(target.get("unit", "")).lower():
                continue
            if filters.get("room_number") and filters["room_number"].lower() not in str(target.get("room_number", "")).lower():
                continue
            if filters.get("category") and target.get("category") != filters["category"]:
                continue
            target.update(changes)
            count += 1
        self._log(user, project_id, "charge_target.batch_update", "charge_target", 0, {"count": count, "filters": filters, "updates": changes})
        return count

    def list_charge_targets(self, user, project_id):
        self._require(user, "read")
        if not self._same_tenant_project(user, project_id):
            return []
        return [t for t in self.targets.values() if t["tenant_id"] == user["tenant_id"] and t["project_id"] == project_id]

    cls.create_owner = create_owner
    cls.list_owners = list_owners
    cls.create_charge_target = create_charge_target
    cls.batch_update_charge_targets = batch_update_charge_targets
    cls.list_charge_targets = list_charge_targets
