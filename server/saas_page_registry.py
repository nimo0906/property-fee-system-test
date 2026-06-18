#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Register SaaS HTML backoffice pages."""

from server.saas_backoffice_pages import register_backoffice_pages
from server.saas_charge_target_pages import register_charge_target_pages
from server.saas_fee_type_pages import register_fee_type_pages
from server.saas_user_pages import register_user_pages


def register_saas_pages(app, service, repository, current_user, sessions):
    register_backoffice_pages(app, current_user)
    register_user_pages(app, service, repository, current_user, sessions)
    register_charge_target_pages(app, service, repository, current_user)
    register_fee_type_pages(app, service, repository, current_user)
