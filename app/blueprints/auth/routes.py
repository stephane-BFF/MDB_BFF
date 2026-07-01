"""Routes d'authentification — login (LDAP/local), 2FA TOTP, logout.

Flux de connexion :
    1. ``/login`` — vérifie l'identité via ``services.ldap_auth.authenticate``
       (bind Active Directory si ``WINDOWS_AUTH_ENABLED``, sinon hash local).
    2. Si le compte a la 2FA activée (``totp_enabled``), l'utilisateur n'est
       **pas** encore connecté : il est redirigé vers ``/2fa`` pour saisir un
       code TOTP (ou un code de secours). L'identité en attente est stockée en
       session signée (``pending_2fa_user_id``).
    3. ``/2fa/setup`` — enrôlement self-service (QR code + codes de secours).

Le durcissement ``ENFORCE_2FA`` (config) redirige les Approbateurs/Admin sans
2FA vers l'enrôlement après login ; désactivé par défaut (dev/test).
"""
from __future__ import annotations

import base64
import io
from urllib.parse import urlparse

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.wrappers import Response
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.wrappers.response import Response as WerkzeugResponse

from app.blueprints.auth import bp
from app.extensions import db
from app.forms.auth import LoginForm, TotpSetupForm, TwoFactorForm
from app.models.audit import AuditTrail
from app.models.user import User
from app.services.ldap_auth import authenticate

_PENDING_2FA_USER = "pending_2fa_user_id"
_PENDING_2FA_REMEMBER = "pending_2fa_remember"
_PENDING_2FA_NEXT = "pending_2fa_next"


