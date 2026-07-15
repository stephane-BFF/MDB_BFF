"""Formulaire WTForms pour la validation de transition HYDR → VALIDE.

Ce formulaire n'est **pas** utilisé pour le rendu HTML (les champs HYDR sont
rendus manuellement depuis ``Formulaire.data`` pour un meilleur support AJAX).
Il sert uniquement à la validation serveur lors du POST ``/valider``.
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional


class HydrValidateForm(FlaskForm):  # type: ignore[misc]
    """Validation finale avant transition BROUILLON → VALIDE.

    Tous les champs obligatoires du PV d'épreuve hydrostatique doivent
    être renseignés avant validation.
    """

    ps_bar = FloatField(
        _l("Pression de service PS (bar)"),
        validators=[
            InputRequired(message=_l("La pression de service PS est requise.")),
            NumberRange(min=0.1, max=999, message=_l("PS doit être entre 0,1 et 999 bar.")),
        ],
    )
    fluide = SelectField(
        _l("Fluide d'épreuve"),
        choices=[
            ("", _l("— Sélectionner —")),
            ("eau", _l("Eau")),
            ("huile", _l("Huile")),
        ],
        validators=[DataRequired(message=_l("Le fluide d'épreuve est requis."))],
    )
    date_epreuve = StringField(
        _l("Date de l'épreuve"),
        validators=[
            DataRequired(message=_l("La date de l'épreuve est requise.")),
            Length(min=10, max=10, message=_l("Format attendu : JJ/MM/AAAA.")),
        ],
    )
    duree_minutes = IntegerField(
        _l("Durée de maintien (minutes)"),
        validators=[
            InputRequired(message=_l("La durée de maintien est requise.")),
            NumberRange(min=30, message=_l("Durée minimale : 30 minutes.")),
        ],
    )
    temperature_c = FloatField(
        _l("Température du fluide (°C)"),
        validators=[Optional(), NumberRange(min=0, max=100)],
    )
    numero_manometre = StringField(
        _l("N° manomètre"),
        validators=[Optional(), Length(max=50)],
    )
    conforme = BooleanField(_l("Résultat conforme"))
    observations = StringField(
        _l("Observations"),
        validators=[Optional(), Length(max=2000)],
    )
