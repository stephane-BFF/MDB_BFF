"""Modèles des référentiels BFF — ressources qualité partagées entre affaires.

Les référentiels sont des tables de données maîtres gérées par les
Approbateurs et l'Admin. Elles alimentent les listes déroulantes des
formulaires (soudeurs, contrôleurs CND, matériaux…) et font l'objet
d'alertes automatiques lorsque les certifications ou étalonnages approchent
de leur date d'expiration.

Entités :
    Soudeur          — qualifications DMOS/WPQR avec date d'expiration
    OperateurCND     — qualifications CND (RT, UT, PT, MT) avec niveau
    Materiau         — désignations normalisées (EN, ASME…)
    Instrument       — métrologie : réf., type, date d'étalonnage suivant

Convention d'alerte expiration :
    > 30 jours  → vert   (OK)
    ≤ 30 jours  → orange (bientôt expiré)
    expiré      → rouge  (invalide)
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Boolean, Date, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TimestampMixin

# ── Seuil d'alerte expiration ─────────────────────────────────────────────

SEUIL_ALERTE_JOURS: int = 30


def _statut_expiration(date_exp: date | None) -> str:
    """Retourne 'ok', 'bientot' ou 'expire' selon la date d'expiration."""
    if date_exp is None:
        return "ok"
    today = date.today()
    if date_exp < today:
        return "expire"
    if date_exp <= today + timedelta(days=SEUIL_ALERTE_JOURS):
        return "bientot"
    return "ok"


class Soudeur(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Soudeur qualifié BFF — qualification DMOS/WPQR avec date d'expiration.

    Utilisé dans les formulaires LISTSOUD et ROLLING pour identifier
    les opérateurs habilités aux opérations de soudage.
    """

    __tablename__ = "soudeurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    matricule: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        doc="Matricule / identifiant BFF du soudeur (ex: 96).",
    )
    initiales: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Initiales / poinçon du soudeur (ex: SG).",
    )
    nom: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        doc="Nom complet du soudeur.",
    )
    qualification: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Référence qualification globale (ex: DMOS 001, WPQR 135-FW-BW). "
        "Facultatif : le détail par QS est saisi dans le formulaire LISTSOUD.",
    )
    indice: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Indice de révision de la qualification (ex: A, B, C).",
    )
    date_expiration: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date d'expiration de la qualification soudeur.",
    )
    actif: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="False si le soudeur a quitté BFF ou sa qualification est révoquée.",
    )
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def statut_expiration(self) -> str:
        """'ok', 'bientot' (≤30 j) ou 'expire'."""
        return _statut_expiration(self.date_expiration)


class OperateurCND(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Opérateur de contrôle non destructif (CND) certifié.

    Utilisé dans LISTCND pour référencer les contrôleurs autorisés à
    effectuer les contrôles RT, UT, PT, MT sur les soudures BFF.
    """

    __tablename__ = "operateurs_cnd"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    nom: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )
    qualification: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Type de contrôle (RT, UT, PT, MT, VT, ET…).",
    )
    niveau: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Niveau de certification (I, II, III selon ISO 9712 ou ASNT).",
    )
    date_expiration: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def statut_expiration(self) -> str:
        """'ok', 'bientot' (≤30 j) ou 'expire'."""
        return _statut_expiration(self.date_expiration)


class Materiau(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Matériau de base ou d'apport approuvé pour les équipements BFF.

    Référencé dans les formulaires BIM (matériaux de base) et BIMSOUD
    (matériaux d'apport soudage).
    """

    __tablename__ = "materiaux"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    designation: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Désignation normalisée (ex: 304L, S31603, P265GH).",
    )
    norme: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Norme de référence (ex: EN 10028-7, ASME SA-240, EN 10216-5).",
    )
    certificat: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Numéro de certificat ou type attendu (ex: 3.1 EN 10204).",
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)


class MetalApport(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Métal d'apport (consommable de soudage) — référentiel BFF.

    Alimente la liste déroulante du formulaire BIMSOUD : sélectionner une
    désignation renseigne automatiquement la classification (norme AWS) et le
    fournisseur. Peuplé par ``flask seed`` depuis le fichier source
    ``LISTE_AQ_EF_16`` (voir ``app/cli/data_metaux_apport.py``).
    """

    __tablename__ = "metaux_apport"
    __table_args__ = (
        UniqueConstraint("designation", name="uq_metaux_apport_designation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    designation: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
        doc="Désignation commerciale du consommable (ex: FOX EV 50).",
    )
    classification: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        doc="Classification / norme AWS (ex: A5.1: E7018-1H4R).",
    )
    fournisseur: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        doc="Fabricant / fournisseur (ex: VOESTALPINE BOHLER WELDING).",
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrganismeNotifie(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Organisme notifié (ON) au titre de la directive PED 2014/68/UE.

    Un ON est identifié par son numéro NANDO à 4 chiffres (ex: ``0062`` pour
    Bureau Veritas). Alimente la liste déroulante « Organisme notifié » du
    formulaire ATTDECR : sélectionner un ON renseigne son numéro. Peuplé par
    ``flask seed`` depuis le fichier source ``NANDO_2014_68_EU.pdf`` (voir
    ``app/cli/data_organismes_notifies.py``).
    """

    __tablename__ = "organismes_notifies"
    __table_args__ = (
        UniqueConstraint("numero", name="uq_organismes_notifies_numero"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    numero: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
        index=True,
        doc="Numéro d'identification NANDO à 4 chiffres (ex: 0062).",
    )
    nom: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nom de l'organisme notifié (ex: BUREAU VERITAS SERVICES).",
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)


class TypeEquipement(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Type d'équipement BFF — classification métier des items (V1.2, D7).

    Alimente la liste déroulante « Type d'équipement » de l'étape Item du
    wizard de création et de la fiche technique. Distinct du champ libre
    ``type_echangeur`` (référence type BFF, ex. « H1 06-01-72 »). Seedé par
    ``flask seed`` (Réfrigérant, HPIN, BHM, RM, SHELL&TUBE…), administrable
    dans l'écran Référentiels.

    À terme (V1.2 Lot 6), chaque type portera aussi son modèle de sommaire
    par défaut (architecture type du dossier constructeur).
    """

    __tablename__ = "types_equipement"
    __table_args__ = (
        UniqueConstraint("libelle", name="uq_types_equipement_libelle"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    libelle: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Libellé du type (ex: Réfrigérant, FAISCEAU de rechange).",
    )
    ordre: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Ordre d'affichage dans les listes déroulantes (0 = premier).",
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)


class Instrument(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Instrument de métrologie soumis à étalonnage périodique.

    Les instruments (manomètres, sondes, comparateurs…) doivent être
    étalonnés périodiquement. Une alerte est déclenchée lorsque la date du
    prochain étalonnage approche.
    """

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        doc="Référence interne BFF de l'instrument (ex: MAN-042).",
    )
    type_instrument: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Type d'appareil (ex: Manomètre, Sonde température, Comparateur).",
    )
    date_etalonnage: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date du dernier étalonnage.",
    )
    date_prochain_etalonnage: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date du prochain étalonnage obligatoire.",
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def statut_expiration(self) -> str:
        """'ok', 'bientot' (≤30 j) ou 'expire' basé sur prochain étalonnage."""
        return _statut_expiration(self.date_prochain_etalonnage)
