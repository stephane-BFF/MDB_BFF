"""Routes du blueprint Formulaires — dispatch générique via registre de services.

URL prefix : ``/affaires/<int:affaire_id>/formulaires``

Routes :
    GET  /<code>          — affichage du formulaire (formulaire.data pré-rempli)
    POST /<code>          — sauvegarde AJAX brouillon (JSON)
    POST /<code>/valider  — transition BROUILLON → VALIDE
    POST /<code>/signer   — transition VALIDE → SIGNE + hash SHA-256
    GET  /<code>/pdf      — génère et télécharge le PDF

Le code est résolu via ``get_service(code)`` ; les codes non enregistrés → 404.
Les formulaires avec ``CUSTOM_TEMPLATE=True`` (ex. HYDR) utilisent leur propre
template Jinja2 ; les autres utilisent ``formulaires/_simple.html``.
"""
from __future__ import annotations

import io

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.wrappers.response import Response

from app.blueprints.formulaires import bp
from app.enums import Role, Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.formulaire import FormulaireTemplate
from app.models.user import User
from app.services.formulaires import get_service
from app.utils.decorators import role_required

_EDIT_ROLES = (Role.REDACTEUR, Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)
_VALIDATE_ROLES = (Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)
_SIGN_ROLES = (Role.APPROBATEUR, Role.ADMIN)


@bp.route("/<code>", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def show(affaire_id: int, code: str) -> str:
    """Affiche le formulaire <code> pour l'affaire donnée.

    Sélectionne le template Jinja2 selon ``svc.CUSTOM_TEMPLATE`` :
    - True  → ``formulaires/<code_lower>.html`` (template dédié)
    - False → ``formulaires/_simple.html`` (gabarit générique piloté par SECTIONS)
    """
    svc = _get_service_or_404(code)
    affaire = _get_affaire(affaire_id)
    formulaire = svc.get_or_none(affaire)

    if formulaire is None:
        form_data = svc.prefill_from_parametrage(affaire)
        is_new = True
    else:
        form_data = formulaire.data
        is_new = False

    tmpl = (
        db.session.query(FormulaireTemplate)
        .filter_by(code=code.upper(), actif=True)
        .first()
    )

    hash_valid: bool | None = None
    if formulaire and formulaire.statut is Statut.SIGNE and formulaire.signatures:
        hash_valid = formulaire.signatures[-1].verify(formulaire)

    user = _current_user()
    can_edit = formulaire is None or (
        formulaire.statut.is_editable
        and user.has_role(Role.REDACTEUR, Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)
    )
    can_validate = (
        formulaire is not None
        and formulaire.statut is Statut.BROUILLON
        and user.has_role(Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)
    )
    can_sign = (
        formulaire is not None
        and formulaire.statut is Statut.VALIDE
        and user.has_role(Role.APPROBATEUR, Role.ADMIN)
    )

    template_name = svc.get_web_template()
    reference_options = (
        svc.get_reference_options() if hasattr(svc, "get_reference_options") else {}
    )
    return render_template(
        template_name,
        affaire=affaire,
        formulaire=formulaire,
        svc=svc,
        tmpl=tmpl,
        form_data=form_data,
        is_new=is_new,
        can_edit=can_edit,
        can_validate=can_validate,
        can_sign=can_sign,
        hash_valid=hash_valid,
        code=code.upper(),
        reference_options=reference_options,
    )


@bp.route("/<code>", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def save(affaire_id: int, code: str) -> Response:
    """Sauvegarde AJAX brouillon — retourne JSON.

    Attend un corps JSON. Le token CSRF doit être passé via ``X-CSRFToken``.

    Returns:
        JSON ``{"ok": true, "statut": "brouillon"}`` ou
        ``{"ok": false, "error": "..."}`` avec code HTTP 400/403.
    """
    svc = _get_service_or_404(code)
    affaire = _get_affaire(affaire_id)

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"ok": False, "error": "Corps JSON attendu."}), 400  # type: ignore[return-value]

    try:
        formulaire = svc.save_brouillon(affaire, payload, _current_user())
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 403  # type: ignore[return-value]

    return jsonify({"ok": True, "statut": formulaire.statut.value})


