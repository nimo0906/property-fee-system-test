#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""物业管理收费系统 — 模块化包"""

from server.db import db_init
from server.base import BaseHandler
from server.auth import AuthMixin
from server.index import IndexMixin
from server.rooms import RoomMixin
from server.owners import OwnerMixin
from server.fees import FeeMixin
from server.meter import MeterMixin
from server.bill_list import BillListMixin
from server.bill_detail import BillDetailMixin
from server.bill_generation import BillGenerationMixin
from server.bill_export import BillExportMixin
from server.bill_print import BillPrintMixin
from server.bill_receipt import BillReceiptMixin
from server.payments import PaymentMixin
from server.billing_ui import BillingUiMixin
from server.repairs import RepairMixin
from server.parking import ParkingMixin
from server.invoices import InvoiceMixin
from server.deposits import DepositMixin
from server.reminders import ReminderMixin
from server.collections import CollectionMixin
from server.closing import ClosingMixin
from server.reports import ReportMixin
from server.import_data import ImportMixin
from server.backups import BackupMixin
from server.data_health import DataHealthMixin
from server.system_update_pages import SystemUpdateMixin
from server.shared_expenses import SharedExpenseMixin
from server.batch_ops import BatchOpsMixin
from server.owner_portal_pages import OwnerPortalPageMixin
from server.api import ApiMixin


class Handler(
    AuthMixin, IndexMixin, RoomMixin, OwnerMixin,
    FeeMixin, MeterMixin,
    BillListMixin, BillDetailMixin, BillGenerationMixin,
    BillExportMixin, BillPrintMixin, BillReceiptMixin,
    PaymentMixin, BillingUiMixin,
    RepairMixin, ParkingMixin, InvoiceMixin, DepositMixin,
    ReminderMixin, CollectionMixin, ClosingMixin, ReportMixin, SharedExpenseMixin, BatchOpsMixin,
    ImportMixin, BackupMixin, DataHealthMixin, SystemUpdateMixin, ApiMixin, OwnerPortalPageMixin, BaseHandler,
):
    """HTTP handler with all feature mixins."""
    pass
