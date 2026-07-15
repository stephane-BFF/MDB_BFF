"""fix dérive de schéma : table fichiers_importes + index référentiels manquants

Revision ID: e1f2a3b4c5d6
Revises: dd4ac392761f
Create Date: 2026-07-15 00:00:00.000000

Corrige une dérive de schéma préexistante détectée par l'autogenerate Alembic
lors de la création de la migration ``dd4ac392761f`` (voir la note dans son
``upgrade()``). Deux écarts entre les modèles SQLAlchemy et les migrations :

1. La table ``fichiers_importes`` (modèle ``FichierImporte``) n'a jamais été
   créée par une migration — un ``flask db upgrade`` sur une base réelle
   plantait dès qu'un import de fichier était tenté (table absente).
2. Quatre index déclarés ``index=True`` dans les modèles de référentiels n'ont
   pas été créés par la migration Phase 4 (``a1b2c3d4e5f6``) :
       - ``soudeurs.nom``
       - ``operateurs_cnd.nom``
       - ``materiaux.designation``
       - ``instruments.reference`` (unique)

Sans impact sur les tests (qui utilisent ``db.create_all()``, pas Alembic).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'dd4ac392761f'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Table fichiers_importes (jamais créée par migration) ──────────────
    op.create_table(
        'fichiers_importes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('affaire_id', sa.Integer(), nullable=False),
        sa.Column('cree_par_id', sa.Integer(), nullable=False),
        sa.Column(
            'chapitre',
            sa.Enum('A', 'B', 'C', 'D', 'E', 'F', 'G',
                    name='chapitre_fichier', native_enum=False, length=2),
            nullable=False,
        ),
        sa.Column('titre', sa.String(length=200), nullable=False),
        sa.Column('ordre', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=100), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=50), nullable=False),
        sa.Column('taille', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['affaire_id'], ['affaires.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cree_par_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('fichiers_importes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fichiers_importes_affaire_id'), ['affaire_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fichiers_importes_chapitre'), ['chapitre'], unique=False)

    # ── 2. Index de référentiels manquants (dérive Phase 4) ──────────────────
    op.create_index(op.f('ix_soudeurs_nom'), 'soudeurs', ['nom'], unique=False)
    op.create_index(op.f('ix_operateurs_cnd_nom'), 'operateurs_cnd', ['nom'], unique=False)
    op.create_index(op.f('ix_materiaux_designation'), 'materiaux', ['designation'], unique=False)
    op.create_index(op.f('ix_instruments_reference'), 'instruments', ['reference'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_instruments_reference'), table_name='instruments')
    op.drop_index(op.f('ix_materiaux_designation'), table_name='materiaux')
    op.drop_index(op.f('ix_operateurs_cnd_nom'), table_name='operateurs_cnd')
    op.drop_index(op.f('ix_soudeurs_nom'), table_name='soudeurs')

    with op.batch_alter_table('fichiers_importes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fichiers_importes_chapitre'))
        batch_op.drop_index(batch_op.f('ix_fichiers_importes_affaire_id'))

    op.drop_table('fichiers_importes')
