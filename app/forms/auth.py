"""Formulaires WTForms pour l'authentification."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):  # type: ignore[misc]
    """Formulaire de connexion locale (email + mot de passe).

    L'auth LDAP/AD (Phase 5) réutilisera ce même formulaire — la résolution
    locale vs LDAP est faite côté route selon ``WINDOWS_AUTH_ENABLED``.
    """

    email = StringField(
        "Adresse e-mail",
        validators=[
            DataRequired(message="L'adresse e-mail est requise."),
            # ``check_deliverability=False`` : pas de résolution DNS MX, indispensable
            # pour les domaines internes type ``.local`` et pour les tests offline.
            Email(message="Format d'e-mail invalide.", check_deliverability=False),
            Length(max=254),
        ],
        render_kw={"autocomplete": "username", "autofocus": True},
    )
    password = PasswordField(
        "Mot de passe",
        validators=[DataRequired(message="Le mot de passe est requis.")],
        render_kw={"autocomplete": "current-password"},
    )
    remember = BooleanField("Se souvenir de moi", default=False)
    submit = SubmitField("Se connecter")
