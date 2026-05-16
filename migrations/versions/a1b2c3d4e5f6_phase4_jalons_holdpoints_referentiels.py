"""Phase 4 — jalons, hold_points, soudeurs, operateurs_cnd, materiaux, instruments

Revision ID: a1b2c3d4e5f6
Revises: 6d7f9b70296a
Create Date: 2026-05-16 00:00:00.000000

Nouvelles tables :
    jalons          — JP0-JP6 par affaire (statut + prérequis + dates)
    hold_points     — Points d'arrêt inspecteur tiers liés à un jalon
    soudeurs        — Qualifications soudeurs DMOS/WPQR
    operateurs_cnd  — Qualifications CND (RT, UT, PT, MT)
    materiaux       — Désignations matériaux normalisées
    instruments     — Métrologie (manomètres, thermomètres…)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = "6d7f9b70296a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── jalons ──────────────────────────────────────────────────────────
    op.create_table(
        "jalons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("affaire_id", sa.Integer(), nullable=False),
        sa.Column(
            "code",
            sa.String(length=4),
            nullable=False,
        ),
        sa.Column(
            "statut",
            sa.String(length=15),
            nullable=False,
            server_default="EN_ATTENTE",
        ),
        sa.Column("date_prevue", sa.Date(), nullable=True),
        sa.Column("date_reelle", sa.Date(), nullable=True),
        sa.Column("prerequis_codes", sa.JSON(), nullable=True),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["affaire_id"], ["affaires.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jalons_affaire_id", "jalons", ["affaire_id"])
    op.create_index("ix_jalons_statut", "jalons", ["statut"])

    # ── hold_points ──────────────────────────────────────────────────────
    op.create_table(
        "hold_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jalon_id", sa.Integer(), nullable=False),
        sa.Column("organisme", sa.String(length=100), nullable=False),
        sa.Column("nom_inspecteur", sa.String(length=200), nullable=True),
        sa.Column("date_inspection", sa.Date(), nullable=True),
        sa.Column("signe", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["jalon_id"], ["jalons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hold_points_jalon_id", "hold_points", ["jalon_id"])

    # ── soudeurs ─────────────────────────────────────────────────────────
    op.create_table(
        "soudeurs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nom", sa.String(length=200), nullable=False),
        sa.Column("qualification", sa.String(length=100), nullable=False),
        sa.Column("indice", sa.String(length=20), nullable=True),
        sa.Column("date_expiration", sa.Date(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── operateurs_cnd ───────────────────────────────────────────────────
    op.create_table(
        "operateurs_cnd",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nom", sa.String(length=200), nullable=False),
        sa.Column("qualification", sa.String(length=50), nullable=False),
        sa.Column("niveau", sa.String(length=10), nullable=False),
        sa.Column("date_expiration", sa.Date(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── materiaux ────────────────────────────────────────────────────────
    op.create_table(
        "materiaux",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("designation", sa.String(length=255), nullable=False),
        sa.Column("norme", sa.String(length=100), nullable=False),
        sa.Column("certificat", sa.String(length=100), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── instruments ──────────────────────────────────────────────────────
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("type_instrument", sa.String(length=100), nullable=False),
        sa.Column("date_etalonnage", sa.Date(), nullable=True),
        sa.Column("date_prochain_etalonnage", sa.Date(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("instruments")
    op.drop_table("materiaux")
    op.drop_table("operateurs_cnd")
    op.drop_table("soudeurs")
    op.drop_index("ix_hold_points_jalon_id", table_name="hold_points")
    op.drop_table("hold_points")
    op.drop_index("ix_jalons_statut", table_name="jalons")
    op.drop_index("ix_jalons_affaire_id", table_name="jalons")
    op.drop_table("jalons")
