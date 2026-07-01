"""Phase 5 — 2FA TOTP, codes de secours et jeton d'API sur users

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-01 00:00:00.000000

Ajoute à la table ``users`` :
    totp_secret     — secret TOTP base32 (nullable ; None = non enrôlé)
    totp_enabled    — 2FA active (booléen, défaut False)
    backup_codes    — hash SHA-256 des codes de secours à usage unique (JSONB)
    api_token_hash  — SHA-256 du jeton d'API REST (nullable, indexé)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("totp_secret", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "totp_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "backup_codes",
                postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("api_token_hash", sa.String(length=64), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_users_api_token_hash"), ["api_token_hash"], unique=False
        )

    # Retire le server_default une fois la colonne peuplée (défaut applicatif via ORM).
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("totp_enabled", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_api_token_hash"))
        batch_op.drop_column("api_token_hash")
        batch_op.drop_column("backup_codes")
        batch_op.drop_column("totp_enabled")
        batch_op.drop_column("totp_secret")
