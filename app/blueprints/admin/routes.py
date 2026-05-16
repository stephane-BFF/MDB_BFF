"""Routes du module Admin — gestion des utilisateurs et journal d'audit global.

URL prefix : ``/admin``

Accès restreint au rôle ADMIN pour toutes les routes.

Routes :
    GET  /                       — liste des utilisateurs
    GET  /users/new              — formulaire création
    POST /users/new              — créer un utilisateur
    GET  /users/<id>/edit        — formulaire édition
    POST /users/<id>/edit        — modifier un utilisateur
    POST /users/<id>/toggle      — activer / désactiver (JSON)
    GET  /users/<id>/reset-pwd   — formulaire reset mot de passe
    POST /users/<id>/reset-pwd   — réinitialiser le mot de passe
    GET  /audit                  — journal d'audit global paginé
"""
from __future__ import annotations

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload
from werkzeug.wrappers.response import Response

from app.blueprints.admin import bp
from app.enums import Role
from app.extensions import db
from app.forms.admin import ResetPasswordForm, UserCreateForm, UserEditForm
from app.models.audit import AuditTrail
from app.models.user import User
from app.utils.decorators import role_required

_ADMIN_ONLY = (Role.ADMIN,)
_ROLE_CHOICES = [(r.value, r.label) for r in Role]

_PER_PAGE_USERS = 50
_PER_PAGE_AUDIT = 50


# ── Liste utilisateurs ────────────────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
@role_required(*_ADMIN_ONLY)
def index() -> str:
    """Liste tous les utilisateurs avec leurs rôles et statuts."""
    users = db.session.query(User).order_by(User.nom, User.prenom).all()
    return render_template("admin/index.html", users=users, roles=list(Role))


# ── Création d'un utilisateur ─────────────────────────────────────────────


@bp.route("/users/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_ADMIN_ONLY)
def user_create() -> str | Response:
    """Formulaire de création d'un nouvel utilisateur."""
    form = UserCreateForm()
    form.role.choices = _ROLE_CHOICES

    if form.validate_on_submit():
        existing = db.session.query(User).filter_by(email=form.email.data).first()
        if existing:
            flash("Cette adresse e-mail est déjà utilisée.", "error")
            return render_template("admin/user_form.html", form=form, title="Nouvel utilisateur")

        user = User(
            prenom=form.prenom.data.strip(),
            nom=form.nom.data.strip(),
            email=form.email.data.strip().lower(),
            role=Role(form.role.data),
            actif=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)

        AuditTrail.log(
            "user.created",
            user=_current_user(),
            entity_type="user",
            entity_id=None,
            new_value=user.email,
            contexte={"role": form.role.data},
        )
        db.session.commit()
        flash(f"Utilisateur {user.full_name} créé avec succès.", "success")
        return redirect(url_for("admin.index"))  # type: ignore[return-value]

    return render_template("admin/user_form.html", form=form, title="Nouvel utilisateur")


# ── Édition d'un utilisateur ──────────────────────────────────────────────


@bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_ADMIN_ONLY)
def user_edit(uid: int) -> str | Response:
    """Modification du rôle, du nom, de l'e-mail et du statut actif."""
    user = _get_user(uid)

    form = UserEditForm(obj=user)
    form.role.choices = _ROLE_CHOICES

    if form.validate_on_submit():
        old_role = user.role
        old_email = user.email

        email_new = form.email.data.strip().lower()
        if email_new != user.email:
            clash = db.session.query(User).filter(
                User.email == email_new, User.id != uid
            ).first()
            if clash:
                flash("Cette adresse e-mail est déjà utilisée par un autre compte.", "error")
                return render_template("admin/user_form.html", form=form, user=user, title="Modifier l'utilisateur")

        user.prenom = form.prenom.data.strip()
        user.nom = form.nom.data.strip()
        user.email = email_new
        user.role = Role(form.role.data)
        user.actif = form.actif.data

        contexte: dict = {}
        if old_role != user.role:
            contexte["old_role"] = old_role.value
            contexte["new_role"] = user.role.value
        if old_email != user.email:
            contexte["old_email"] = old_email

        AuditTrail.log(
            "user.updated",
            user=_current_user(),
            entity_type="user",
            entity_id=user.id,
            contexte=contexte or None,
        )
        db.session.commit()
        flash(f"Utilisateur {user.full_name} mis à jour.", "success")
        return redirect(url_for("admin.index"))  # type: ignore[return-value]

    form.role.data = user.role.value
    form.actif.data = user.actif
    return render_template("admin/user_form.html", form=form, user=user, title="Modifier l'utilisateur")


