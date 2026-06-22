"""add SaaS meter readings

Revision ID: 0008_saas_meter_readings
Revises: 0007_saas_charge_target_room_fields
Create Date: 2026-06-22
"""

from alembic import op


revision = "0008_saas_meter_readings"
down_revision = "0007_saas_charge_target_room_fields"
branch_labels = None
depends_on = None


UPGRADE_SQL = [
    """
    CREATE TABLE IF NOT EXISTS meter_readings (
        id BIGSERIAL PRIMARY KEY,
        tenant_id BIGINT NOT NULL REFERENCES tenants(id),
        project_id BIGINT NOT NULL REFERENCES projects(id),
        charge_target_id BIGINT NOT NULL REFERENCES charge_targets(id),
        fee_type_id BIGINT NOT NULL REFERENCES fee_types(id),
        billing_period TEXT NOT NULL,
        previous_reading NUMERIC(12,2) NOT NULL DEFAULT 0,
        current_reading NUMERIC(12,2) NOT NULL DEFAULT 0,
        consumption NUMERIC(12,2) NOT NULL DEFAULT 0,
        reading_date DATE,
        status TEXT NOT NULL DEFAULT 'draft',
        notes TEXT,
        bill_id BIGINT REFERENCES bills(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(tenant_id, project_id, charge_target_id, fee_type_id, billing_period),
        FOREIGN KEY(project_id, tenant_id) REFERENCES projects(id, tenant_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_meter_readings_scope_period ON meter_readings(tenant_id, project_id, billing_period)",
    "CREATE INDEX IF NOT EXISTS idx_meter_readings_bill ON meter_readings(bill_id)",
]

DOWNGRADE_SQL = [
    "DROP INDEX IF EXISTS idx_meter_readings_bill",
    "DROP INDEX IF EXISTS idx_meter_readings_scope_period",
    "DROP TABLE IF EXISTS meter_readings",
]


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    for statement in DOWNGRADE_SQL:
        op.execute(statement)
