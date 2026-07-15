"""registre BE et n° item par affaire

Revision ID: dd4ac392761f
Revises: b7c8d9e0f1a2
Create Date: 2026-07-01 21:23:26.585558

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd4ac392761f'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    # NOTE : l'autogenerate Alembic a aussi détecté une dérive de schéma
    # préexistante et sans rapport avec cette migration (table
    # ``fichiers_importes`` et plusieurs index sur soudeurs/materiaux/
    # operateurs_cnd/instruments absents de la base bien que présents dans
    # les modèles). Volontairement laissée de côté ici — signalée à part.
    op.create_table('registre_be_items',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('numero_affaire', sa.String(length=10), nullable=False),
    sa.Column('item', sa.String(length=4), nullable=False),
    sa.Column('client_nom', sa.String(length=255), nullable=True),
    sa.Column('destinataire', sa.String(length=255), nullable=True),
    sa.Column('repere_client', sa.String(length=100), nullable=True),
    sa.Column('type_appareil', sa.String(length=100), nullable=True),
    sa.Column('nombre', sa.Integer(), nullable=True),
    sa.Column('annee', sa.Integer(), nullable=True),
    sa.Column('references_client', sa.String(length=100), nullable=True),
    sa.Column('libelle_brut', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('numero_affaire', 'item', name='uq_registre_be_items_affaire_item')
    )
    with op.batch_alter_table('registre_be_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_registre_be_items_annee'), ['annee'], unique=False)
        batch_op.create_index(batch_op.f('ix_registre_be_items_numero_affaire'), ['numero_affaire'], unique=False)

    with op.batch_alter_table('affaires', schema=None) as batch_op:
        batch_op.add_column(sa.Column('item', sa.String(length=4), nullable=True))
        batch_op.alter_column('numero_affaire',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=10),
               existing_nullable=True)
        batch_op.drop_index(batch_op.f('ix_affaires_numero_affaire'))
        batch_op.create_index(batch_op.f('ix_affaires_numero_affaire'), ['numero_affaire'], unique=False)
        batch_op.create_unique_constraint('uq_affaires_numero_item', ['numero_affaire', 'item'])


def downgrade():
    with op.batch_alter_table('affaires', schema=None) as batch_op:
        batch_op.drop_constraint('uq_affaires_numero_item', type_='unique')
        batch_op.drop_index(batch_op.f('ix_affaires_numero_affaire'))
        batch_op.create_index(batch_op.f('ix_affaires_numero_affaire'), ['numero_affaire'], unique=1)
        batch_op.alter_column('numero_affaire',
               existing_type=sa.String(length=10),
               type_=sa.VARCHAR(length=20),
               existing_nullable=True)
        batch_op.drop_column('item')

    with op.batch_alter_table('registre_be_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_registre_be_items_numero_affaire'))
        batch_op.drop_index(batch_op.f('ix_registre_be_items_annee'))

    op.drop_table('registre_be_items')
