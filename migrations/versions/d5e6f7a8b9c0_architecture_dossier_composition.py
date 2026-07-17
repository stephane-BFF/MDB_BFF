"""architecture type du dossier + composition par affaire (V1.2 Lot 6)

- ``types_equipement.formulaires_defaut`` (JSON) : architecture type — codes
  des formulaires inclus par défaut pour ce type d'équipement (NULL = tout).
- ``affaires.composition_dossier`` (JSON) : composition du dossier,
  initialisée depuis l'architecture type à la création puis personnalisable
  via la page Sommaire (NULL = tout inclus, rétrocompatible).

Migration purement additive.

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-07-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e6f7a8b9c0'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('types_equipement', schema=None) as batch_op:
        batch_op.add_column(sa.Column('formulaires_defaut', sa.JSON(), nullable=True))

    with op.batch_alter_table('affaires', schema=None) as batch_op:
        batch_op.add_column(sa.Column('composition_dossier', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('affaires', schema=None) as batch_op:
        batch_op.drop_column('composition_dossier')

    with op.batch_alter_table('types_equipement', schema=None) as batch_op:
        batch_op.drop_column('formulaires_defaut')
