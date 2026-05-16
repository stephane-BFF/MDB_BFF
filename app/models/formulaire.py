"""Modèles Formulaire (générique JSONB) et FormulaireTemplate (versioning).

Décision architecturale : **une seule table** ``formulaires`` héberge les
27 formulaires qualité plutôt que 27 tables dédiées. Les champs communs
(``id, affaire_id, code, chapitre, statut, template_version``) sont
indexés ; les champs spécifiques (``ps``, ``pt``, observations…) vivent
dans ``data: JSONB``.

Chaque formulaire référence un ``FormulaireTemplate`` via la paire
``(code, template_version)`` — composite FK pour intégrité référentielle.
La table ``formulaires_templates`` versionne le schéma de champs : tout
formulaire signé reste affichable selon le schéma de la version qui l'a
produit, même après une évolution ultérieure.

La logique métier spécifique (ex: calcul PT = PS × 1.43 pour HYDR) vit
dans ``app/services/formulaires/<code>.py`` — **jamais** dans ce modèle.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import Chapitre, Statut
from app.extensions import db
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.signature import Signature


class FormulaireTemplate(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Schéma versionné d'un formulaire qualité.

    Une ligne par couple ``(code, version)`` — ex: ``("HYDR", 1)``,
    ``("HYDR", 2)`` après évolution. Le champ ``schema`` (JSON Schema)
    décrit les champs attendus dans ``Formulaire.data``.

    Attributes:
        code: Code court du formulaire (ex: ``"HYDR"``, ``"BIM"``, ``"DIM"``).
        version: Numéro de version (incrémental, démarre à 1).
        chapitre: Chapitre du dossier qualité (A à G).
        libelle: Titre du formulaire en français.
        libelle_en: Titre en anglais (pour les modules PED multilingues).
        schema: JSON Schema décrivant les champs de ``Formulaire.data``.
        actif: True si cette version est la « courante » pour ce code
            (sert à orienter les nouvelles instanciations).
    """

    __tablename__ = "formulaires_templates"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_template_code_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chapitre: Mapped[Chapitre] = mapped_column(
        SQLEnum(Chapitre, name="chapitre", native_enum=False, length=1),
        nullable=False,
    )
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    libelle_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        doc="JSON Schema décrivant les champs autorisés dans Formulaire.data.",
    )
    actif: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="True = version courante utilisée pour les nouvelles instances.",
    )

    def __repr__(self) -> str:
        return f"<FormulaireTemplate {self.code} v{self.version}>"


class Formulaire(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Instance d'un formulaire qualité au sein d'une affaire.

    Workflow : ``BROUILLON → SOUMIS → (REJETE → BROUILLON) → VALIDE → SIGNE``.
    Voir ``app.enums.Statut``.

    Attributes:
        affaire_id: FK vers l'affaire propriétaire (cascade DELETE).
        code: Code du formulaire (ex: ``"HYDR"``). Indexé pour requêtes
            dashboard et activation conditionnelle.
        chapitre: Chapitre A-G de rattachement (redondant avec
            ``template.chapitre``, dénormalisé pour requêtes rapides).
        statut: Statut workflow courant.
        data: Champs spécifiques au formulaire, conformes au JSON Schema
            de la version template référencée.
        template_version: Version du template (référence composite FK
            avec ``code`` → ``formulaires_templates(code, version)``).
    """

    __tablename__ = "formulaires"
    __table_args__ = (
        ForeignKeyConstraint(
            ["code", "template_version"],
            ["formulaires_templates.code", "formulaires_templates.version"],
            ondelete="RESTRICT",
            name="fk_formulaire_template",
        ),
        UniqueConstraint(
            "affaire_id", "code", name="uq_formulaire_affaire_code"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    affaire_id: Mapped[int] = mapped_column(
        ForeignKey("affaires.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    chapitre: Mapped[Chapitre] = mapped_column(
        SQLEnum(Chapitre, name="chapitre", native_enum=False, length=1),
        nullable=False,
        index=True,
    )
    statut: Mapped[Statut] = mapped_column(
        SQLEnum(Statut, name="statut", native_enum=False, length=20),
        nullable=False,
        default=Statut.BROUILLON,
        index=True,
    )
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        doc="Champs spécifiques du formulaire (conformes au template).",
    )
    template_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Version du FormulaireTemplate utilisée — fige le schéma pour ce formulaire.",
    )

    # ── Relations ────────────────────────────────────────────────────────
    affaire: Mapped[Affaire] = relationship(back_populates="formulaires")
    signatures: Mapped[list[Signature]] = relationship(
        back_populates="formulaire",
        cascade="all, delete-orphan",
        order_by="Signature.created_at",
    )

    # ── Propriétés calculées génériques ──────────────────────────────────
    @property
    def is_editable(self) -> bool:
        """True si le contenu peut encore être modifié (hors Admin)."""
        return self.statut.is_editable

    @property
    def is_signed(self) -> bool:
        """True si le formulaire a été signé (au moins une signature)."""
        return self.statut is Statut.SIGNE

    def __repr__(self) -> str:
        return (
            f"<Formulaire {self.code} v{self.template_version} "
            f"affaire_id={self.affaire_id} statut={self.statut.value}>"
        )
