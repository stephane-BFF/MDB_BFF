"""Formulaires WTForms pour l'authentification."""
from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp


class LoginForm(FlaskForm):  # type: ignore[misc]
    """Formulaire de connexion locale (email + mot de passe).

    L'auth LDAP/AD (Phase 5) réutilisera ce même formulaire — la résolution
    locale vs LDAP est faite côté route selon ``WINDOWS_AUTH_ENABLED``.
    """

    email = StringField(
        _l("Adresse e-mail"),
        validators=[
            DataRequired(message=_l("L'adresse e-mail est requise.")),
            # ``check_deliverability=False`` : pas de résolution DNS MX, indispensable
            # pour les domaines internes type ``.local`` et pour les tests offline.
            Email(message=_l("Format d'e-mail invalide."), check_deliverability=False),
            Length(max=254),
        ],
        render_kw={"autocomplete": "username", "autofocus": True},
    )
    password = PasswordField(
        _l("Mot de passe"),
        validators=[DataRequired(message=_l("Le mot de passe est requis."))],
        render_kw={"autocomplete": "current-password"},
    )
    remember = BooleanField(_l("Se souvenir de moi"), default=False)
    submit = SubmitField(_l("Se connecter"))


class TwoFactorForm(FlaskForm):  # type: ignore[misc]
    """Second facteur : code TOTP à 6 chiffres OU code de secours à 8 chiffres.

    Le champ accepte 6 à 8 chiffres ; la route tente d'abord le TOTP (6),
    puis le code de secours (8) si le TOTP échoue.
    """

    code = StringField(
        _l("Code d'authentification"),
        validators=[
            DataRequired(message=_l("Le code est requis.")),
            Regexp(r"^\d{6,8}$", message=_l("Le code doit comporter 6 à 8 chiffres.")),
        ],
        render_kw={
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "autofocus": True,
            "placeholder": "123456",
        },
    )
    submit = SubmitField(_l("Vérifier"))


class TotpSetupForm(FlaskForm):  # type: ignore[misc]
    """Confirmation d'enrôlement 2FA : premier code TOTP à 6 chiffres."""

    code = StringField(
        _l("Code à 6 chiffres"),
        validators=[
            DataRequired(message=_l("Saisissez le code affiché par votre application.")),
            Regexp(r"^\d{6}$", message=_l("Le code doit comporter 6 chiffres.")),
        ],
        render_kw={
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "autofocus": True,
            "placeholder": "123456",
        },
    )
    submit = SubmitField(_l("Activer la double authentification"))
