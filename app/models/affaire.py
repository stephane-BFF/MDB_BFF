"""Modèles Affaire et ParametrageAffaire.

Une **Affaire** représente un dossier qualité (manufacturer's data book) pour
un équipement BFF. Elle est créée via un wizard de 4 étapes (Q1 → Q4) puis
suit le workflow ``WIZARD_BROUILLON → BROUILLON → SOUMIS → VALIDE → SIGNE
→ CLOTUREE → ARCHIVEE``.

Le **ParametrageAffaire** stocke les réponses du wizard en JSONB pour deux
raisons :

1. La matrice de paramétrage (CDC v3) peut évoluer sans migration
   schéma.
2. Les réponses pilotent l'activation conditionnelle des formulaires, mais
   ne sont pas requêtées atomiquement.

Les champs « identité » réellement utilisés sur la page de garde et le
sommaire du MDB (numéro, client, repère, type d'échangeur…) sont
matérialisés en colonnes typées sur ``Affaire`` pour autoriser des filtres
indexés (dashboard, recherche).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import Statut, StatutWizard
from app.extensions import db
from app.models.base import TimestampMixin
from app.models.referentiel import TypeEquipement
from app.models.user import User

if TYPE_CHECKING:
    from app.models.fichier import FichierImporte
    from app.models.formulaire import Formulaire
    from app.models.jalon import Jalon


class Affaire(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Dossier constructeur qualité (MDB) pour un équipement BFF.

    Cycle de vie :
        WIZARD_BROUILLON (création via wizard Q1→Q4) → BROUILLON (wizard
        complet) → SOUMIS → VALIDE → SIGNE → CLOTUREE → ARCHIVEE.

    Pendant le wizard, la plupart des champs « identité » sont ``NULL`` et
    se remplissent au fur et à mesure. La transition vers BROUILLON
    présuppose qu'ils sont tous renseignés (validation service-side).
    """

    __tablename__ = "affaires"
    __table_args__ = (
        UniqueConstraint("numero_affaire", "item", name="uq_affaires_numero_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Identité du dossier (page de garde + sommaire MDB) ───────────────
    numero_affaire: Mapped[str | None] = mapped_column(
        String(10),
        index=True,
        nullable=True,
        doc="N° d'affaire attribué par le BE, format BN|BP + 4 chiffres (ex: BN0811).",
    )
    item: Mapped[str | None] = mapped_column(
        String(4),
        nullable=True,
        doc="N° d'item BE au sein de l'affaire (4 chiffres, ex: 8975) — une "
        "même affaire peut porter plusieurs items/dossiers.",
    )
    annee: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        nullable=True,
        doc="Année de l'affaire.",
    )
    client_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    references_client: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="« VOS REFERENCES » — bon de commande client.",
    )
    references_internes: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="« NOS REFERENCES » BFF — calculée automatiquement en "
        "``{numero_affaire}-{item}`` (ex: BN0811-8975) à la validation de Q1.",
    )
    repere: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Repère équipement client (ex: 322TK4131).",
    )
    type_echangeur: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Type d'échangeur BFF (ex: H1 06-01-72).",
    )
    type_equipement_id: Mapped[int | None] = mapped_column(
        ForeignKey("types_equipement.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        doc="Type d'équipement (référentiel V1.2 : Réfrigérant, HPIN, BHM…).",
    )
    nombre: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Nombre d'appareils livrés sous ce dossier.",
    )
    annee_construction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    composition_dossier: Mapped[list[str] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        doc="Composition du dossier (V1.2 Lot 6, D8) : codes des formulaires "
        "inclus au sommaire. NULL = tout inclus (rétrocompatible). "
        "Initialisée depuis l'architecture type du type d'équipement, puis "
        "personnalisable via la page Sommaire. Exclure ne supprime aucune "
        "donnée.",
    )

    # ── Workflow ─────────────────────────────────────────────────────────
    statut: Mapped[Statut] = mapped_column(
        SQLEnum(Statut, name="statut", native_enum=False, length=20),
        nullable=False,
        index=True,
        default=Statut.WIZARD_BROUILLON,
    )
    statut_wizard: Mapped[StatutWizard | None] = mapped_column(
        SQLEnum(StatutWizard, name="statut_wizard", native_enum=False, length=4),
        nullable=True,
        default=StatutWizard.Q1,
        doc="Étape courante du wizard ; ``NULL`` lorsque le wizard est terminé.",
    )

    # ── Traçabilité ──────────────────────────────────────────────────────
    cree_par_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cree_par: Mapped[User] = relationship(
        back_populates="affaires_creees",
        foreign_keys=[cree_par_id],
    )

    # ── Relations ────────────────────────────────────────────────────────
    type_equipement: Mapped[TypeEquipement | None] = relationship()
    parametrage: Mapped[ParametrageAffaire | None] = relationship(
        back_populates="affaire",
        uselist=False,
        cascade="all, delete-orphan",
    )
    formulaires: Mapped[list[Formulaire]] = relationship(
        back_populates="affaire",
        cascade="all, delete-orphan",
        order_by="(Formulaire.chapitre, Formulaire.code)",
    )
    fichiers_importes: Mapped[list[FichierImporte]] = relationship(
        back_populates="affaire",
        cascade="all, delete-orphan",
        order_by="(FichierImporte.chapitre, FichierImporte.ordre)",
    )
    jalons: Mapped[list[Jalon]] = relationship(
        back_populates="affaire",
        cascade="all, delete-orphan",
        order_by="Jalon.code",
    )

    # ── Propriétés calculées ─────────────────────────────────────────────
    @property
    def is_wizard(self) -> bool:
        """True si l'affaire est encore dans le wizard de création."""
        return self.statut is Statut.WIZARD_BROUILLON

    @property
    def is_editable(self) -> bool:
        """True si l'affaire peut encore être modifiée (hors Admin)."""
        return self.statut.is_editable

    def __repr__(self) -> str:
        return f"<Affaire {self.numero_affaire or '(wizard)'} statut={self.statut.value}>"


class ParametrageAffaire(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Réponses du wizard et de la fiche technique de l'item.

    Stockage JSONB pour permettre l'évolution de la matrice de paramétrage
    (CDC v3) sans migration schéma. Les réponses pilotent l'activation
    conditionnelle des 27 formulaires.

    Attributes:
        reponses: Dict {clé Q → valeur}, ex: ``{"q3_categorie_ped": "III",
            "q5_groupe_fluide": 2, "q6_pression_design_bar": 16}``.
        template_version: Version de la matrice Q1-Q8 utilisée. Permet
            d'interpréter ``reponses`` avec le bon schéma même après
            évolution.
    """

    __tablename__ = "parametrages_affaire"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    affaire_id: Mapped[int] = mapped_column(
        ForeignKey("affaires.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    reponses: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        doc="Réponses Q1-Q8 stockées en JSON ; clés ``qN_<champ>``.",
    )
    template_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Version de la matrice de paramétrage utilisée.",
    )

    affaire: Mapped[Affaire] = relationship(back_populates="parametrage")

    def __repr__(self) -> str:
        return f"<ParametrageAffaire affaire_id={self.affaire_id} v{self.template_version}>"