@bp.route("/login", methods=["GET", "POST"])
def login() -> Response | str | WerkzeugResponse | tuple[str, int]:
    """Connecte un utilisateur (LDAP/AD ou local), avec 2FA si activée.

    Le paramètre ``next`` est validé pour ne pas autoriser des redirections
    externes (open-redirect).
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        result = authenticate(form.email.data or "", form.password.data or "")
        user = result.user

        if not result.success:
            AuditTrail.log(
                "auth.failed",
                user=user,
                entity_type="user",
                entity_id=user.id if user is not None else None,
                contexte={
                    "email": form.email.data,
                    "ip": request.remote_addr,
                    "reason": result.reason,
                    "method": result.method.name.lower(),
                },
            )
            db.session.commit()
            flash("E-mail ou mot de passe incorrect.", "danger")
            return render_template("auth/login.html", form=form), 401

        if user is not None and not user.actif:
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

        assert user is not None  # succès ⇒ user résolu
        next_url = request.args.get("next")

        # ── Second facteur requis ? ──────────────────────────────────────
        if user.totp_enabled:
            session[_PENDING_2FA_USER] = user.id
            session[_PENDING_2FA_REMEMBER] = bool(form.remember.data)
            safe_next = next_url if next_url and _is_safe_redirect(next_url) else None
            session[_PENDING_2FA_NEXT] = safe_next
            AuditTrail.log(
                "auth.2fa_challenge",
                user=user,
                entity_type="user",
                entity_id=user.id,
                contexte={"ip": request.remote_addr, "method": result.method.name.lower()},
            )
            db.session.commit()
            return redirect(url_for("auth.two_factor"))

        return _complete_login(
            user,
            remember=bool(form.remember.data),
            method=result.method.name.lower(),
            next_url=next_url,
        )

    return render_template("auth/login.html", form=form)


@bp.route("/2fa", methods=["GET", "POST"])
def two_factor() -> Response | str | WerkzeugResponse | tuple[str, int]:
    """Second facteur : saisie d'un code TOTP ou d'un code de secours."""
    user_id = session.get(_PENDING_2FA_USER)
    if user_id is None:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if user is None or not user.actif:
        _clear_pending_2fa()
        flash("Session d'authentification expirée, reconnectez-vous.", "warning")
        return redirect(url_for("auth.login"))

    form = TwoFactorForm()
    if form.validate_on_submit():
        code = (form.code.data or "").strip()
        via_backup = False
        if user.verify_totp(code):
            ok = True
        elif user.consume_backup_code(code):
            ok, via_backup = True, True
        else:
            ok = False

        if not ok:
            AuditTrail.log(
                "auth.2fa_failed",
                user=user,
                entity_type="user",
                entity_id=user.id,
                contexte={"ip": request.remote_addr},
            )
            db.session.commit()
            flash("Code d'authentification invalide.", "danger")
            return render_template("auth/two_factor.html", form=form), 401

        remember = bool(session.get(_PENDING_2FA_REMEMBER))
        next_url = session.get(_PENDING_2FA_NEXT)
        _clear_pending_2fa()
        if via_backup:
            flash(
                "Connexion via code de secours. Pensez à régénérer vos codes.",
                "warning",
            )
        return _complete_login(
            user, remember=remember, method="2fa", next_url=next_url, via_backup=via_backup
        )

    return render_template("auth/two_factor.html", form=form)


@bp.route("/2fa/setup", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def two_factor_setup() -> Response | str | WerkzeugResponse:
    """Enrôlement 2FA self-service : affiche le QR code puis active la 2FA.

    À l'affichage (GET), un secret est généré s'il n'en existe pas encore et
    stocké (``totp_enabled`` reste False). À la validation (POST) d'un code
    correct, la 2FA est activée et 8 codes de secours sont générés et affichés
    une seule fois.
    """
    user: User = current_user  # type: ignore[assignment]
    form = TotpSetupForm()

    if user.totp_enabled and request.method == "GET":
        flash("La double authentification est déjà active sur votre compte.", "info")

    # Génère un secret d'enrôlement si absent (ou si non encore confirmé).
    if not user.totp_secret or not user.totp_enabled:
        if request.method == "GET" and not user.totp_secret:
            user.start_totp_enrollment()
            db.session.commit()

    if form.validate_on_submit():
        if user.confirm_totp(form.code.data or ""):
            backup_codes = user.generate_backup_codes()
            AuditTrail.log(
                "auth.2fa_enabled",
                user=user,
                entity_type="user",
                entity_id=user.id,
                contexte={"ip": request.remote_addr},
            )
            db.session.commit()
            flash("Double authentification activée.", "success")
            return render_template(
                "auth/two_factor_setup.html",
                form=form,
                activated=True,
                backup_codes=backup_codes,
            )
        flash("Code invalide, réessayez avec le code courant de l'application.", "danger")

    qr_uri = _totp_qr_data_uri(user)
    return render_template(
        "auth/two_factor_setup.html",
        form=form,
        activated=False,
        secret=user.totp_secret,
        qr_uri=qr_uri,
    )


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


# ── Helpers ────────────────────────────────────────────────────────────────


def _complete_login(
    user: User,
    *,
    remember: bool,
    method: str,
    next_url: str | None,
    via_backup: bool = False,
) -> WerkzeugResponse:
    """Finalise la connexion : login_user + audit + redirection sûre."""
    login_user(user, remember=remember)
    AuditTrail.log(
        "auth.login",
        user=user,
        entity_type="user",
        entity_id=user.id,
        contexte={
            "ip": request.remote_addr,
            "remember": remember,
            "method": method,
            "backup_code": via_backup,
        },
    )
    db.session.commit()
    flash(f"Bienvenue {user.prenom} !", "success")

    # Durcissement : forcer l'enrôlement 2FA des rôles à privilège.
    if (
        current_app.config.get("ENFORCE_2FA")
        and user.requires_2fa
        and not user.totp_enabled
    ):
        flash(
            "Votre rôle impose la double authentification : veuillez l'activer.",
            "warning",
        )
        return redirect(url_for("auth.two_factor_setup"))

    if next_url and _is_safe_redirect(next_url):
        return redirect(next_url)
    return redirect(url_for("dashboard.index"))


def _clear_pending_2fa() -> None:
    """Purge l'état de challenge 2FA de la session."""
    session.pop(_PENDING_2FA_USER, None)
    session.pop(_PENDING_2FA_REMEMBER, None)
    session.pop(_PENDING_2FA_NEXT, None)


def _totp_qr_data_uri(user: User) -> str | None:
    """Génère le QR code de l'URI d'enrôlement TOTP en data URI PNG base64."""
    if not user.totp_secret:
        return None
    try:
        import qrcode  # noqa: PLC0415
    except ImportError:  # pragma: no cover — qrcode est une dépendance déclarée
        return None
    issuer = current_app.config.get("TOTP_ISSUER", "MDB BFF")
    uri = user.totp_provisioning_uri(issuer=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


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
