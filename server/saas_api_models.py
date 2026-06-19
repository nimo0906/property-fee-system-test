#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pydantic request models for SaaS FastAPI routes."""

from pydantic import BaseModel


class LoginIn(BaseModel):
    tenant_name: str
    project_name: str
    username: str
    role_code: str
    password: str = ""


class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str


class ProjectSwitchIn(BaseModel):
    project_id: int


class FeeIn(BaseModel):
    name: str
    unit_price: float


class OwnerIn(BaseModel):
    name: str
    phone: str = ""
    owner_type: str = "业主"


class TargetIn(BaseModel):
    owner_id: int = 0
    building: str
    unit: str = ""
    room_number: str
    category: str = "居民"
    area: float


class ImportPreviewIn(BaseModel):
    rows: list


class ImportConfirmIn(BaseModel):
    import_id: int


class ImportFileRegisterIn(BaseModel):
    import_type: str
    original_name: str
    file_size: int
    content_type: str = ""


class UserCreateIn(BaseModel):
    username: str
    role_code: str


class PasswordResetIn(BaseModel):
    new_password: str


class RestoreDrillIn(BaseModel):
    backup_id: str
    scope: str


class UserActiveIn(BaseModel):
    is_active: bool
