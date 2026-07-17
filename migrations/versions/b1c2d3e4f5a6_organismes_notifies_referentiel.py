"""Référentiel des organismes notifiés (ON PED 2014/68/UE) — table organismes_notifies

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-07-16 00:00:00.000000

Alimente la liste déroulante « Organisme notifié » du formulaire ATTDECR :
sélectionner un ON renseigne son numéro NANDO. Horodatages en
``CURRENT_TIMESTAMP`` (valide SQLite ET PostgreSQL).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "b1c2d3e4f5a6"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organismes_notifies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("numero", sa.String(length=4), nullable=False),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero", name="uq_organismes_notifies_numero"),
    )
    op.create_index(
        "ix_organismes_notifies_numero", "organismes_notifies", ["numero"]
    )


def downgrade() -> None:
    op.drop_index("ix_organismes_notifies_numero", table_name="organismes_notifies")
    op.drop_table("organismes_notifies")
