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

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FloatField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
)


class WizardQ1Form(FlaskForm):  # type: ignore[misc]
    """Q1 — Identification du dossier."""

    annee = IntegerField(
        "Année de l'affaire",
        validators=[
            InputRequired(message="L'année est requise."),
            NumberRange(min=2020, max=2099, message="Année entre 2020 et 2099."),
        ],
        render_kw={"placeholder": "2026"},
    )
    numero_affaire = StringField(
        "Numéro d'affaire",
        validators=[
            DataRequired(message="Le numéro d'affaire est requis."),
            Regexp(
                r"^BN\d{4}-\d{3}$",
                message="Format attendu : BN{AAAA}-{NNN} (ex: BN2026-042).",
            ),
        ],
        render_kw={"placeholder": "BN2026-042"},
    )
    references_internes = StringField(
        "Référence interne BFF",
        validators=[Optional(), Length(max=100)],
        description="« NOS REFERENCES » — code interne BFF (ex: 9541-BN0909).",
    )


class WizardQ2Form(FlaskForm):  # type: ignore[misc]
    """Q2 — Identification du client et de sa commande."""

    client_nom = StringField(
        "Nom du client",
        validators=[
            DataRequired(message="Le nom du client est requis."),
            Length(max=255),
        ],
        render_kw={"placeholder": "TotalEnergies Raffinerie Mitteldeutschland GmbH"},
    )
    references_client = StringField(
        "Référence client",
        validators=[Optional(), Length(max=100)],
        description="« VOS REFERENCES » — n° de commande client (ex: 4551559245).",
    )


