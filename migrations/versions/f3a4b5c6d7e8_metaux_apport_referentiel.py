"""Référentiel des métaux d'apport (consommables de soudage) — table metaux_apport

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6
Create Date: 2026-07-16 00:00:00.000000

Alimente la liste déroulante du formulaire BIMSOUD : désignation →
classification (norme AWS) + fournisseur renseignés automatiquement.

Note : les horodatages utilisent ``CURRENT_TIMESTAMP`` (valide SQLite ET
PostgreSQL) et non ``now()`` — cf. correctif du bug de finalisation Q8.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "f3a4b5c6d7e8"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metaux_apport",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("designation", sa.String(length=150), nullable=False),
        sa.Column("classification", sa.String(length=150), nullable=False),
        sa.Column("fournisseur", sa.String(length=150), nullable=True),
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
        sa.UniqueConstraint("designation", name="uq_metaux_apport_designation"),
    )
    op.create_index("ix_metaux_apport_designation", "metaux_apport", ["designation"])


def downgrade() -> None:
    op.drop_index("ix_metaux_apport_designation", table_name="metaux_apport")
    op.drop_table("metaux_apport")
