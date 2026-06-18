"""saas baseline

Revision ID: 0001_saas_baseline
Revises:
Create Date: 2026-06-18
"""
from alembic import op
from server.saas_schema import build_saas_postgres_schema

revision = "0001_saas_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for statement in build_saas_postgres_schema().split(";\n"):
        sql = statement.strip().rstrip(";")
        if sql:
            op.execute(sql)


def downgrade():
    for table in ["audit_logs", "imports", "payments", "bills", "fee_types", "charge_targets", "owners", "users", "role_permissions", "permissions", "roles", "projects", "tenants"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