class WizardQ3Form(FlaskForm):  # type: ignore[misc]
    """Q3 — Identification de l'équipement."""

    repere = StringField(
        "Repère équipement",
        validators=[
            DataRequired(message="Le repère équipement est requis."),
            Length(max=100),
        ],
        render_kw={"placeholder": "322TK4131"},
        description="Repère utilisé par le client pour identifier l'appareil.",
    )
    type_echangeur = StringField(
        "Type d'échangeur",
        validators=[
            DataRequired(message="Le type d'échangeur est requis."),
            Length(max=100),
        ],
        render_kw={"placeholder": "H1 06-01-72"},
        description="Référence type BFF (ex: H1 06-01-72).",
    )
    nombre = IntegerField(
        "Nombre d'appareils",
        validators=[
            InputRequired(message="Le nombre est requis."),
            NumberRange(min=1, max=999),
        ],
        default=1,
    )
    annee_construction = IntegerField(
        "Année de construction",
        validators=[
            InputRequired(message="L'année de construction est requise."),
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
        "Catégorie PED",
        choices=[
            ("", "— Sélectionner —"),
            ("I", "I — Risque faible"),
            ("II", "II — Risque modéré"),
            ("III", "III — Risque élevé"),
            ("IV", "IV — Risque très élevé"),
        ],
        validators=[DataRequired(message="La catégorie PED est requise.")],
    )
    module_ped = SelectField(
        "Module de conformité",
        choices=[
            ("", "— Sélectionner —"),
            ("A", "A — Contrôle interne de fabrication"),
            ("A2", "A2 — Contrôle interne + surveillance"),
            ("B+C2", "B + C2 — Examen UE de type + contrôle"),
            ("B+D", "B + D — Examen UE de type + AQ production"),
            ("B+F", "B + F — Examen UE de type + vérif. produit"),
            ("G", "G — Vérification CE à l'unité"),
            ("H", "H — Assurance qualité complète"),
        ],
        validators=[DataRequired(message="Le module de conformité est requis.")],
    )
    fluide_groupe = SelectField(
        "Groupe de fluide",
        choices=[
            ("", "— Sélectionner —"),
            ("1", "Groupe 1 — Fluide dangereux"),
            ("2", "Groupe 2 — Fluide non dangereux"),
        ],
        validators=[DataRequired(message="Le groupe de fluide est requis.")],
    )
    fluide_nom = StringField(
        "Nom du fluide principal",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Eau, huile, vapeur, azote…"},
    )


class WizardQ5Form(FlaskForm):  # type: ignore[misc]
    """Q5 — Conditions de service (pression, température, volume)."""

    ps_bar = FloatField(
        "Pression de service PS (bar)",
        validators=[
            InputRequired(message="PS est requise."),
            NumberRange(min=0, max=1000),
        ],
        render_kw={"step": "0.1"},
        description="Pression de calcul ; la pression d'épreuve PT = PS × 1.43 sera dérivée.",
    )
    temperature_min_c = FloatField(
        "Température minimale (°C)",
        validators=[InputRequired(), NumberRange(min=-273, max=2000)],
        default=0,
        render_kw={"step": "1"},
    )
    temperature_max_c = FloatField(
        "Température maximale (°C)",
        validators=[InputRequired(), NumberRange(min=-273, max=2000)],
        render_kw={"step": "1"},
    )
    volume_l = FloatField(
        "Volume (litres)",
        validators=[Optional(), NumberRange(min=0, max=1_000_000)],
        render_kw={"step": "0.1"},
    )


class WizardQ6Form(FlaskForm):  # type: ignore[misc]
    """Q6 — Procédés de fabrication.

    Active les formulaires des chapitres C (soudage, dimensions, TTH) et D (CND).
    """

    procedes_soudage = SelectMultipleField(
        "Procédés de soudage utilisés",
        choices=[
            ("141", "141 — TIG"),
            ("111", "111 — Électrode enrobée (manuel)"),
            ("136", "136 — MAG fil fourré"),
            ("121", "121 — Sous-flux"),
            ("131", "131 — MIG"),
        ],
        validators=[DataRequired(message="Sélectionnez au moins un procédé.")],
        description="Maintenez Ctrl/Cmd pour sélections multiples.",
    )
    tubes_soudes = BooleanField(
        "Présence de tubes soudés à la calandre",
        default=True,
    )
    tth_required = BooleanField(
        "Traitement thermique après soudage (TTH) requis",
        default=False,
        description="Détendage / recuit normalisé selon ASME ou EN.",
    )


class WizardQ7Form(FlaskForm):  # type: ignore[misc]
    """Q7 — Contrôles non destructifs et tests d'épreuve."""

    cnd_methodes = SelectMultipleField(
        "Méthodes de CND requises",
        choices=[
            ("RT", "RT — Radiographie"),
            ("UT", "UT — Ultrasons"),
            ("PT", "PT — Ressuage"),
            ("MT", "MT — Magnétoscopie"),
            ("VT", "VT — Examen visuel"),
        ],
        description="Maintenez Ctrl/Cmd pour sélections multiples.",
    )
    test_pression = SelectField(
        "Test de pression à réaliser",
        choices=[
            ("hydrostatique", "Hydrostatique (HYDR)"),
            ("pneumatique", "Pneumatique (AirSav)"),
            ("azote", "Étanchéité azote (Azote)"),
        ],
        default="hydrostatique",
        validators=[DataRequired()],
    )
    inspection_client = BooleanField(
        "Inspection client / TPI prévue",
        default=False,
        description="Tierce Partie Indépendante ou inspecteur client présent.",
    )


class WizardQ8Form(FlaskForm):  # type: ignore[misc]
    """Q8 — Récapitulatif et validation finale.

    Affiche l'ensemble des réponses Q1-Q7 pour relecture. Le submit déclenche
    la bascule ``WIZARD_BROUILLON → BROUILLON``.
    """

    confirmation = BooleanField(
        "Je confirme l'exactitude des informations saisies",
        validators=[DataRequired(message="Vous devez confirmer pour finaliser.")],
    )
    commentaire = TextAreaField(
        "Commentaire (optionnel)",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3},
    )