@bp.route("/<code>/valider", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_VALIDATE_ROLES)
def valider(affaire_id: int, code: str) -> Response:
    """Transition BROUILLON → VALIDE — requiert des champs obligatoires renseignés."""
    svc = _get_service_or_404(code)
    affaire = _get_affaire(affaire_id)
    formulaire = svc.get_or_none(affaire)
    if formulaire is None:
        abort(404)

    try:
        svc.valider(formulaire, _current_user())
        flash(f"Formulaire {code.upper()} validé.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("formulaires.show", affaire_id=affaire_id, code=code))  # type: ignore[return-value]


@bp.route("/<code>/signer", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_SIGN_ROLES)
def signer(affaire_id: int, code: str) -> Response:
    """Transition VALIDE → SIGNE — crée la Signature SHA-256."""
    svc = _get_service_or_404(code)
    affaire = _get_affaire(affaire_id)
    formulaire = svc.get_or_none(affaire)
    if formulaire is None:
        abort(404)

    try:
        sig = svc.signer(formulaire, _current_user())
        flash(
            f"Formulaire {code.upper()} signé — hash {sig.hash_sha256[:12]}…",
            "success",
        )
    except ValueError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("formulaires.show", affaire_id=affaire_id, code=code))  # type: ignore[return-value]


@bp.route("/<code>/pdf", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def pdf(affaire_id: int, code: str) -> Response:
    """Génère le PDF du formulaire et le retourne en téléchargement.

    Accessible depuis le statut VALIDE ou SIGNE. La sauvegarde NAS est non
    bloquante : si le NAS est inaccessible un flash warning est affiché mais
    le PDF est tout de même servi au navigateur.
    """
    svc = _get_service_or_404(code)
    affaire = _get_affaire(affaire_id)
    formulaire = svc.get_or_none(affaire)
    if formulaire is None:
        abort(404)

    if formulaire.statut not in (Statut.VALIDE, Statut.SIGNE):
        flash(
            "Le PDF n'est accessible qu'une fois le formulaire validé ou signé.",
            "warning",
        )
        return redirect(url_for("formulaires.show", affaire_id=affaire_id, code=code))  # type: ignore[return-value]

    try:
        from app.services.pdf import unitaire as pdf_svc  # noqa: PLC0415

        pdf_bytes = pdf_svc.render_formulaire_pdf(formulaire, affaire, svc)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("formulaires.show", affaire_id=affaire_id, code=code))  # type: ignore[return-value]

    try:
        from app.services import network as net_svc  # noqa: PLC0415

        saved_path = net_svc.save_pdf(
            pdf_bytes, affaire.annee, affaire.references_internes, code.upper()
        )
        current_app.logger.info(
            "pdf.nas_saved",
            extra={"path": str(saved_path), "affaire": affaire.numero_affaire},
        )
    except OSError as exc:
        flash(f"PDF généré mais non sauvegardé sur le NAS : {exc}", "warning")

    filename = f"{affaire.references_internes}_{code.upper()}.pdf"
    return send_file(  # type: ignore[return-value]
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=filename,
    )


# ── Helpers ───────────────────────────────────────────────────────────────


def _current_user() -> User:
    return current_user._get_current_object()  # type: ignore[no-any-return]


def _get_affaire(affaire_id: int) -> Affaire:
    """Charge l'affaire ou abort 404."""
    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        abort(404)
    return affaire


def _get_service_or_404(code: str):  # type: ignore[return]
    """Résout le code de formulaire via le registre ou abort 404."""
    svc = get_service(code)
    if svc is None:
        abort(404)
    return svc
