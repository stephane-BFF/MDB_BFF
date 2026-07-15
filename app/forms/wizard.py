"""Formulaires WTForms du wizard de création d'affaire (Q1 → Q8).

**HYPOTHÈSE DE TRAVAIL** : la structure Q1-Q8 ci-dessous est basée sur la
logique métier MDB / PED 2014/68/UE (le CDC v3 « Matrice de paramétrage »
était vide à la rédaction). À réviser avec le métier dès que le CDC v3
sera disponible.

Mapping Q → modèle :

    | Étape | Modèle                            | Persistance                |
    |-------|-----------------------------------|----------------------------|
    | Q1    | Identification dossier            | colonnes ``Affaire``        |
    | Q2    | Identification client             | colonnes ``Affaire``        |
    | Q3    | Identification équipement         | colonnes ``Affaire``        |
    | Q4    | Caractéristiques PED              | ``ParametrageAffaire.reponses`` |
    | Q5    | Conditions de service             | ``ParametrageAffaire.reponses`` |
    | Q6    | Procédés de fabrication           | ``ParametrageAffaire.reponses`` |
    | Q7    | Contrôles requis (CND, épreuves)  | ``ParametrageAffaire.reponses`` |
    | Q8    | Récapitulatif + validation finale | (lecture seule)             |
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FloatField,
    IntegerField,
    SelectField,
    SelectMultipleField,
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


class WizardQ1Form(FlaskForm):  # type: ignore[misc]
    """Q1 — Identification du dossier.

    Le n° d'affaire est choisi dans une liste déroulante alimentée par le
    registre général de commande BE (import ``flask import-registre-be``) ;
    ses choix sont peuplés côté route (``form.numero_affaire.choices = …``)
    car ils dépendent des données en base. Si l'affaire n'y figure pas
    encore, la valeur spéciale ``NUMERO_AFFAIRE_MANUEL`` bascule sur les
    champs de saisie manuelle (``numero_affaire_manuel`` / ``item``).

    Le champ ``item`` est un ``SelectField`` sans validation de choix
    (``validate_choice=False``) : ses options réelles sont peuplées en JS via
    l'endpoint JSON ``/affaires/registre-be/items`` une fois l'affaire
    choisie, et sa valeur est revérifiée côté service à la sauvegarde.
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
    item = SelectField(
        _l("N° d'item"),
        validators=[DataRequired(message=_l("Le n° d'item est requis."))],
        validate_choice=False,
        description=_l("4 chiffres — un même n° d'affaire peut porter plusieurs items."),
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

    def validate_item(self, field: SelectField) -> None:  # noqa: D102
        if not field.data or not is_valid_item(field.data):
            raise ValidationError("Le n° d'item doit comporter 4 chiffres (ex: 8975).")


class WizardQ2Form(FlaskForm):  # type: ignore[misc]
    """Q2 — Identification du client et de sa commande."""

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


class WizardQ3Form(FlaskForm):  # type: ignore[misc]
    """Q3 — Identification de l'équipement."""

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


class WizardQ4Form(FlaskForm):  # type: ignore[misc]
    """Q4 — Caractéristiques PED 2014/68/UE.

    Détermine la catégorie et le module de conformité applicables.
    Stocké en JSONB sous les clés ``q4_*``.
    """

    categorie_ped = SelectField(
        _l("Catégorie PED"),
        choices=[
            ("", _l("— Sélectionner —")),
            ("I", _l("I — Risque faible")),
            ("II", _l("II — Risque modéré")),
            ("III", _l("III — Risque élevé")),
            ("IV", _l("IV — Risque très élevé")),
        ],
        validators=[DataRequired(message=_l("La catégorie PED est requise."))],
    )
    module_ped = SelectField(
        _l("Module de conformité"),
        choices=[
            ("", _l("— Sélectionner —")),
            ("A", _l("A — Contrôle interne de fabrication")),
            ("A2", _l("A2 — Contrôle interne + surveillance")),
            ("B+C2", _l("B + C2 — Examen UE de type + contrôle")),
            ("B+D", _l("B + D — Examen UE de type + AQ production")),
            ("B+F", _l("B + F — Examen UE de type + vérif. produit")),
            ("G", _l("G — Vérification CE à l'unité")),
            ("H", _l("H — Assurance qualité complète")),
        ],
        validators=[DataRequired(message=_l("Le module de conformité est requis."))],
    )
    fluide_groupe = SelectField(
        _l("Groupe de fluide"),
        choices=[
            ("", _l("— Sélectionner —")),
            ("1", _l("Groupe 1 — Fluide dangereux")),
            ("2", _l("Groupe 2 — Fluide non dangereux")),
        ],
        validators=[DataRequired(message=_l("Le groupe de fluide est requis."))],
    )
    fluide_nom = StringField(
        _l("Nom du fluide principal"),
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": _l("Eau, huile, vapeur, azote…")},
    )


class WizardQ5Form(FlaskForm):  # type: ignore[misc]
    """Q5 — Conditions de service (pression, température, volume)."""

    ps_bar = FloatField(
        _l("Pression de service PS (bar)"),
        validators=[
            InputRequired(message=_l("PS est requise.")),
            NumberRange(min=0, max=1000),
        ],
        render_kw={"step": "0.1"},
        description=_l(
            "Pression de calcul ; la pression d'épreuve PT = PS × 1.43 sera dérivée."
        ),
    )
    temperature_min_c = FloatField(
        _l("Température minimale (°C)"),
        validators=[InputRequired(), NumberRange(min=-273, max=2000)],
        default=0,
        render_kw={"step": "1"},
    )
    temperature_max_c = FloatField(
        _l("Température maximale (°C)"),
        validators=[InputRequired(), NumberRange(min=-273, max=2000)],
        render_kw={"step": "1"},
    )
    volume_l = FloatField(
        _l("Volume (litres)"),
        validators=[Optional(), NumberRange(min=0, max=1_000_000)],
        render_kw={"step": "0.1"},
    )


class WizardQ6Form(FlaskForm):  # type: ignore[misc]
    """Q6 — Procédés de fabrication.

    Active les formulaires des chapitres C (soudage, dimensions, TTH) et D (CND).
    """

    procedes_soudage = SelectMultipleField(
        _l("Procédés de soudage utilisés"),
        choices=[
            ("141", _l("141 — TIG")),
            ("111", _l("111 — Électrode enrobée (manuel)")),
            ("136", _l("136 — MAG fil fourré")),
            ("121", _l("121 — Sous-flux")),
            ("131", _l("131 — MIG")),
        ],
        validators=[DataRequired(message=_l("Sélectionnez au moins un procédé."))],
        description=_l("Maintenez Ctrl/Cmd pour sélections multiples."),
    )
    tubes_soudes = BooleanField(
        _l("Présence de tubes soudés à la calandre"),
        default=True,
    )
    tth_required = BooleanField(
        _l("Traitement thermique après soudage (TTH) requis"),
        default=False,
        description=_l("Détendage / recuit normalisé selon ASME ou EN."),
    )


class WizardQ7Form(FlaskForm):  # type: ignore[misc]
    """Q7 — Contrôles non destructifs et tests d'épreuve."""

    cnd_methodes = SelectMultipleField(
        _l("Méthodes de CND requises"),
        choices=[
            ("RT", _l("RT — Radiographie")),
            ("UT", _l("UT — Ultrasons")),
            ("PT", _l("PT — Ressuage")),
            ("MT", _l("MT — Magnétoscopie")),
            ("VT", _l("VT — Examen visuel")),
        ],
        description=_l("Maintenez Ctrl/Cmd pour sélections multiples."),
    )
    test_pression = SelectField(
        _l("Test de pression à réaliser"),
        choices=[
            ("hydrostatique", _l("Hydrostatique (HYDR)")),
            ("pneumatique", _l("Pneumatique (AirSav)")),
            ("azote", _l("Étanchéité azote (Azote)")),
        ],
        default="hydrostatique",
        validators=[DataRequired()],
    )
    inspection_client = BooleanField(
        _l("Inspection client / TPI prévue"),
        default=False,
        description=_l("Tierce Partie Indépendante ou inspecteur client présent."),
    )


class WizardQ8Form(FlaskForm):  # type: ignore[misc]
    """Q8 — Récapitulatif et validation finale.

    Affiche l'ensemble des réponses Q1-Q7 pour relecture. Le submit déclenche
    la bascule ``WIZARD_BROUILLON → BROUILLON``.
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
