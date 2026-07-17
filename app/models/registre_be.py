"""Modèle du registre général de commande BE (Bureau d'Études).

``RegistreBEItem`` reflète les lignes exploitables du fichier Excel
« Registre general commande BE.xlsx » entretenu par le BE : chaque ligne
associe un **n° d'affaire** (``BN``/``BP`` + 4 chiffres, ex. ``BN0811``) à un
**n° d'item** (4 chiffres, ex. ``8975``) au sein de cette affaire, avec les
informations d'identité déjà connues (client, repère, type d'appareil…).

Cette table est peuplée par la commande ``flask import-registre-be`` (voir
``app/services/registre_be.py`` et ``app/cli/import_registre.py``), jamais
modifiée manuellement. Elle alimente la liste déroulante de sélection du
n° d'affaire à l'étape Q1 du wizard de création (voir
``app/blueprints/affaires/routes.py``).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin


class RegistreBEItem(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Une ligne (affaire, item) du registre général de commande BE.

    Le couple (``numero_affaire``, ``item``) est unique : c'est la clé
    naturelle utilisée par l'import idempotent pour faire un upsert.
    """

    __tablename__ = "registre_be_items"
    __table_args__ = (
        UniqueConstraint("numero_affaire", "item", name="uq_registre_be_items_affaire_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    numero_affaire: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        doc="N° d'affaire BE (ex: BN0811, BP1234).",
    )
    item: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
        doc="N° d'item BE au sein de l'affaire (4 chiffres, ex: 8975).",
    )
    client_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destinataire: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repere_client: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Repère client tel que saisi par le BE (colonne « REPERE N° »).",
    )
    type_appareil: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Type d'appareil BFF (colonne « TYPE APPAREIL »).",
    )
    nombre: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annee: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    references_client: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="N° de commande client (colonne « N° Commande »).",
    )
    libelle_brut: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Texte brut de la colonne source (ex: « BN0811 - RM11721 »), "
        "conservé pour traçabilité.",
    )

    # ── Réglementation (colonnes R/S/T du registre — chantier V1.2 Lot 0) ──
    certification_brute: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Colonne R « CERTIFICATION » telle quelle (ex: « DESP 2014/68/UE », "
        "« STAMP U », « DESP + STAMP U », régimes historiques…).",
    )
    desp: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="True si la certification mentionne la DESP/PED (dérivé de la col. R).",
    )
    stamp_u: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="True si la certification mentionne le stamp U ASME (dérivé de la col. R).",
    )
    categorie_risque: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Colonne S « CAT » — catégorie de risque PED (I, II, III, IV, 4.3 ; "
        "valeurs historiques 97/23 possibles, ex: 3.3).",
    )
    module_evaluation: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Colonne T « MODULE » — module d'évaluation de la conformité "
        "(A, D1, E1, G, H, H1 ; valeurs historiques possibles, ex: A1, B1+F).",
    )

    @property
    def label(self) -> str:
        """Libellé lisible pour la liste déroulante item (Q1)."""
        parts = [self.item]
        if self.repere_client:
            parts.append(self.repere_client)
        elif self.type_appareil:
            parts.append(self.type_appareil)
        return " — ".join(parts)

    def __repr__(self) -> str:
        return f"<RegistreBEItem {self.numero_affaire}-{self.item}>"
