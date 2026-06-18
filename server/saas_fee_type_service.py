#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee type list helper for SaaS in-memory service."""


def _list_fee_types(self, user, project_id):
    self._require(user, 'read')
    if not self._same_tenant_project(user, project_id):
        return []
    return [
        item for item in self.fees.values()
        if item['tenant_id'] == user['tenant_id'] and item['project_id'] == project_id
    ]


def attach_fee_type_methods(cls):
    cls.list_fee_types = _list_fee_types
