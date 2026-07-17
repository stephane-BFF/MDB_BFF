"""registre BE : colonnes réglementation R/S/T (V1.2 Lot 0)

Ajoute à ``registre_be_items`` les colonnes issues du registre général BE :
``certification_brute`` (col. R telle quelle), les drapeaux dérivés ``desp``
et ``stamp_u``, ``categorie_risque`` (col. S) et ``module_evaluation``
(col. T). Migration purement additive — un réimport
``flask import-registre-be`` peuple les nouvelles colonnes.

Revision ID: a9c1d2e3f4b5
Revises: b1c2d3e4f5a6
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9c1d2e3f4b5'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('registre_be_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('certification_brute', sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column('desp', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column('stamp_u', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column('categorie_risque', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('module_evaluation', sa.String(length=10), nullable=True))


def downgrade():
    with op.batch_alter_table('registre_be_items', schema=None) as batch_op:
        batch_op.drop_column('module_evaluation')
        batch_op.drop_column('categorie_risque')
        batch_op.drop_column('stamp_u')
        batch_op.drop_column('desp')
        batch_op.drop_column('certification_brute')
