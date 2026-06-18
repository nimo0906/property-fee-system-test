"""add SaaS ops audit tables

Revision ID: 0004_saas_ops_audit_tables
Revises: 0003_saas_project_tenant_scope
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_saas_ops_audit_tables"
down_revision = "0003_saas_project_tenant_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "backup_records",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("backup_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "backup_id", name="uq_backup_records_tenant_backup_id"),
        sa.ForeignKeyConstraint(["project_id", "tenant_id"], ["projects.id", "projects.tenant_id"], name="fk_backup_records_project_tenant_scope"),
    )
    op.create_table(
        "restore_drills",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("backup_id", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id", "tenant_id"], ["projects.id", "projects.tenant_id"], name="fk_restore_drills_project_tenant_scope"),
    )


def downgrade():
    op.drop_table("restore_drills")
    op.drop_table("backup_records")
