"""add SaaS owner and charge target alignment fields

Revision ID: 0007_saas_charge_target_room_fields
Revises: 0006_saas_payment_receipts
Create Date: 2026-06-20
"""

from alembic import op


revision = "0007_saas_charge_target_room_fields"
down_revision = "0006_saas_payment_receipts"
branch_labels = None
depends_on = None


UPGRADE_SQL = [
    "ALTER TABLE owners ADD COLUMN IF NOT EXISTS owner_type TEXT NOT NULL DEFAULT '业主'",
    "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS unit_price_override NUMERIC(12,4)",
    "ALTER TABLE fee_types ADD COLUMN IF NOT EXISTS billing_mode TEXT NOT NULL DEFAULT 'area'",
    "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS floor INTEGER",
    "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS shop_name TEXT",
    "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS tenant_name TEXT",
    "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS tenant_phone TEXT",
    "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS payment_cycle TEXT",
    "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS notes TEXT",
]

DOWNGRADE_SQL = [
    "ALTER TABLE charge_targets DROP COLUMN IF EXISTS notes",
    "ALTER TABLE charge_targets DROP COLUMN IF EXISTS payment_cycle",
    "ALTER TABLE charge_targets DROP COLUMN IF EXISTS tenant_phone",
    "ALTER TABLE charge_targets DROP COLUMN IF EXISTS tenant_name",
    "ALTER TABLE charge_targets DROP COLUMN IF EXISTS shop_name",
    "ALTER TABLE charge_targets DROP COLUMN IF EXISTS floor",
    "ALTER TABLE fee_types DROP COLUMN IF EXISTS billing_mode",
    "ALTER TABLE charge_targets DROP COLUMN IF EXISTS unit_price_override",
    "ALTER TABLE owners DROP COLUMN IF EXISTS owner_type",
]


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    for statement in DOWNGRADE_SQL:
        op.execute(statement)
