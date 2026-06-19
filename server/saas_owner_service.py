#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner and charge target methods for in-memory SaaS service."""

from server.saas_service import PermissionDenied


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

    def create_charge_target(self, user, project_id, building, unit, room_number, category, area, owner_id=0, unit_price_override=None):
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
                  "unit_price_override": price_override}
        self.targets[tid] = target
        self._log(user, project_id, 'charge_target.create', 'charge_target', tid, {'building': building, 'room_number': room_number})
        return target

    def list_charge_targets(self, user, project_id):
        self._require(user, "read")
        if not self._same_tenant_project(user, project_id):
            return []
        return [t for t in self.targets.values() if t["tenant_id"] == user["tenant_id"] and t["project_id"] == project_id]

    cls.create_owner = create_owner
    cls.list_owners = list_owners
    cls.create_charge_target = create_charge_target
    cls.list_charge_targets = list_charge_targets
