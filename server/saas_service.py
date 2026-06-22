#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-memory SaaS backoffice domain service for first cloud slice tests."""

from server.passwords import hash_password
from server.saas_fee_rules import normalize_billing_mode


class PermissionDenied(Exception):
    pass


ROLE_PERMISSIONS = {
    "system_admin": {"read", "write", "manage_users", "backup", "billing", "payment", "import"},
    "platform_admin": {"read", "manage_users", "platform_users"},
    "finance": {"read", "write", "billing", "payment", "import"},
    "cashier": {"read", "payment"},
    "frontdesk": {"read", "write", "import"},
    "executive": {"read"},
}


class SaasBackofficeService:
    @classmethod
    def in_memory(cls):
        return cls()

    def __init__(self):
        self._seq = 1
        self.tenants = {}
        self.projects = {}
        self.users = {}
        self.targets = {}
        self.owners = {}
        self.fees = {}
        self.bills = {}
        self.payments = {}
        self.payment_keys = {}
        self.imports = {}
        self.backup_records = {}
        self.restore_drills = {}
        self.audit_logs = []
        self.meter_readings = {}

    def _id(self):
        value = self._seq
        self._seq += 1
        return value

    def _require(self, user, perm):
        if perm not in ROLE_PERMISSIONS.get(user["role_code"], set()):
            raise PermissionDenied(f"{user['role_code']} lacks {perm}")

    def _same_tenant_project(self, user, project_id):
        project = self.projects.get(project_id)
        return bool(project and project["tenant_id"] == user["tenant_id"])

    def _log(self, user, project_id, action, entity_type=None, entity_id=None, detail=None):
        row = {
            "id": self._id(),
            "tenant_id": user["tenant_id"],
            "project_id": project_id,
            "user_id": user["id"],
            "username": user["username"],
            "tenant_name": user.get("tenant_name", ""),
            "role_code": user["role_code"],
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "detail": detail or {},
        }
        self.audit_logs.append(row)
        return row

    def create_tenant(self, name):
        tid = self._id()
        self.tenants[tid] = {"id": tid, "name": name}
        return tid

    def create_project(self, tenant_id, name):
        pid = self._id()
        self.projects[pid] = {"id": pid, "tenant_id": tenant_id, "name": name}
        return pid

    def _default_project_id(self, tenant_id):
        return next((p["id"] for p in self.projects.values() if p["tenant_id"] == tenant_id), None)

    def _validate_role(self, role_code):
        if role_code not in ROLE_PERMISSIONS:
            raise ValueError("unknown role")

    def create_user(self, tenant_id, username, role_code):
        self._validate_role(role_code)
        uid = self._id()
        user = {
            "id": uid,
            "tenant_id": tenant_id,
            "project_id": self._default_project_id(tenant_id),
            "username": username,
            "role_code": role_code,
        }
        self.users[uid] = user
        return user

    def create_staff_user(self, user, project_id, username, role_code):
        self._require(user, "manage_users")
        self._validate_role(role_code)
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        new_user = self.create_user(user["tenant_id"], username, role_code)
        new_user["project_id"] = project_id
        self._log(user, project_id, 'user.create', 'user', new_user['id'], {'username': username, 'role_code': role_code})
        return new_user


    def list_staff_users(self, user, project_id):
        self._require(user, "manage_users")
        if not self._same_tenant_project(user, project_id):
            return []
        return [
            {k: v for k, v in row.items() if k != 'password_hash'}
            for row in self.users.values()
            if user['role_code'] == 'platform_admin' or row['tenant_id'] == user['tenant_id']
        ]

    def set_user_active(self, user, project_id, target_user_id, is_active):
        self._require(user, "manage_users")
        target = self.users[target_user_id]
        cross_tenant = target['tenant_id'] != user['tenant_id']
        if (cross_tenant and user.get('role_code') != 'platform_admin') or (not cross_tenant and not self._same_tenant_project(user, project_id)):
            raise PermissionDenied("cross tenant user")
        active_value = 1 if is_active else 0
        target['is_active'] = active_value
        action = 'user.enable' if is_active else 'user.disable'
        target_project_id = target.get('project_id') or self._default_project_id(target['tenant_id']) or project_id
        detail = {
            'target_user_id': target_user_id,
            'target_username': target.get('username'),
            'target_role_code': target.get('role_code'),
            'new_is_active': bool(is_active),
        }
        if cross_tenant:
            detail.update({'scope': 'platform', 'actor_username': user.get('username'), 'actor_tenant_id': user.get('tenant_id')})
        self._log(user if not cross_tenant else target, target_project_id, action, 'user', target_user_id, detail)
        return {'user_id': target_user_id, 'is_active': active_value}

    def create_fee_type(self, user, project_id, name, unit_price, billing_mode="area"):
        self._require(user, "write")
        if not self._same_tenant_project(user, project_id):
            raise PermissionDenied("cross tenant project")
        fid = self._id()
        fee = {"id": fid, "tenant_id": user["tenant_id"], "project_id": project_id,
               "name": name, "unit_price": float(unit_price), "billing_mode": normalize_billing_mode(billing_mode)}
        self.fees[fid] = fee
        self._log(user, project_id, 'fee_type.create', 'fee_type', fid, {'name': name, 'unit_price': float(unit_price), 'billing_mode': fee['billing_mode']})
        return fee

    def list_audit_logs(self, user, project_id):
        self._require(user, 'read')
        if not self._same_tenant_project(user, project_id):
            return []
        return [row for row in self.audit_logs if row['tenant_id'] == user['tenant_id'] and row['project_id'] == project_id]

    def create_backup_marker(self, user, project_id):
        if user['role_code'] != 'system_admin':
            raise PermissionDenied('backup requires admin')
        backup_id = f"backup-{self._id():06d}"
        record = {
            'backup_id': backup_id,
            'tenant_id': user['tenant_id'],
            'project_id': project_id,
            'status': 'created',
            'created_at': backup_id.replace('backup-', ''),
        }
        self.backup_records[backup_id] = record
        self._log(user, project_id, 'backup.create', 'backup', None, {'kind': 'manual', 'backup_id': backup_id})
        return {'backup_id': backup_id}

    def list_backup_records(self, user, project_id):
        if user['role_code'] != 'system_admin':
            raise PermissionDenied('backup requires admin')
        if not self._same_tenant_project(user, project_id):
            return []
        return [r for r in self.backup_records.values() if r['tenant_id'] == user['tenant_id'] and r['project_id'] == project_id]

    def record_restore_drill(self, user, project_id, backup_id, scope):
        if user['role_code'] != 'system_admin':
            raise PermissionDenied('restore drill requires admin')
        if scope not in {'database', 'tenant-files', 'system-files'}:
            raise ValueError('invalid restore drill scope')
        drill_id = f"restore-drill-{self._id():06d}"
        drill = {'id': drill_id, 'tenant_id': user['tenant_id'], 'project_id': project_id, 'backup_id': backup_id, 'scope': scope, 'status': 'recorded'}
        self.restore_drills[drill_id] = drill
        self._log(user, project_id, 'restore.drill', 'restore_drill', None, {'backup_id': backup_id, 'scope': scope})
        return drill

    def reset_user_password(self, user, target_user_id, new_password):
        self._require(user, "manage_users")
        target = self.users[target_user_id]
        cross_tenant = target["tenant_id"] != user["tenant_id"]
        if cross_tenant and user.get('role_code') != 'platform_admin':
            raise PermissionDenied("cross tenant user")
        target['password_hash'] = hash_password(new_password)
        project_id = target.get('project_id') or self._default_project_id(target['tenant_id']) or target['tenant_id']
        detail = {
            'target_user_id': target_user_id,
            'target_username': target.get('username'),
            'target_role_code': target.get('role_code'),
            'password_changed': True,
        }
        if cross_tenant:
            detail.update({'scope': 'platform', 'actor_username': user.get('username'), 'actor_tenant_id': user.get('tenant_id')})
        self._log(user if not cross_tenant else target, project_id, 'user.password_reset', 'user', target_user_id, detail)
        return {'user_id': target_user_id}


from server.saas_billing_service import attach_billing_methods
from server.saas_fee_type_service import attach_fee_type_methods
from server.saas_owner_service import attach_owner_methods
from server.saas_import_mapping import attach_import_mapping_methods
from server.saas_meter_service import attach_meter_methods
from server.saas_contract_service import attach_contract_methods
attach_billing_methods(SaasBackofficeService)
attach_fee_type_methods(SaasBackofficeService)
attach_owner_methods(SaasBackofficeService)
attach_import_mapping_methods(SaasBackofficeService)
attach_meter_methods(SaasBackofficeService)
attach_contract_methods(SaasBackofficeService)
