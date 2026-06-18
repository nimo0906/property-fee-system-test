#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Register SaaS HTML backoffice pages."""

from server.saas_acceptance_pages import register_acceptance_pages
from server.saas_audit_log_pages import register_audit_log_pages
from server.saas_backoffice_pages import register_backoffice_pages
from server.saas_backup_pages import register_backup_pages
from server.saas_bill_pages import register_bill_pages
from server.saas_charge_target_pages import register_charge_target_pages
from server.saas_fee_type_pages import register_fee_type_pages
from server.saas_deploy_pages import register_deploy_pages
from server.saas_import_pages import register_import_pages
from server.saas_payment_pages import register_payment_pages
from server.saas_report_pages import register_report_pages
from server.saas_tenant_admin_pages import register_tenant_admin_pages
from server.saas_user_pages import register_user_pages


def register_saas_pages(app, service, repository, current_user, sessions):
    register_backoffice_pages(app, current_user)
    register_tenant_admin_pages(app, service, repository, current_user)
    register_deploy_pages(app, current_user)
    register_acceptance_pages(app, current_user)
    register_user_pages(app, service, repository, current_user, sessions)
    register_charge_target_pages(app, service, repository, current_user)
    register_fee_type_pages(app, service, repository, current_user)
    register_bill_pages(app, service, repository, current_user)
    register_payment_pages(app, service, repository, current_user)
    register_report_pages(app, service, repository, current_user)
    register_import_pages(app, service, repository, current_user)
    register_audit_log_pages(app, service, repository, current_user)
    register_backup_pages(app, service, repository, current_user)
