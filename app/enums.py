"""Énumérations Python typées pour les valeurs métier MDB BFF.

Toutes les comparaisons doivent utiliser les membres d'enum directement
(ex: ``user.role is Role.ADMIN``), jamais les valeurs string sous-jacentes.

Les classes héritent de ``StrEnum`` (Python 3.11+) afin que la valeur stockée
en base et sérialisée en JSON soit la chaîne lisible (``"admin"``,
``"wizard_brouillon"``, ``"JP0"``…). SQLAlchemy peut mapper directement ces
enums via ``sa.Enum(Role)``.
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Rôles utilisateurs BFF — 5 niveaux d'autorisation cumulatifs.

    Hiérarchie : LECTEUR < REDACTEUR < VERIFICATEUR < APPROBATEUR < ADMIN.
    Voir matrice des permissions dans ``CLAUDE.md``.
    """

    LECTEUR = "lecteur"
    REDACTEUR = "redacteur"
    VERIFICATEUR = "verificateur"
    APPROBATEUR = "approbateur"
    ADMIN = "admin"

    @property
    def label(self) -> str:
        """Libellé français pour affichage UI."""
        return _ROLE_LABELS[self]


_ROLE_LABELS: dict[Role, str] = {
    Role.LECTEUR: "Lecteur",
    Role.REDACTEUR: "Rédacteur",
    Role.VERIFICATEUR: "Vérificateur",
    Role.APPROBATEUR: "Approbateur",
    Role.ADMIN: "Administrateur",
}


class Statut(StrEnum):
    """Statut workflow d'une affaire ou d'un formulaire.

    Workflow standard d'un formulaire :
        BROUILLON → SOUMIS → (REJETE → BROUILLON) → VALIDE → SIGNE

    Workflow d'une affaire :
        WIZARD_BROUILLON → BROUILLON → SOUMIS → (REJETE → BROUILLON)
                                     → VALIDE → SIGNE → CLOTUREE → ARCHIVEE

    Transitions notables :
        - WIZARD_BROUILLON → BROUILLON : sortie du wizard (récapitulatif validé).
        - SOUMIS → REJETE : Vérificateur renvoie le document pour correction.
        - REJETE → BROUILLON : Rédacteur reprend la main pour modifier.
        - SIGNE → CLOTUREE : affaire terminée (tous formulaires signés).
        - CLOTUREE → ARCHIVEE : archivage long-terme.

    Les transitions sont irréversibles sauf intervention Admin.
    """

    WIZARD_BROUILLON = "wizard_brouillon"
    BROUILLON = "brouillon"
    SOUMIS = "soumis"
    REJETE = "rejete"
    VALIDE = "valide"
    SIGNE = "signe"
    CLOTUREE = "cloturee"
    ARCHIVEE = "archivee"

    @property
    def label(self) -> str:
        """Libellé français pour affichage UI."""
        return _STATUT_LABELS[self]

    @property
    def is_editable(self) -> bool:
        """True si le contenu peut encore être modifié (hors Admin).

        Les statuts éditables sont ceux où le Rédacteur peut intervenir :
        WIZARD_BROUILLON, BROUILLON, REJETE (retour pour correction).
        """
        return self in _STATUTS_EDITABLES

    @property
    def is_final(self) -> bool:
        """True si le statut est terminal pour une affaire (CLOTUREE, ARCHIVEE)."""
        return self in (Statut.CLOTUREE, Statut.ARCHIVEE)


_STATUT_LABELS: dict[Statut, str] = {
    Statut.WIZARD_BROUILLON: "Wizard en cours",
    Statut.BROUILLON: "Brouillon",
    Statut.SOUMIS: "Soumis",
    Statut.REJETE: "Rejeté",
    Statut.VALIDE: "Validé",
    Statut.SIGNE: "Signé",
    Statut.CLOTUREE: "Clôturée",
    Statut.ARCHIVEE: "Archivée",
}

_STATUTS_EDITABLES: frozenset[Statut] = frozenset(
    {Statut.WIZARD_BROUILLON, Statut.BROUILLON, Statut.REJETE}
)


class StatutWizard(StrEnum):
    """Étape max atteinte du wizard de création d'affaire (Q1 → Q4).

    Stockée sur ``Affaire.statut_wizard`` tant que ``Affaire.statut`` vaut
    ``Statut.WIZARD_BROUILLON``. Passe à ``None`` quand le wizard est terminé.

    Depuis la V1.2 (wizard raccourci — voir
    ``docs/STRATEGIE_AMELIORATIONS_V1.2_2026-07-16.md``), le wizard ne compte
    plus que 4 étapes : les ex-Q4→Q7 (fluide, conditions de service,
    procédés, contrôles) sont saisies après création, dans la fiche
    technique de l'item. La valeur stockée est l'étape **max atteinte** (les
    étapes antérieures restent librement navigables), plus l'étape courante.
    """

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"

    @property
    def numero(self) -> int:
        """Numéro de l'étape (1 à 4)."""
        return int(self.value[1:])

    @property
    def label(self) -> str:
        """Nom court de l'étape, affiché sous la pastille du stepper."""
        return _WIZARD_LABELS[self]

    @property
    def is_last(self) -> bool:
        """True si c'est la dernière étape du wizard (Q4 — récapitulatif)."""
        return self is StatutWizard.Q4


