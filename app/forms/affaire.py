"""Formulaires WTForms pour les affaires (filtres liste, wizard, etc.)."""
from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import Length, Optional

from app.enums import Statut


class AffaireFilterForm(FlaskForm):  # type: ignore[misc]
    """Filtres de la liste des affaires (GET ; CSRF désactivé par défaut Flask-WTF).

    Les filtres sont passés en query-string ``?statut=...&annee=...&q=...``
    pour permettre le partage d'URL et la pagination.
    """

    class Meta:
        # Filtres en GET : pas de CSRF requis (la requête ne modifie rien).
        csrf = False

    statut = SelectField(
        _l("Statut"),
        choices=[("", _l("— Tous —")), *((s.value, s.label) for s in Statut)],
        default="",
        validators=[Optional()],
    )
    annee = StringField(
        _l("Année"),
        validators=[Optional(), Length(max=4)],
        render_kw={"placeholder": "2026", "inputmode": "numeric", "pattern": "[0-9]*"},
    )
    q = StringField(
        _l("Recherche"),
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": _l("N° affaire, client, repère…")},
    )
