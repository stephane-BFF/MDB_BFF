"""Formulaires WTForms du wizard de création d'affaire (V1.2 — 4 étapes).

Wizard raccourci (voir ``docs/STRATEGIE_AMELIORATIONS_V1.2_2026-07-16.md``,
Lot 1) : le dossier est créé dès les informations d'identification et la
réglementation renseignées. Les ex-étapes Q4→Q7 (fluide, conditions de
service, procédés, contrôles) sont saisies après création, dans la fiche
technique de l'item (Lot 2).

Mapping étape → modèle :

    | Étape | Nom            | Contenu                             | Persistance             |
    |-------|----------------|-------------------------------------|-------------------------|
    | Q1    | Affaire        | année, n° affaire, client, commande | colonnes ``Affaire``    |
    | Q2    | Item           | n° item, repère, types, nombre      | colonnes ``Affaire``    |
    | Q3    | Réglementation | DESP, STAMP U, catégorie, module    | JSONB (clés ``q4_*``)   |
    | Q4    | Récapitulatif  | confirmation finale                 | (lecture seule)         |

⚠️ Contrat de stockage (décision D2) : l'étape Réglementation écrit sous les
clés JSONB historiques ``q4_desp`` / ``q4_stamp_u`` / ``q4_categorie_ped`` /
``q4_module_ped`` — consommées par ATTDECR, ETATDESC… Ne pas renommer.
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
    ValidationError,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
)

from app.utils.validators import is_valid_item, is_valid_numero_affaire

# Valeur spéciale du champ ``numero_affaire`` déclenchant la saisie manuelle
# de secours, pour les affaires pas encore répertoriées dans le registre BE.
NUMERO_AFFAIRE_MANUEL = "__manuel__"


# ── Référentiel PED 2014/68/UE — catégories et modules de conformité ──────
#
# Catégories de risque : I à IV sont soumises à évaluation de conformité ;
# ``Art.4.3`` couvre les équipements conçus selon les règles de l'art (article
# 4 §3 — sous les seuils, sans marquage CE ni module) ; ``N/A`` (historique)
# désigne les équipements non destinés au marché européen — depuis la V1.2
# ce cas est exprimé par « DESP = non » (le champ catégorie est alors ignoré).
CATEGORIE_ART_43 = "Art.4.3"
CATEGORIE_NA = "N/A"

# Catégories pour lesquelles un module de conformité s'applique réellement.
CATEGORIES_AVEC_MODULE: frozenset[str] = frozenset({"I", "II", "III", "IV"})

# Libellés des modules de conformité (Annexe III PED 2014/68/UE).
MODULES_PED: dict[str, str] = {
    "A": "A — Contrôle interne de la fabrication",
    "A2": "A2 — Contrôle interne + contrôles supervisés à intervalles aléatoires",
    "B+C2": "B + C2 — Examen UE de type + conformité au type (essais supervisés)",
    "B+D": "B + D — Examen UE de type + assurance qualité de la production",
    "B+E": "B + E — Examen UE de type + assurance qualité du produit",
    "B+F": "B + F — Examen UE de type + vérification sur produit",
    "D1": "D1 — Assurance qualité de la production",
    "E1": "E1 — Assurance qualité du contrôle et de l'essai finals",
    "G": "G — Vérification à l'unité",
    "H": "H — Assurance complète de la qualité",
    "H1": "H1 — Assurance complète de la qualité + examen de la conception",
}

# Modules prévus pour chaque catégorie de risque (tableaux d'évaluation de la
# conformité, Annexe II PED 2014/68/UE).
MODULES_PAR_CATEGORIE: dict[str, list[str]] = {
    "I": ["A"],
    "II": ["A2", "D1", "E1"],
    "III": ["B+C2", "B+D", "B+E", "B+F", "H"],
    "IV": ["B+D", "B+F", "G", "H1"],
}

# L'article 14 de la PED 2014/68/UE autorise le fabricant à appliquer une
# procédure prévue pour une catégorie SUPÉRIEURE : les modules des catégories
# au-dessus sont donc également recevables (arbitrage V1.2, demande n°5).
_ORDRE_CATEGORIES = ["I", "II", "III", "IV"]


def _modules_superieurs(categorie: str) -> list[str]:
    """Modules des catégories strictement supérieures à ``categorie``.

    Dédoublonnés (un module déjà prévu pour la catégorie n'est pas répété),
    ordonnés comme ``MODULES_PED`` pour un affichage stable.
    """
    usuels = set(MODULES_PAR_CATEGORIE.get(categorie, []))
    rang = _ORDRE_CATEGORIES.index(categorie)
    superieurs = {
        module
        for cat in _ORDRE_CATEGORIES[rang + 1 :]
        for module in MODULES_PAR_CATEGORIE[cat]
    } - usuels
    return [m for m in MODULES_PED if m in superieurs]


# Modules des catégories supérieures, par catégorie (pour les <optgroup> UI).
MODULES_SUPERIEURS_PAR_CATEGORIE: dict[str, list[str]] = {
    cat: _modules_superieurs(cat) for cat in _ORDRE_CATEGORIES
}

# Ensemble des modules recevables par catégorie (usuels + supérieurs) —
# référence unique de la validation serveur.
MODULES_AUTORISES_PAR_CATEGORIE: dict[str, list[str]] = {
    cat: MODULES_PAR_CATEGORIE[cat] + MODULES_SUPERIEURS_PAR_CATEGORIE[cat]
    for cat in _ORDRE_CATEGORIES
}


class WizardQ1Form(FlaskForm):  # type: ignore[misc]
    """Q1 — Affaire : identification et informations génériques.

    Le n° d'affaire est choisi dans une liste déroulante alimentée par le
    registre général de commande BE (import ``flask import-registre-be``) ;
    ses choix sont peuplés côté route car ils dépendent des données en base.
    Si l'affaire n'y figure pas encore, la valeur spéciale
    ``NUMERO_AFFAIRE_MANUEL`` bascule sur le champ de saisie manuelle.

    Le client et la référence de commande sont préremplis en JS depuis le
    registre à la sélection du n° d'affaire (modifiables ensuite).
    """

    annee = IntegerField(
        _l("Année de l'affaire"),
        validators=[
            InputRequired(message=_l("L'année est requise.")),
            NumberRange(min=2020, max=2099, message=_l("Année entre 2020 et 2099.")),
        ],
        render_kw={"placeholder": "2026"},
    )
    numero_affaire = SelectField(
        _l("N° d'affaire"),
        validators=[DataRequired(message=_l("Le n° d'affaire est requis."))],
        description=_l("Issu du registre général de commande BE."),
    )
    numero_affaire_manuel = StringField(
        _l("N° d'affaire (saisie manuelle)"),
        validators=[Optional(), Length(max=10)],
        filters=[lambda v: v.strip().upper() if v else v],
        render_kw={"placeholder": "BN0811"},
        description=_l("Uniquement si l'affaire n'est pas encore dans le registre BE."),
    )
    client_nom = StringField(
        _l("Nom du client"),
        validators=[
            DataRequired(message=_l("Le nom du client est requis.")),
            Length(max=255),
        ],
        render_kw={"placeholder": "TotalEnergies Raffinerie Mitteldeutschland GmbH"},
    )
    references_client = StringField(
        _l("Référence client"),
        validators=[Optional(), Length(max=100)],
        description=_l("« VOS REFERENCES » — n° de commande client (ex: 4551559245)."),
    )

    def validate_numero_affaire_manuel(
        self, field: StringField
    ) -> None:  # noqa: D102 — validateur WTForms conventionnel
        if self.numero_affaire.data != NUMERO_AFFAIRE_MANUEL:
            return
        if not field.data:
            raise ValidationError("Le n° d'affaire manuel est requis.")
        if not is_valid_numero_affaire(field.data):
            raise ValidationError("Format attendu : BN ou BP + 4 chiffres (ex: BN0811).")


class WizardQ2Form(FlaskForm):  # type: ignore[misc]
    """Q2 — Item : identification de l'équipement du dossier.

    Le champ ``item`` est un ``SelectField`` sans validation de choix
    (``validate_choice=False``) : ses options réelles sont peuplées en JS via
    l'endpoint JSON ``/affaires/registre-be/items`` (le n° d'affaire est déjà
    connu), et sa valeur est revérifiée côté service à la sauvegarde. La
    sélection d'un item préremplit repère / type / nombre depuis le registre.
    """

    item = SelectField(
        _l("N° d'item"),
        validators=[DataRequired(message=_l("Le n° d'item est requis."))],
        validate_choice=False,
        description=_l("4 chiffres — un même n° d'affaire peut porter plusieurs items."),
    )
    repere = StringField(
        _l("Repère équipement"),
        validators=[
            DataRequired(message=_l("Le repère équipement est requis.")),
            Length(max=100),
        ],
        render_kw={"placeholder": "322TK4131"},
        description=_l("Repère utilisé par le client pour identifier l'appareil."),
    )
    type_echangeur = StringField(
        _l("Type d'échangeur"),
        validators=[
            DataRequired(message=_l("Le type d'échangeur est requis.")),
            Length(max=100),
        ],
        render_kw={"placeholder": "H1 06-01-72"},
        description=_l("Référence type BFF (ex: H1 06-01-72)."),
    )
    type_equipement_id = SelectField(
        _l("Type d'équipement"),
        validators=[DataRequired(message=_l("Le type d'équipement est requis."))],
        description=_l("Classification BFF (Réfrigérant, HPIN, BHM, SHELL&TUBE…)."),
    )
    nombre = IntegerField(
        _l("Nombre d'appareils"),
        validators=[
            InputRequired(message=_l("Le nombre est requis.")),
            NumberRange(min=1, max=999),
        ],
        default=1,
    )
    annee_construction = IntegerField(
        _l("Année de construction"),
        validators=[
            InputRequired(message=_l("L'année de construction est requise.")),
            NumberRange(min=2020, max=2099),
        ],
        render_kw={"placeholder": "2026"},
    )

    def validate_item(self, field: SelectField) -> None:  # noqa: D102
        if not field.data or not is_valid_item(field.data):
            raise ValidationError("Le n° d'item doit comporter 4 chiffres (ex: 8975).")


class WizardQ3Form(FlaskForm):  # type: ignore[misc]
    """Q3 — Réglementation applicable (DESP / STAMP U).

    Préremplie depuis les colonnes R/S/T du registre BE quand l'item en est
    issu. Stockée en JSONB sous les clés historiques ``q4_*`` (décision D2).

    Logique conditionnelle :
        - ``desp`` / ``stamp_u`` sont des cases indépendantes (les deux
          peuvent s'appliquer, ou aucune — équipement hors marché européen).
        - La catégorie n'est requise que si DESP ; ``Art.4.3`` = soumis à la
          directive mais sous les seuils (sans module ni marquage CE).
        - Le module n'est requis que pour les catégories I–IV, et doit être
          recevable : modules de la catégorie **ou d'une catégorie
          supérieure** (art. 14 PED — voir ``MODULES_AUTORISES_PAR_CATEGORIE``).
    """

    desp = BooleanField(
        _l("Soumis à la DESP 2014/68/UE"),
        description=_l("Directive des équipements sous pression (marché UE)."),
    )
    stamp_u = BooleanField(
        _l("Stamp U (ASME)"),
        description=_l("Code ASME Section VIII — marché nord-américain."),
    )
    categorie_ped = SelectField(
        _l("Catégorie de risque"),
        choices=[
            ("", _l("— Sélectionner —")),
            ("I", _l("I — Risque faible")),
            ("II", _l("II — Risque modéré")),
            ("III", _l("III — Risque élevé")),
            ("IV", _l("IV — Risque très élevé")),
            (CATEGORIE_ART_43, _l("Art. 4.3 — Sous les seuils (règles de l'art)")),
        ],
        description=_l("Requise si DESP. Vérifiable ensuite dans la fiche technique."),
    )
    module_ped = SelectField(
        _l("Module d'évaluation de la conformité"),
        choices=[("", _l("— Sélectionner —"))]
        + [(code, label) for code, label in MODULES_PED.items()],
        description=_l(
            "Modules de la catégorie, ou d'une catégorie supérieure "
            "(art. 14 PED). Sans objet pour Art. 4.3."
        ),
    )

    def validate_categorie_ped(self, field: SelectField) -> None:  # noqa: D102
        if self.desp.data and not field.data:
            raise ValidationError("La catégorie de risque est requise si DESP.")

    def validate_module_ped(self, field: SelectField) -> None:  # noqa: D102
        if not self.desp.data:
            # Hors DESP, le module est sans objet : toute valeur est ignorée.
            return
        categorie = self.categorie_ped.data
        if categorie not in CATEGORIES_AVEC_MODULE:
            # Art.4.3 : sous les seuils, pas de module d'évaluation.
            return
        if not field.data:
            raise ValidationError(
                "Le module de conformité est requis pour cette catégorie."
            )
        autorises = MODULES_AUTORISES_PAR_CATEGORIE.get(categorie, [])
        if field.data not in autorises:
            raise ValidationError(
                f"Module non recevable pour la catégorie {categorie} — "
                f"choix possibles : {', '.join(autorises)}."
            )


class WizardQ4Form(FlaskForm):  # type: ignore[misc]
    """Q4 — Récapitulatif et création du dossier.

    Affiche l'ensemble des réponses Q1-Q3 pour relecture. Le submit déclenche
    la bascule ``WIZARD_BROUILLON → BROUILLON`` : le dossier est créé, la
    fiche technique (ex-Q4→Q7) pourra être complétée ensuite.
    """

    confirmation = BooleanField(
        _l("Je confirme l'exactitude des informations saisies"),
        validators=[DataRequired(message=_l("Vous devez confirmer pour finaliser."))],
    )
    commentaire = TextAreaField(
        _l("Commentaire (optionnel)"),
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3},
    )