# ── Toggle actif / inactif ────────────────────────────────────────────────


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_ADMIN_ONLY)
def user_toggle(uid: int) -> Response:
    """Active ou désactive un compte utilisateur (requête JSON)."""
    user = _get_user(uid)

    if user.id == _current_user().id:
        return jsonify({"ok": False, "error": "Impossible de désactiver son propre compte."}), 400  # type: ignore[return-value]

    user.actif = not user.actif
    AuditTrail.log(
        "user.deactivated" if not user.actif else "user.activated",
        user=_current_user(),
        entity_type="user",
        entity_id=user.id,
        new_value=str(user.actif),
    )
    db.session.commit()
    return jsonify({"ok": True, "actif": user.actif})  # type: ignore[return-value]


# ── Reset mot de passe ────────────────────────────────────────────────────


@bp.route("/users/<int:uid>/reset-pwd", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_ADMIN_ONLY)
def user_reset_password(uid: int) -> str | Response:
    """Réinitialisation du mot de passe d'un utilisateur par l'admin."""
    user = _get_user(uid)
    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.password.data)
        AuditTrail.log(
            "user.password_reset",
            user=_current_user(),
            entity_type="user",
            entity_id=user.id,
        )
        db.session.commit()
        flash(f"Mot de passe de {user.full_name} réinitialisé.", "success")
        return redirect(url_for("admin.index"))  # type: ignore[return-value]

    return render_template(
        "admin/reset_password.html",
        form=form,
        user=user,
    )


# ── Journal d'audit global ────────────────────────────────────────────────


@bp.route("/audit")
@login_required  # type: ignore[untyped-decorator]
@role_required(*_ADMIN_ONLY)
def audit_log() -> str:
    """Journal d'audit global paginé avec filtres action / utilisateur / entité."""
    action_filter = request.args.get("action", "").strip()
    user_filter = request.args.get("user_id", "").strip()
    entity_filter = request.args.get("entity_type", "").strip()

    stmt = (
        select(AuditTrail)
        .options(joinedload(AuditTrail.user))
        .order_by(AuditTrail.created_at.desc())
    )

    if action_filter:
        stmt = stmt.where(AuditTrail.action.ilike(f"%{action_filter}%"))
    if user_filter and user_filter.isdigit():
        stmt = stmt.where(AuditTrail.user_id == int(user_filter))
    if entity_filter:
        stmt = stmt.where(AuditTrail.entity_type == entity_filter)

    pagination = db.paginate(stmt, per_page=_PER_PAGE_AUDIT, error_out=False)

    # Liste des utilisateurs pour le filtre
    all_users = db.session.query(User).order_by(User.nom).all()
    entity_types = ["affaire", "formulaire", "jalon", "user", "referentiel"]

    return render_template(
        "admin/audit.html",
        pagination=pagination,
        entries=pagination.items,
        all_users=all_users,
        entity_types=entity_types,
        action_filter=action_filter,
        user_filter=user_filter,
        entity_filter=entity_filter,
    )


# ── Helpers ───────────────────────────────────────────────────────────────


def _current_user() -> User:
    return current_user._get_current_object()  # type: ignore[no-any-return]


def _get_user(uid: int) -> User:
    user = db.session.get(User, uid)
    if user is None:
        abort(404)
    return user
