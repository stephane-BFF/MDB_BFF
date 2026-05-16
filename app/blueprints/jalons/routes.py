"""Routes du blueprint Jalons — timeline JP0-JP6 par affaire.

URL prefix : ``/affaires/<int:affaire_id>/jalons``

Routes :
    GET    /                    — page timeline jalons
    POST   /<code>/franchir     — franchissement d'un jalon
    POST   /<code>/hold-point   — création d'un Hold Point
    POST   /<code>/hold-point/<hp_id>/signer — signature Hold Point
    PATCH  /<code>/date         — mise à jour date prévue (JSON)
"""
from __future__ import annotations

from datetime import date

from flask import abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.wrappers.response import Response

from app.blueprints.jalons import bp
from app.enums import JalonCode, Role, StatutJalon
from app.extensions import db
from app.models.affaire import Affaire
from app.models.jalon import Jalon
from app.services import jalons as jalon_svc
from app.utils.decorators import role_required

_EDIT_ROLES = (Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)


@bp.route("/", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def index(affaire_id: int) -> Response:
    """Affiche la timeline JP0-JP6 de l'affaire."""
    affaire = _get_affaire(affaire_id)

    # Rafraîchit les statuts EN_RETARD / BLOQUE avant affichage
    jalon_svc.refresh_statuts(affaire)
    db.session.commit()

    jalons = sorted(affaire.jalons, key=lambda j: j.code.numero)

    # Pour chaque jalon : calcul des prérequis satisfaits
    jalons_ctx = []
    for j in jalons:
        ok, manquants = jalon_svc.verifier_prerequis(j)
        jalons_ctx.append({
            "jalon": j,
            "prerequis_ok": ok,
            "manquants": manquants,
        })

    return render_template(  # type: ignore[return-value]
        "jalons/index.html",
        affaire=affaire,
        jalons_ctx=jalons_ctx,
    )


@bp.route("/<code>/franchir", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def franchir(affaire_id: int, code: str) -> Response:
    """Franchit un jalon si tous les prérequis sont satisfaits."""
    jalon = _get_jalon(affaire_id, code)
    commentaire = request.form.get("commentaire", "").strip() or None

    from flask_login import current_user as cu  # noqa: PLC0415
    user = cu._get_current_object()  # type: ignore[no-any-return]

    ok, erreur = jalon_svc.franchir_jalon(jalon, user, commentaire)
    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if ok:
            return jsonify({"ok": True, "statut": jalon.statut.value})  # type: ignore[return-value]
        return jsonify({"ok": False, "error": erreur}), 400  # type: ignore[return-value]

    if not ok:
        current_app.logger.warning("jalon.franchissement_refuse", extra={"erreur": erreur})

    return redirect(url_for("jalons.index", affaire_id=affaire_id))  # type: ignore[return-value]


@bp.route("/<code>/hold-point", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def creer_hold_point(affaire_id: int, code: str) -> Response:
    """Crée un Hold Point sur un jalon."""
    jalon = _get_jalon(affaire_id, code)
    payload = request.get_json(silent=True) or {}

    organisme = (payload.get("organisme") or "").strip()
    if not organisme:
        return jsonify({"ok": False, "error": "Organisme requis."}), 400  # type: ignore[return-value]

    nom_inspecteur = (payload.get("nom_inspecteur") or "").strip() or None
    date_str = payload.get("date_inspection", "")
    date_inspection: date | None = None
    if date_str:
        try:
            date_inspection = date.fromisoformat(date_str)
        except ValueError:
            return jsonify({"ok": False, "error": "Date invalide."}), 400  # type: ignore[return-value]

    from flask_login import current_user as cu  # noqa: PLC0415
    user = cu._get_current_object()  # type: ignore[no-any-return]

    hp = jalon_svc.creer_hold_point(jalon, organisme, nom_inspecteur, date_inspection, user)
    db.session.commit()

    return jsonify({  # type: ignore[return-value]
        "ok": True,
        "hold_point": {
            "id": hp.id,
            "organisme": hp.organisme,
            "nom_inspecteur": hp.nom_inspecteur,
            "date_inspection": hp.date_inspection.isoformat() if hp.date_inspection else None,
            "signe": hp.signe,
        },
    })


@bp.route("/<code>/hold-point/<int:hp_id>/signer", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(Role.APPROBATEUR, Role.ADMIN)
def signer_hold_point(affaire_id: int, code: str, hp_id: int) -> Response:
    """Signe un Hold Point (rôle Approbateur ou Admin uniquement)."""
    jalon = _get_jalon(affaire_id, code)
    hp = db.session.get(jalon.__class__.__mro__[0], hp_id)  # type: ignore[arg-type]

    # Récupération directe via la relation pour vérifier l'appartenance
    hp = next((h for h in jalon.hold_points if h.id == hp_id), None)
    if hp is None:
        abort(404)

    from flask_login import current_user as cu  # noqa: PLC0415
    user = cu._get_current_object()  # type: ignore[no-any-return]

    jalon_svc.signer_hold_point(hp, user)
    db.session.commit()

    return jsonify({"ok": True, "signe": True})  # type: ignore[return-value]


@bp.route("/<code>/date", methods=["PATCH"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def update_date(affaire_id: int, code: str) -> Response:
    """Met à jour la date prévue d'un jalon (JSON PATCH)."""
    jalon = _get_jalon(affaire_id, code)
    payload = request.get_json(silent=True) or {}

    date_str = payload.get("date_prevue", "")
    if date_str:
        try:
            jalon.date_prevue = date.fromisoformat(date_str)
        except ValueError:
            return jsonify({"ok": False, "error": "Date invalide."}), 400  # type: ignore[return-value]
    else:
        jalon.date_prevue = None

    db.session.commit()
    return jsonify({  # type: ignore[return-value]
        "ok": True,
        "date_prevue": jalon.date_prevue.isoformat() if jalon.date_prevue else None,
    })


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_affaire(affaire_id: int) -> Affaire:
    a = db.session.get(Affaire, affaire_id)
    if a is None:
        abort(404)
    return a


def _get_jalon(affaire_id: int, code: str) -> Jalon:
    try:
        jcode = JalonCode(code.upper())
    except ValueError:
        abort(404)
    j = (
        db.session.query(Jalon)
        .filter_by(affaire_id=affaire_id, code=jcode)
        .first()
    )
    if j is None:
        abort(404)
    return j
