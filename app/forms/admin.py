"""Formulaires WTForms — module administration utilisateurs."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional


class UserCreateForm(FlaskForm):
    """Formulaire de création d'un utilisateur BFF."""

    prenom = StringField(
        "Prénom",
        validators=[DataRequired(message="Prénom requis."), Length(max=120)],
    )
    nom = StringField(
        "Nom",
        validators=[DataRequired(message="Nom requis."), Length(max=120)],
    )
    email = EmailField(
        "Adresse e-mail",
        validators=[
            DataRequired(message="E-mail requis."),
            Email(message="Adresse e-mail invalide."),
            Length(max=254),
        ],
    )
    role = SelectField(
        "Rôle",
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(message="Mot de passe requis."),
            Length(min=8, message="Minimum 8 caractères."),
        ],
    )
    password_confirm = PasswordField(
        "Confirmation",
        validators=[
            DataRequired(message="Confirmation requise."),
            EqualTo("password", message="Les mots de passe ne correspondent pas."),
        ],
    )
    submit = SubmitField("Créer l'utilisateur")


class UserEditForm(FlaskForm):
    """Formulaire de modification d'un utilisateur existant."""

    prenom = StringField(
        "Prénom",
        validators=[DataRequired(message="Prénom requis."), Length(max=120)],
    )
    nom = StringField(
        "Nom",
        validators=[DataRequired(message="Nom requis."), Length(max=120)],
    )
    email = EmailField(
        "Adresse e-mail",
        validators=[
            DataRequired(message="E-mail requis."),
            Email(message="Adresse e-mail invalide."),
            Length(max=254),
        ],
    )
    role = SelectField(
        "Rôle",
        validators=[DataRequired()],
    )
    actif = BooleanField("Compte actif")
    submit = SubmitField("Enregistrer")


class ResetPasswordForm(FlaskForm):
    """Formulaire de réinitialisation du mot de passe par l'admin."""

    password = PasswordField(
        "Nouveau mot de passe",
        validators=[
            DataRequired(message="Mot de passe requis."),
            Length(min=8, message="Minimum 8 caractères."),
        ],
    )
    password_confirm = PasswordField(
        "Confirmation",
        validators=[
            DataRequired(message="Confirmation requise."),
            EqualTo("password", message="Les mots de passe ne correspondent pas."),
        ],
    )
    submit = SubmitField("Réinitialiser")
