"""add SaaS tenant project composite scope constraints

Revision ID: 0003_saas_project_tenant_scope
Revises: 0002_saas_import_storage_keys
Create Date: 2026-06-18
"""

from alembic import op


revision = "0003_saas_project_tenant_scope"
down_revision = "0002_saas_import_storage_keys"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_projects_id_tenant_id", "projects", ["id", "tenant_id"])
    for table in ["owners", "charge_targets", "fee_types", "bills", "payments", "imports", "audit_logs"]:
        op.create_foreign_key(
            f"fk_{table}_project_tenant_scope",
            table,
            "projects",
            ["project_id", "tenant_id"],
            ["id", "tenant_id"],
        )


def downgrade():
    for table in ["audit_logs", "imports", "payments", "bills", "fee_types", "charge_targets", "owners"]:
        op.drop_constraint(f"fk_{table}_project_tenant_scope", table, type_="foreignkey")
    op.drop_constraint("uq_projects_id_tenant_id", "projects", type_="unique")
