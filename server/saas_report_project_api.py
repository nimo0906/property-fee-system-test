#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Project summary report API routes."""

from server.saas_csv_export import csv_content, project_summary_export_rows
from server.saas_repository import TenantScopeError
from server.saas_service import PermissionDenied


def _percent(numerator, denominator):
    if not denominator:
        return "0.00%"
    return f"{(float(numerator or 0) / float(denominator) * 100):.2f}%"


def project_summary_for_service(service, user, period):
    items = []
    projects = [p for p in service.projects.values() if p.get("tenant_id") == user["tenant_id"]]
    for project in sorted(projects, key=lambda p: p["id"]):
        summary = service.report(user, project["id"], period)
        due = float(summary.get("bill_amount_total") or 0)
        paid = float(summary.get("payment_amount_total") or 0)
        unpaid = float(summary.get("unpaid_amount_total") or 0)
        items.append({
            "name": project.get("name", ""),
            "bill_count": int(summary.get("bill_count") or 0),
            "bill_amount_total": round(due, 2),
            "payment_amount_total": round(paid, 2),
            "unpaid_amount_total": round(unpaid, 2),
            "collection_rate": _percent(paid, due),
            "arrears_rate": _percent(unpaid, due),
        })
    return items


def register_report_project_routes(app, service, repository, current_user):
    from fastapi import Depends, HTTPException

    @app.get("/api/exports/reports/projects.csv")
    def export_report_projects(period: str, user=Depends(current_user)):
        try:
            items = repository.report_projects(user["tenant_id"], period) if repository else project_summary_for_service(service, user, period)
            headers, rows = project_summary_export_rows(items)
            return {"filename": f"report-projects-{period or 'all'}.csv", "content": csv_content(headers, rows)}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/reports/projects")
    def report_projects(period: str, user=Depends(current_user)):
        try:
            items = repository.report_projects(user["tenant_id"], period) if repository else project_summary_for_service(service, user, period)
            return {"items": items}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")