_WIZARD_LABELS: dict[StatutWizard, str] = {
    StatutWizard.Q1: "Affaire",
    StatutWizard.Q2: "Item",
    StatutWizard.Q3: "Réglementation",
    StatutWizard.Q4: "Récapitulatif",
}


class Chapitre(StrEnum):
    """Chapitres A–G organisant les 27 formulaires du dossier qualité.

    Libellés repris du sommaire officiel BFF (modèle ``MDB-9541-BN0909.pdf``).
    Voir la table « Les 27 Formulaires » dans ``CLAUDE.md`` pour la
    répartition des codes formulaires par chapitre.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"

    @property
    def label(self) -> str:
        """Libellé français officiel du chapitre (sommaire MDB)."""
        return _CHAPITRE_LABELS[self]

    @property
    def label_en(self) -> str:
        """Libellé anglais officiel du chapitre (export international)."""
        return _CHAPITRE_LABELS_EN[self]


_CHAPITRE_LABELS: dict[Chapitre, str] = {
    Chapitre.A: "Certificat de conformité",
    Chapitre.B: "Notes de calcul",
    Chapitre.C: (
        "Homologation des procédés de soudage et d'assemblage permanent — "
        "Qualification des soudeurs et des opérateurs"
    ),
    Chapitre.D: "Liste des matériaux utilisés — Certificats",
    Chapitre.E: "Cahier de contrôle",
    Chapitre.F: "Plan de l'appareil",
    Chapitre.G: "Manuel d'installation, de mise en route et de maintenance",
}

_CHAPITRE_LABELS_EN: dict[Chapitre, str] = {
    Chapitre.A: "Certificate of conformity",
    Chapitre.B: "Calculation sheet",
    Chapitre.C: (
        "Procedure qualification record and permanent assembly qualification — "
        "Welder's and operator's qualification"
    ),
    Chapitre.D: "Bill of material used — Certificates",
    Chapitre.E: "Control documents",
    Chapitre.F: "Drawings",
    Chapitre.G: "Installation, Operation and Maintenance Manual",
}


class JalonCode(StrEnum):
    """Codes des 7 jalons projet (JP0 à JP6).

    Un jalon ne peut être franchi que si tous ses prérequis (formulaires)
    sont au statut ``Statut.VALIDE``. Voir la logique dans ``services/jalons``.
    """

    JP0 = "JP0"
    JP1 = "JP1"
    JP2 = "JP2"
    JP3 = "JP3"
    JP4 = "JP4"
    JP5 = "JP5"
    JP6 = "JP6"

    @property
    def numero(self) -> int:
        """Numéro du jalon (0 à 6)."""
        return int(self.value[2:])


class StatutJalon(StrEnum):
    """Statut d'un jalon JP0-JP6.

    Transitions autorisées :
        EN_ATTENTE → EN_COURS → FRANCHI
        EN_COURS   → EN_RETARD (si date_prevue dépassée)
        EN_COURS / EN_RETARD → BLOQUE (si prérequis manquants)
        BLOQUE → EN_COURS (lorsque les prérequis sont satisfaits)
    """

    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    FRANCHI = "franchi"
    EN_RETARD = "en_retard"
    BLOQUE = "bloque"

    @property
    def label(self) -> str:
        """Libellé français pour l'UI."""
        return _STATUT_JALON_LABELS[self]

    @property
    def badge_class(self) -> str:
        """Classe Bootstrap du badge d'état."""
        return _STATUT_JALON_BADGES[self]


_STATUT_JALON_LABELS: dict[StatutJalon, str] = {
    StatutJalon.EN_ATTENTE: "En attente",
    StatutJalon.EN_COURS: "En cours",
    StatutJalon.FRANCHI: "Franchi",
    StatutJalon.EN_RETARD: "En retard",
    StatutJalon.BLOQUE: "Bloqué",
}

_STATUT_JALON_BADGES: dict[StatutJalon, str] = {
    StatutJalon.EN_ATTENTE: "bg-secondary",
    StatutJalon.EN_COURS: "bg-primary",
    StatutJalon.FRANCHI: "bg-success",
    StatutJalon.EN_RETARD: "bg-warning text-dark",
    StatutJalon.BLOQUE: "bg-danger",
}
