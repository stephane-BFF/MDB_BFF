"""Routes d'authentification — login local, logout."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask.wrappers import Response
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.wrappers.response import Response as WerkzeugResponse

from app.blueprints.auth import bp
from app.extensions import db
from app.forms.auth import LoginForm
from app.models.audit import AuditTrail
from app.models.user import User


@bp.route("/login", methods=["GET", "POST"])
def login() -> Response | str | WerkzeugResponse | tuple[str, int]:
    """Connecte un utilisateur. Redirige vers ``next`` ou le dashboard.

    Le paramètre ``next`` est validé pour ne pas autoriser des redirections
    externes (open-redirect).
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data or ""):
            AuditTrail.log(
                "auth.failed",
                entity_type="user",
                entity_id=user.id if user is not None else None,
                contexte={
                    "email": form.email.data,
                    "ip": request.remote_addr,
                    "reason": "user_not_found" if user is None else "bad_password",
                },
            )
            db.session.commit()
            flash("E-mail ou mot de passe incorrect.", "danger")
            return render_template("auth/login.html", form=form), 401

        if not user.actif:
            AuditTrail.log(
                "auth.failed",
                user=user,
                entity_type="user",
                entity_id=user.id,
                contexte={"ip": request.remote_addr, "reason": "inactive"},
            )
            db.session.commit()
            flash("Ce compte a été désactivé. Contactez un administrateur.", "warning")
            return render_template("auth/login.html", form=form), 403

        login_user(user, remember=bool(form.remember.data))
        AuditTrail.log(
            "auth.login",
            user=user,
            entity_type="user",
            entity_id=user.id,
            contexte={"ip": request.remote_addr, "remember": bool(form.remember.data)},
        )
        db.session.commit()
        flash(f"Bienvenue {user.prenom} !", "success")

        next_url = request.args.get("next")
        if next_url and _is_safe_redirect(next_url):
            return redirect(next_url)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def logout() -> WerkzeugResponse:
    """Déconnecte l'utilisateur courant (POST only pour anti-CSRF)."""
    user_id = current_user.id
    AuditTrail.log(
        "auth.logout",
        user=current_user,
        entity_type="user",
        entity_id=user_id,
        contexte={"ip": request.remote_addr},
    )
    db.session.commit()
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("auth.login"))


def _is_safe_redirect(target: str) -> bool:
    """Vérifie que l'URL de redirection est interne (anti open-redirect).

    Refuse les URLs absolues vers un autre domaine et les schémas non-HTTP(S).
    """
    parsed = urlparse(target)
    if parsed.netloc and parsed.netloc != request.host:
        return False
    if parsed.scheme and parsed.scheme not in {"http", "https", ""}:
        return False
    return True
