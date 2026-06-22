#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent license cloud service and admin API for commercial SaaS."""

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
        if int(seats) < 1:
            raise ValueError("seats must be positive")
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

    def list_customers(self):
        return [dict(item) for item in self.customers.values()]

    def list_products(self):
        return [dict(item) for item in self.products.values()]

    def list_entitlements(self):
        return [dict(item) for item in self.entitlements.values()]

    def list_audit_logs(self):
        return [dict(item) for item in self.audit_logs]

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


def create_license_app(service=None, admin_token=""):
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
        from fastapi.responses import HTMLResponse
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for license cloud service") from exc

    app = FastAPI(title="物业收费授权云服务")
    app.state.license_service = service or LicenseCloudService.in_memory()
    app.state.license_admin_token = str(admin_token or "")

    def require_admin_token(x_license_admin_token: str = Header(default="")):
        expected = app.state.license_admin_token
        if expected and not secrets.compare_digest(str(x_license_admin_token or ""), expected):
            raise HTTPException(status_code=401, detail="license_admin_token_required")

    class LicenseCheckIn(BaseModel):
        customer_code: str
        product_code: str

    class LicenseCustomerIn(BaseModel):
        customer_code: str
        name: str
        status: str = "active"

    class LicenseProductIn(BaseModel):
        product_code: str
        name: str
        status: str = "active"

    class LicenseEntitlementIn(BaseModel):
        customer_code: str
        product_code: str
        seats: int = 1
        expires_at: str = ""

    @app.get("/health")
    def health():
        return {"ok": True, "service": "property-license-cloud", "storage": "independent"}

    @app.get("/api/license/boundary")
    def boundary():
        data = build_license_service_boundary()
        return {key: value for key, value in data.items() if key != "business_database_name"}

    @app.post("/api/license/check")
    def check_license(data: LicenseCheckIn):
        return app.state.license_service.check_license(data.customer_code, data.product_code)

    @app.post("/api/license/customers", dependencies=[Depends(require_admin_token)])
    def create_customer(data: LicenseCustomerIn):
        return {"item": app.state.license_service.create_customer(data.customer_code, data.name, data.status)}

    @app.get("/api/license/customers", dependencies=[Depends(require_admin_token)])
    def list_customers():
        return {"items": app.state.license_service.list_customers()}

    @app.post("/api/license/products", dependencies=[Depends(require_admin_token)])
    def create_product(data: LicenseProductIn):
        return {"item": app.state.license_service.create_product(data.product_code, data.name, data.status)}

    @app.get("/api/license/products", dependencies=[Depends(require_admin_token)])
    def list_products():
        return {"items": app.state.license_service.list_products()}

    @app.post("/api/license/entitlements", dependencies=[Depends(require_admin_token)])
    def issue_entitlement(data: LicenseEntitlementIn):
        try:
            item = app.state.license_service.issue_entitlement(data.customer_code, data.product_code, data.seats, data.expires_at)
            return {"item": item}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/license/entitlements", dependencies=[Depends(require_admin_token)])
    def list_entitlements():
        return {"items": app.state.license_service.list_entitlements()}

    @app.get("/api/license/audit-logs", dependencies=[Depends(require_admin_token)])
    def list_audit_logs():
        return {"items": app.state.license_service.list_audit_logs()}

    @app.get("/license-admin", dependencies=[Depends(require_admin_token)])
    def license_admin():
        return HTMLResponse(_render_license_admin(app.state.license_service))

    return app


def _render_license_admin(service):
    customer_rows = "".join(_row(i, ["customer_code", "name", "status"]) for i in service.list_customers())
    product_rows = "".join(_row(i, ["product_code", "name", "status"]) for i in service.list_products())
    entitlement_rows = "".join(_row(i, ["customer_code", "product_code", "seats", "expires_at", "status"]) for i in service.list_entitlements())
    audit_rows = "".join(_row(i, ["customer_code", "product_code", "action"]) for i in service.list_audit_logs())
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>授权云服务后台</title>{_style()}</head>
<body><h1>授权云服务后台</h1><p>独立服务、独立数据库，只管理商业授权，不展示业务库字段或客户上传数据。</p>
<section><h2>客户管理</h2><table><tr><th>客户编号</th><th>客户名称</th><th>状态</th></tr>{customer_rows}</table></section>
<section><h2>产品管理</h2><table><tr><th>产品编号</th><th>产品名称</th><th>状态</th></tr>{product_rows}</table></section>
<section><h2>授权管理</h2><table><tr><th>客户编号</th><th>产品编号</th><th>席位</th><th>到期时间</th><th>状态</th></tr>{entitlement_rows}</table></section>
<section><h2>授权审计</h2><table><tr><th>客户编号</th><th>产品编号</th><th>动作</th></tr>{audit_rows}</table></section></body></html>'''


def _style():
    return '<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:24px;background:#f6f7fb;color:#172033}section{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:14px 0}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #eef0f4;padding:8px;text-align:left}</style>'


def _row(item, keys):
    return "<tr>" + "".join(f"<td>{_h(item.get(key, ''))}</td>" for key in keys) + "</tr>"


def _h(value):
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _is_expired(value):
    if not value:
        return False
    try:
        return date.fromisoformat(str(value)[:10]) < date.today()
    except ValueError:
        return False
