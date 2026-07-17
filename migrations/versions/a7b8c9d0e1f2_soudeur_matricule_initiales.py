"""Soudeur : matricule + initiales, qualification devient facultative

Revision ID: a7b8c9d0e1f2
Revises: f3a4b5c6d7e8
Create Date: 2026-07-16 00:00:00.000000

Enrichit le référentiel Soudeur pour la liste déroulante « Soudeur » du
formulaire LISTSOUD : matricule (identifiant BFF) et initiales / poinçon.
La ``qualification`` devient facultative — un soudeur peut être répertorié
par son identité seule, le détail par QS étant saisi dans le formulaire.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "a7b8c9d0e1f2"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("soudeurs") as batch:
        batch.add_column(sa.Column("matricule", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("initiales", sa.String(length=10), nullable=True))
        batch.alter_column(
            "qualification",
            existing_type=sa.String(length=100),
            nullable=True,
        )
        batch.create_index("ix_soudeurs_matricule", ["matricule"])


def downgrade() -> None:
    # Les soudeurs répertoriés par identité seule (seed) ont une qualification
    # NULL : la remplir avant de restaurer la contrainte NOT NULL, sinon la
    # recréation de table échoue.
    op.execute("UPDATE soudeurs SET qualification = '' WHERE qualification IS NULL")
    with op.batch_alter_table("soudeurs") as batch:
        batch.drop_index("ix_soudeurs_matricule")
        batch.alter_column(
            "qualification",
            existing_type=sa.String(length=100),
            nullable=False,
        )
        batch.drop_column("initiales")
        batch.drop_column("matricule")
