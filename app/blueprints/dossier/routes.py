"""Routes du blueprint Dossier — génération du dossier PDF complet MDB BFF.

URL prefix : ``/affaires/<int:affaire_id>/dossier``

Routes :
    GET  /pdf          — génération synchrone + téléchargement direct
    POST /pdf/async    — déclenche la tâche Celery asynchrone
    GET  /pdf/status/<task_id>  — statut de la tâche en cours
"""
from __future__ import annotations

import io

from flask import abort, current_app, flash, jsonify, redirect, send_file, url_for
from flask_login import login_required
from werkzeug.wrappers.response import Response

from app.blueprints.dossier import bp
from app.extensions import db
from app.models.affaire import Affaire
from app.models.audit import AuditTrail
from app.models.user import User
from app.services import network as net_svc
from app.utils.decorators import role_required
from app.enums import Role

_READ_ROLES = (Role.LECTEUR, Role.REDACTEUR, Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)


@bp.route("/pdf", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_READ_ROLES)
def pdf(affaire_id: int) -> Response:
    """Génère le dossier PDF complet de manière synchrone et le sert en téléchargement.

    Accessible à tous les rôles (lecture seule).
    La sauvegarde NAS est non bloquante : un flash warning est affiché si
    le NAS est inaccessible, mais le PDF est servi au navigateur.

    Redirige avec flash "danger" si WeasyPrint / GTK est absent.
    """
    affaire = _get_affaire(affaire_id)

    try:
        from app.services.pdf.assemblage import assemble_dossier  # noqa: PLC0415

        pdf_bytes = assemble_dossier(affaire)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("affaires.show", affaire_id=affaire_id))  # type: ignore[return-value]

    AuditTrail.log(
        "dossier.pdf_downloaded",
        entity_type="affaire",
        entity_id=affaire_id,
        contexte={"size_bytes": len(pdf_bytes)},
    )
    db.session.commit()

    try:
        net_svc.save_pdf(
            pdf_bytes,
            affaire.annee,
            affaire.references_internes,
            "DOSSIER_COMPLET",
        )
    except OSError as exc:
        flash(f"Dossier généré mais non sauvegardé sur le NAS : {exc}", "warning")

    filename = f"{affaire.references_internes}_DOSSIER_COMPLET.pdf"
    return send_file(  # type: ignore[return-value]
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=filename,
    )


@bp.route("/pdf/async", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_READ_ROLES)
def pdf_async(affaire_id: int) -> Response:
    """Déclenche la génération asynchrone du dossier PDF via Celery.

    Returns:
        JSON ``{"ok": true, "task_id": "..."}``
    """
    affaire = _get_affaire(affaire_id)

    from app.services.pdf.tasks import generate_dossier_pdf  # noqa: PLC0415

    task = generate_dossier_pdf.delay(affaire.id)
    current_app.logger.info(
        "dossier.task_dispatched",
        extra={"affaire": affaire.numero_affaire, "task_id": task.id},
    )
    return jsonify({"ok": True, "task_id": task.id})  # type: ignore[return-value]


@bp.route("/pdf/status/<task_id>", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def pdf_status(affaire_id: int, task_id: str) -> Response:  # noqa: ARG001
    """Interroge l'état d'une tâche Celery de génération de dossier.

    Returns:
        JSON ``{"state": "PENDING"|"SUCCESS"|"FAILURE", "result": ...}``
    """
    from celery.result import AsyncResult  # noqa: PLC0415

    result = AsyncResult(task_id)
    payload: dict = {"state": result.state}
    if result.ready():
        payload["result"] = result.result if result.successful() else str(result.result)
    return jsonify(payload)  # type: ignore[return-value]


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_affaire(affaire_id: int) -> Affaire:
    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        abort(404)
    return affaire
