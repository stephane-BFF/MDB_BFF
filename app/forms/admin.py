"""Formulaires WTForms — module administration utilisateurs."""
from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional


class UserCreateForm(FlaskForm):
    """Formulaire de création d'un utilisateur BFF."""

    prenom = StringField(
        _l("Prénom"),
        validators=[DataRequired(message=_l("Prénom requis.")), Length(max=120)],
    )
    nom = StringField(
        _l("Nom"),
        validators=[DataRequired(message=_l("Nom requis.")), Length(max=120)],
    )
    email = EmailField(
        _l("Adresse e-mail"),
        validators=[
            DataRequired(message=_l("E-mail requis.")),
            Email(message=_l("Adresse e-mail invalide.")),
            Length(max=254),
        ],
    )
    role = SelectField(
        _l("Rôle"),
        validators=[DataRequired()],
    )
    password = PasswordField(
        _l("Mot de passe"),
        validators=[
            DataRequired(message=_l("Mot de passe requis.")),
            Length(min=8, message=_l("Minimum 8 caractères.")),
        ],
    )
    password_confirm = PasswordField(
        _l("Confirmation"),
        validators=[
            DataRequired(message=_l("Confirmation requise.")),
            EqualTo("password", message=_l("Les mots de passe ne correspondent pas.")),
        ],
    )
    submit = SubmitField(_l("Créer l'utilisateur"))


class UserEditForm(FlaskForm):
    """Formulaire de modification d'un utilisateur existant."""

    prenom = StringField(
        _l("Prénom"),
        validators=[DataRequired(message=_l("Prénom requis.")), Length(max=120)],
    )
    nom = StringField(
        _l("Nom"),
        validators=[DataRequired(message=_l("Nom requis.")), Length(max=120)],
    )
    email = EmailField(
        _l("Adresse e-mail"),
        validators=[
            DataRequired(message=_l("E-mail requis.")),
            Email(message=_l("Adresse e-mail invalide.")),
            Length(max=254),
        ],
    )
    role = SelectField(
        _l("Rôle"),
        validators=[DataRequired()],
    )
    actif = BooleanField(_l("Compte actif"))
    submit = SubmitField(_l("Enregistrer"))


class ResetPasswordForm(FlaskForm):
    """Formulaire de réinitialisation du mot de passe par l'admin."""

    password = PasswordField(
        _l("Nouveau mot de passe"),
        validators=[
            DataRequired(message=_l("Mot de passe requis.")),
            Length(min=8, message=_l("Minimum 8 caractères.")),
        ],
    )
    password_confirm = PasswordField(
        _l("Confirmation"),
        validators=[
            DataRequired(message=_l("Confirmation requise.")),
            EqualTo("password", message=_l("Les mots de passe ne correspondent pas.")),
        ],
    )
    submit = SubmitField(_l("Réinitialiser"))
