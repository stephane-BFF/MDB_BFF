"""types d'équipement (référentiel V1.2 D7) + FK sur affaires

Crée la table ``types_equipement`` (Réfrigérant, HPIN, BHM, RM, SHELL&TUBE,
FAISCEAU de rechange, CALANDRE de rechange, BEU — seedés par ``flask seed``)
et la colonne ``affaires.type_equipement_id``. Migration additive.

Revision ID: c3d4e5f6a7b8
Revises: a9c1d2e3f4b5
Create Date: 2026-07-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'a9c1d2e3f4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('types_equipement',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('libelle', sa.String(length=100), nullable=False),
    sa.Column('ordre', sa.Integer(), nullable=False),
    sa.Column('actif', sa.Boolean(), nullable=False),
    sa.Column('commentaire', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('libelle', name='uq_types_equipement_libelle')
    )
    with op.batch_alter_table('types_equipement', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_types_equipement_libelle'), ['libelle'], unique=False)

    with op.batch_alter_table('affaires', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type_equipement_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_affaires_type_equipement_id'), ['type_equipement_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_affaires_type_equipement_id',
            'types_equipement',
            ['type_equipement_id'],
            ['id'],
            ondelete='RESTRICT',
        )


def downgrade():
    with op.batch_alter_table('affaires', schema=None) as batch_op:
        batch_op.drop_constraint('fk_affaires_type_equipement_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_affaires_type_equipement_id'))
        batch_op.drop_column('type_equipement_id')

    with op.batch_alter_table('types_equipement', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_types_equipement_libelle'))

    op.drop_table('types_equipement')
