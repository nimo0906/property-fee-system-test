#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent license cloud service boundary for commercial SaaS."""

from datetime import date
import secrets


LICENSE_DATABASE_NAME = "property_license_cloud"
BUSINESS_DATABASE_NAME = "property_saas"


def build_license_service_schema():
    return """
CREATE TABLE IF NOT EXISTS license_customers (
    id BIGSERIAL PRIMARY KEY,
    customer_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS license_products (
    id BIGSERIAL PRIMARY KEY,
    product_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS license_entitlements (
    id BIGSERIAL PRIMARY KEY,
    entitlement_code TEXT NOT NULL UNIQUE,
    customer_code TEXT NOT NULL REFERENCES license_customers(customer_code),
    product_code TEXT NOT NULL REFERENCES license_products(product_code),
    status TEXT NOT NULL DEFAULT 'active',
    seats INTEGER NOT NULL DEFAULT 1,
    expires_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(customer_code, product_code)
);

CREATE TABLE IF NOT EXISTS license_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    customer_code TEXT,
    product_code TEXT,
    action TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
""".strip()


def build_license_service_boundary():
    return {
        "service": "property-license-cloud",
        "database": LICENSE_DATABASE_NAME,
        "business_database": "not_allowed",
        "business_database_name": BUSINESS_DATABASE_NAME,
        "stores_customer_uploads": False,
        "returns_business_data": False,
        "allowed_result_fields": ["allowed", "status", "customer_code", "product_code", "seats", "expires_at"],
        "tables": ["license_customers", "license_products", "license_entitlements", "license_audit_logs"],
    }


class LicenseCloudService:
    def __init__(self):
        self.customers = {}
        self.products = {}
        self.entitlements = {}
        self.audit_logs = []

    @classmethod
    def in_memory(cls):
        return cls()

    def create_customer(self, customer_code, name, status="active"):
        item = {"customer_code": customer_code, "name": name, "status": status}
        self.customers[customer_code] = item
        self._log(customer_code, "", "customer.create", {"status": status})
        return dict(item)

    def create_product(self, product_code, name, status="active"):
        item = {"product_code": product_code, "name": name, "status": status}
        self.products[product_code] = item
        self._log("", product_code, "product.create", {"status": status})
        return dict(item)

    def issue_entitlement(self, customer_code, product_code, seats=1, expires_at=""):
        self._require_customer_product(customer_code, product_code)
        item = {
            "entitlement_code": "lic-" + secrets.token_hex(8),
            "customer_code": customer_code,
            "product_code": product_code,
            "status": "active",
            "seats": int(seats),
            "expires_at": expires_at,
        }
        self.entitlements[(customer_code, product_code)] = item
        self._log(customer_code, product_code, "entitlement.issue", {"seats": int(seats), "expires_at": expires_at})
        return dict(item)

    def check_license(self, customer_code, product_code):
        entitlement = self.entitlements.get((customer_code, product_code))
        allowed = bool(entitlement) and entitlement["status"] == "active" and not _is_expired(entitlement.get("expires_at"))
        result = {
            "allowed": allowed,
            "status": entitlement["status"] if entitlement else "missing",
            "customer_code": customer_code,
            "product_code": product_code,
            "seats": entitlement.get("seats", 0) if entitlement else 0,
            "expires_at": entitlement.get("expires_at", "") if entitlement else "",
        }
        self._log(customer_code, product_code, "license.check", {"allowed": allowed, "status": result["status"]})
        return result

    def _require_customer_product(self, customer_code, product_code):
        if customer_code not in self.customers:
            raise ValueError("unknown customer")
        if product_code not in self.products:
            raise ValueError("unknown product")

    def _log(self, customer_code, product_code, action, detail):
        self.audit_logs.append({
            "customer_code": customer_code,
            "product_code": product_code,
            "action": action,
            "detail": dict(detail),
        })


def create_license_app(service=None):
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for license cloud service") from exc

    app = FastAPI(title="物业收费授权云服务")
    app.state.license_service = service or LicenseCloudService.in_memory()

    class LicenseCheckIn(BaseModel):
        customer_code: str
        product_code: str

    @app.get("/health")
    def health():
        return {"ok": True, "service": "property-license-cloud", "storage": "independent"}

    @app.get("/api/license/boundary")
    def boundary():
        data = build_license_service_boundary()
        return {key: value for key, value in data.items() if key != "business_database_name"}

    @app.post("/api/license/check")
    def check_license(data: LicenseCheckIn):
        try:
            return app.state.license_service.check_license(data.customer_code, data.product_code)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return app


def _is_expired(value):
    if not value:
        return False
    try:
        return date.fromisoformat(str(value)[:10]) < date.today()
    except ValueError:
        return False
