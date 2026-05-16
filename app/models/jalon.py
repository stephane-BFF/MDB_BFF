"""Modèles Jalon et HoldPoint — suivi de l'avancement JP0-JP6.

Un **Jalon** représente un point de contrôle obligatoire dans la fabrication
d'un équipement BFF. Il est associé à une liste de prérequis documentaires
(codes formulaires) qui doivent être au statut VALIDE ou SIGNE avant de
pouvoir le franchir.

Un **HoldPoint** est une signature inspecteur tiers (ex. LRQA) attachée à
un jalon. Une fois signé, le jalon est verrouillé : aucune modification des
formulaires prérequis n'est autorisée.

Structure jalons JP0-JP6 (référence CDC v1) :
    JP0 — Revue de lancement        (aucun prérequis documentaire)
    JP1 — Lancement fabrication     (BIM, LISTSOUD)
    JP2 — Fin de soudage            (NDEMAP, LISTCND)
    JP3 — Fin traitements thermiques (TTH1 si applicable)
    JP4 — Test hydrostatique        (HYDR)
    JP5 — Contrôles finaux          (VISUFINAL, DIM, PROPRETE)
    JP6 — Expédition                (tous les formulaires signés)
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import JalonCode, StatutJalon
from app.extensions import db
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.user import User


# ── Prérequis documentaires par jalon (ordre canonique) ───────────────────

PREREQUIS_PAR_JALON: dict[JalonCode, list[str]] = {
    JalonCode.JP0: [],
    JalonCode.JP1: ["BIM", "LISTSOUD"],
    JalonCode.JP2: ["NDEMAP", "LISTCND"],
    JalonCode.JP3: ["TTH1"],          # optionnel selon paramétrage
    JalonCode.JP4: ["HYDR"],
    JalonCode.JP5: ["VISUFINAL", "DIM", "PROPRETE"],
    JalonCode.JP6: [
        "CONFCOM", "ATTDECR", "ATTREP", "ETATDESC",
        "BIM", "BIMSOUD", "PMI",
        "TTH1", "LISTSOUD", "ROLLING", "DIM",
        "LISTCND", "NDEMAP", "DURETE", "FERRITE",
        "HYDR", "RECORDHYDRO", "AIRSAV", "AZOTE",
        "VISUFINAL", "PROPRETE", "SECHAGE", "PESAGE",
        "PEDMOD",
    ],
}

_JALON_LABELS: dict[JalonCode, str] = {
    JalonCode.JP0: "Revue de lancement",
    JalonCode.JP1: "Lancement fabrication",
    JalonCode.JP2: "Fin de soudage",
    JalonCode.JP3: "Fin traitements thermiques",
    JalonCode.JP4: "Test hydrostatique",
    JalonCode.JP5: "Contrôles finaux",
    JalonCode.JP6: "Expédition",
}


class Jalon(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Jalon de fabrication JP0-JP6 pour une affaire BFF.

    Un jalon est initialisé automatiquement (statut EN_ATTENTE) lors de la
    création d'une affaire. Son franchissement est conditionné par les
    prérequis documentaires définis dans ``PREREQUIS_PAR_JALON``.
    """

    __tablename__ = "jalons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    affaire_id: Mapped[int] = mapped_column(
        ForeignKey("affaires.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[JalonCode] = mapped_column(
        SQLEnum(JalonCode, name="jalon_code", native_enum=False, length=4),
        nullable=False,
    )
    statut: Mapped[StatutJalon] = mapped_column(
        SQLEnum(StatutJalon, name="statut_jalon", native_enum=False, length=15),
        nullable=False,
        default=StatutJalon.EN_ATTENTE,
        index=True,
    )

    date_prevue: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date cible fixée par le chargé d'affaires.",
    )
    date_reelle: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date effective de franchissement.",
    )

    # Override des prérequis (liste de codes formulaires JSON) — None = valeur par défaut
    prerequis_codes: Mapped[list[str] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        doc="Surcharge des prérequis par défaut (None = utiliser PREREQUIS_PAR_JALON).",
    )

    commentaire: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Relations ────────────────────────────────────────────────────────────
    affaire: Mapped[Affaire] = relationship(back_populates="jalons")
    hold_points: Mapped[list[HoldPoint]] = relationship(
        back_populates="jalon",
        cascade="all, delete-orphan",
        order_by="HoldPoint.created_at",
    )

    # ── Propriétés calculées ─────────────────────────────────────────────────

    @property
    def label(self) -> str:
        """Libellé descriptif du jalon."""
        return _JALON_LABELS.get(self.code, self.code.value)

    @property
    def effective_prerequis(self) -> list[str]:
        """Prérequis effectifs (surcharge ou valeur par défaut)."""
        if self.prerequis_codes is not None:
            return list(self.prerequis_codes)
        return list(PREREQUIS_PAR_JALON.get(self.code, []))

    @property
    def est_verrouille(self) -> bool:
        """True si au moins un Hold Point a été signé (jalon immuable)."""
        return any(hp.signe for hp in self.hold_points)

    @property
    def est_franchi(self) -> bool:
        """True si le jalon a été franchi."""
        return self.statut is StatutJalon.FRANCHI


class HoldPoint(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Point d'arrêt avec signature inspecteur tiers.

    Un Hold Point est créé lorsqu'un client ou organisme notifié (ex. LRQA)
    exige une présence physique avant de passer au jalon suivant. Une fois
    signé, il verrouille le jalon et empêche toute modification des
    formulaires prérequis.
    """

    __tablename__ = "hold_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    jalon_id: Mapped[int] = mapped_column(
        ForeignKey("jalons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organisme: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Nom de l'organisme (ex: LRQA, Bureau Veritas, client).",
    )
    nom_inspecteur: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Nom de l'inspecteur tiers.",
    )
    date_inspection: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    signe: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="True si l'inspecteur a validé et signé le hold point.",
    )
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relations ────────────────────────────────────────────────────────────
    jalon: Mapped[Jalon] = relationship(back_populates="hold_points")
