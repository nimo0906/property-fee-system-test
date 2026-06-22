"""add SaaS merchant contracts and amendments

Revision ID: 0009_saas_merchant_contracts
Revises: 0008_saas_meter_readings
Create Date: 2026-06-22
"""

from alembic import op


revision = "0009_saas_merchant_contracts"
down_revision = "0008_saas_meter_readings"
branch_labels = None
depends_on = None


UPGRADE_SQL = [
    "ALTER TABLE bills ADD COLUMN IF NOT EXISTS source TEXT",
    "ALTER TABLE bills ADD COLUMN IF NOT EXISTS source_ref TEXT",
    """
    CREATE TABLE IF NOT EXISTS merchant_contracts (
        id BIGSERIAL PRIMARY KEY,
        tenant_id BIGINT NOT NULL REFERENCES tenants(id),
        project_id BIGINT NOT NULL REFERENCES projects(id),
        charge_target_id BIGINT NOT NULL REFERENCES charge_targets(id),
        contract_no TEXT NOT NULL,
        merchant_name TEXT NOT NULL,
        shop_name TEXT,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        contract_area NUMERIC(12,2) NOT NULL DEFAULT 0,
        rent_unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
        property_rate NUMERIC(12,4) NOT NULL DEFAULT 0,
        rent_cycle TEXT NOT NULL DEFAULT 'monthly',
        property_cycle TEXT NOT NULL DEFAULT 'monthly',
        deposit_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(tenant_id, project_id, contract_no),
        FOREIGN KEY(project_id, tenant_id) REFERENCES projects(id, tenant_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS contract_amendments (
        id BIGSERIAL PRIMARY KEY,
        tenant_id BIGINT NOT NULL REFERENCES tenants(id),
        project_id BIGINT NOT NULL REFERENCES projects(id),
        contract_id BIGINT NOT NULL REFERENCES merchant_contracts(id),
        amendment_no TEXT NOT NULL,
        effective_date DATE NOT NULL,
        rent_unit_price NUMERIC(12,2),
        property_rate NUMERIC(12,4),
        contract_area NUMERIC(12,2),
        status TEXT NOT NULL DEFAULT 'confirmed',
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(tenant_id, project_id, contract_id, amendment_no),
        FOREIGN KEY(project_id, tenant_id) REFERENCES projects(id, tenant_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_merchant_contracts_scope ON merchant_contracts(tenant_id, project_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_contract_amendments_contract ON contract_amendments(tenant_id, project_id, contract_id)",
]

DOWNGRADE_SQL = [
    "DROP INDEX IF EXISTS idx_contract_amendments_contract",
    "DROP INDEX IF EXISTS idx_merchant_contracts_scope",
    "DROP TABLE IF EXISTS contract_amendments",
    "DROP TABLE IF EXISTS merchant_contracts",
]


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    for statement in DOWNGRADE_SQL:
        op.execute(statement)
