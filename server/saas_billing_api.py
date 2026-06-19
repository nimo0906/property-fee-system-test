#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI billing routes for SaaS backoffice."""

from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied
from server.saas_fee_rules import calculate_bill_amount
from server.saas_csv_export import bill_export_rows, csv_content, payment_export_rows


def register_billing_routes(app, service):
    from fastapi import Depends, HTTPException
    from pydantic import BaseModel

    class BillGenerateIn(BaseModel):
        target_id: int
        fee_type_id: int
        billing_period: str
        service_start: str
        service_end: str

    class PaymentIn(BaseModel):
        bill_id: int
        amount: float
        method: str = ""
        idempotency_key: str = ""

    class BatchBillGenerateIn(BaseModel):
        fee_type_id: int
        billing_period: str
        service_start: str
        service_end: str
        category: str = ""
        building: str = ""
        unit: str = ""

    current_user = app.state.current_user
    repository = getattr(app.state, "repository", None)

    @app.post("/api/bills/generate")
    def generate_bill(data: BillGenerateIn, user=Depends(current_user)):
        try:
            service._require(user, "billing")
            if repository:
                target = repository.get_charge_target(user["tenant_id"], user["project_id"], data.target_id)
                fee = repository.get_fee_type(user["tenant_id"], user["project_id"], data.fee_type_id)
                if not target or not fee:
                    raise HTTPException(status_code=404, detail="target or fee type not found")
                item = repository.create_bill(
                    user["tenant_id"], user["project_id"], target["id"], fee["id"],
                    data.billing_period, data.service_start, data.service_end,
                    calculate_bill_amount(target, fee, data.service_start, data.service_end),
                    actor_user_id=user["id"],
                )
            else:
                target = service.targets[data.target_id]
                fee = service.fees[data.fee_type_id]
                item = service.generate_bill(user, user["project_id"], target, fee, data.billing_period, data.service_start, data.service_end)
            return {"item": item}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")


    @app.post("/api/bills/batch-generate")
    def batch_generate_bills(data: BatchBillGenerateIn, user=Depends(current_user)):
        try:
            service._require(user, "billing")
            if repository:
                result = repository.batch_generate_bills(
                    user["tenant_id"], user["project_id"], data.fee_type_id,
                    data.billing_period, data.service_start, data.service_end, data.category, data.building, data.unit, actor_user_id=user["id"],
                )
            else:
                result = service.batch_generate_bills(
                    user, user["project_id"], data.fee_type_id, data.billing_period, data.service_start, data.service_end, data.category, data.building, data.unit
                )
            return result
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/bills/search")
    def search_bills(keyword: str = "", period: str = "", status: str = "", page: int = 1, page_size: int = 20, user=Depends(current_user)):
        try:
            if repository:
                return repository.search_bills(user["tenant_id"], user["project_id"], keyword, period or None, status or None, page, page_size)
            return service.search_bills(user, user["project_id"], keyword, period or None, status or None, page, page_size)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/bills")
    def list_bills(period: str = "", status: str = "", user=Depends(current_user)):
        try:
            if repository:
                return {"items": repository.list_bills(user["tenant_id"], user["project_id"], period or None, status or None)}
            return {"items": service.list_bills(user, user["project_id"], period or None, status or None)}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/bills/{bill_id}/approve")
    def approve_bill(bill_id: int, user=Depends(current_user)):
        try:
            if repository:
                item = repository.approve_bill(user["tenant_id"], user["project_id"], bill_id, actor_user_id=user["id"])
            else:
                item = service.approve_bill(user, user["project_id"], bill_id)
            return {"item": item}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/payments")
    def search_payments(keyword: str = "", period: str = "", page: int = 1, page_size: int = 20, user=Depends(current_user)):
        try:
            if repository:
                return repository.search_payments(user["tenant_id"], user["project_id"], keyword, period or None, page, page_size)
            return service.search_payments(user, user["project_id"], keyword, period or None, page, page_size)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/payments")
    def record_payment(data: PaymentIn, user=Depends(current_user)):
        try:
            if repository:
                item = repository.create_payment(user["tenant_id"], user["project_id"], data.bill_id, data.amount, data.method, data.idempotency_key or None, actor_user_id=user["id"])
            else:
                item = service.record_payment(user, data.bill_id, data.amount, data.method, data.idempotency_key or None)
            return {"item": item}
        except TenantScopeError:
            raise HTTPException(status_code=403, detail="forbidden")
        except PermissionDenied as exc:
            detail = str(exc)
            if "remaining arrears" in detail or "positive" in detail:
                raise HTTPException(status_code=400, detail=detail)
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/exports/bills")
    def export_bills(period: str = "", status: str = "", user=Depends(current_user)):
        try:
            if repository:
                result = repository.search_bills(user["tenant_id"], user["project_id"], "", period or None, status or None, 1, 10000)
                headers, rows = bill_export_rows(result["items"])
                content = csv_content(headers, rows)
                return {"filename": f"bills-{period or 'all'}.csv", "content": content}
            return service.export_bills(user, user["project_id"], period or None, status or None)
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/exports/payments")
    def export_payments(period: str = "", target_id: str = "", user=Depends(current_user)):
        try:
            if repository:
                result = repository.search_payments(user["tenant_id"], user["project_id"], "", period or None, 1, 10000)
                items = result["items"]
                if str(target_id or '').strip():
                    bill_ids = {int(bill.get('id')) for bill in repository.list_bills(user["tenant_id"], user["project_id"]) if int(bill.get('charge_target_id') or 0) == int(target_id)}
                    items = [item for item in items if int(item.get('bill_id') or 0) in bill_ids]
                headers, rows = payment_export_rows(items)
                content = csv_content(headers, rows)
                return {"filename": f"payments-{period or 'all'}.csv", "content": content}
            result = service.export_payments(user, user["project_id"], period or None)
            if str(target_id or '').strip():
                bill_ids = {int(bill.get('id')) for bill in service.list_bills(user, user["project_id"]) if int(bill.get('charge_target_id') or 0) == int(target_id)}
                payments = service.search_payments(user, user["project_id"], "", period or None, 1, 10000)["items"]
                headers, rows = payment_export_rows([item for item in payments if int(item.get('bill_id') or 0) in bill_ids])
                result = {"filename": f"payments-{period or 'all'}.csv", "content": csv_content(headers, rows)}
            return result
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/reports/summary")
    def report_summary(period: str, user=Depends(current_user)):
        if repository:
            return repository.report_summary(user["tenant_id"], user["project_id"], period)
        return service.report(user, user["project_id"], period)

    @app.get("/api/reports/breakdown")
    def report_breakdown(period: str, user=Depends(current_user)):
        try:
            if repository:
                return repository.report_breakdown(user["tenant_id"], user["project_id"], period)
            return {"by_building": [], "by_fee_type": []}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")
