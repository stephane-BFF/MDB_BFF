"""Formulaire WTForms pour la validation de transition HYDR → VALIDE.

Ce formulaire n'est **pas** utilisé pour le rendu HTML (les champs HYDR sont
rendus manuellement depuis ``Formulaire.data`` pour un meilleur support AJAX).
Il sert uniquement à la validation serveur lors du POST ``/valider``.
"""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional


class HydrValidateForm(FlaskForm):  # type: ignore[misc]
    """Validation finale avant transition BROUILLON → VALIDE.

    Tous les champs obligatoires du PV d'épreuve hydrostatique doivent
    être renseignés avant validation.
    """

    ps_bar = FloatField(
        "Pression de service PS (bar)",
        validators=[
            InputRequired(message="La pression de service PS est requise."),
            NumberRange(min=0.1, max=999, message="PS doit être entre 0,1 et 999 bar."),
        ],
    )
    fluide = SelectField(
        "Fluide d'épreuve",
        choices=[
            ("", "— Sélectionner —"),
            ("eau", "Eau"),
            ("huile", "Huile"),
        ],
        validators=[DataRequired(message="Le fluide d'épreuve est requis.")],
    )
    date_epreuve = StringField(
        "Date de l'épreuve",
        validators=[
            DataRequired(message="La date de l'épreuve est requise."),
            Length(min=10, max=10, message="Format attendu : JJ/MM/AAAA."),
        ],
    )
    duree_minutes = IntegerField(
        "Durée de maintien (minutes)",
        validators=[
            InputRequired(message="La durée de maintien est requise."),
            NumberRange(min=30, message="Durée minimale : 30 minutes."),
        ],
    )
    temperature_c = FloatField(
        "Température du fluide (°C)",
        validators=[Optional(), NumberRange(min=0, max=100)],
    )
    numero_manometre = StringField(
        "N° manomètre",
        validators=[Optional(), Length(max=50)],
    )
    conforme = BooleanField("Résultat conforme")
    observations = StringField(
        "Observations",
        validators=[Optional(), Length(max=2000)],
    )
