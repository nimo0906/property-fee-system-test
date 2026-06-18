#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI billing routes for SaaS backoffice."""

from server.saas_service import PermissionDenied


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

    current_user = app.state.current_user

    @app.post("/api/bills/generate")
    def generate_bill(data: BillGenerateIn, user=Depends(current_user)):
        try:
            service._require(user, "billing")
            target = service.targets[data.target_id]
            fee = service.fees[data.fee_type_id]
            item = service.generate_bill(user, user["project_id"], target, fee, data.billing_period, data.service_start, data.service_end)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/bills/search")
    def search_bills(keyword: str = "", period: str = "", status: str = "", page: int = 1, page_size: int = 20, user=Depends(current_user)):
        try:
            return service.search_bills(user, user["project_id"], keyword, period or None, status or None, page, page_size)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/bills")
    def list_bills(period: str = "", status: str = "", user=Depends(current_user)):
        try:
            return {"items": service.list_bills(user, user["project_id"], period or None, status or None)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/bills/{bill_id}/approve")
    def approve_bill(bill_id: int, user=Depends(current_user)):
        try:
            return {"item": service.approve_bill(user, user["project_id"], bill_id)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/payments")
    def search_payments(keyword: str = "", period: str = "", page: int = 1, page_size: int = 20, user=Depends(current_user)):
        try:
            return service.search_payments(user, user["project_id"], keyword, period or None, page, page_size)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/payments")
    def record_payment(data: PaymentIn, user=Depends(current_user)):
        try:
            return {"item": service.record_payment(user, data.bill_id, data.amount, data.method, data.idempotency_key or None)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/exports/bills")
    def export_bills(period: str = "", status: str = "", user=Depends(current_user)):
        try:
            return service.export_bills(user, user["project_id"], period or None, status or None)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/exports/payments")
    def export_payments(period: str = "", user=Depends(current_user)):
        try:
            return service.export_payments(user, user["project_id"], period or None)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/reports/summary")
    def report_summary(period: str, user=Depends(current_user)):
        return service.report(user, user["project_id"], period)
