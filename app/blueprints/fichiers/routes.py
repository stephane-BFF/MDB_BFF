"""Routes du blueprint Fichiers — import drag & drop de fichiers extérieurs.

URL prefix : ``/affaires/<int:affaire_id>/fichiers``

Routes :
    GET    /           — liste JSON des fichiers de l'affaire
    POST   /upload     — upload multipart (AJAX), retourne JSON
    GET    /<fid>      — téléchargement du fichier
    PATCH  /<fid>      — mise à jour des métadonnées (titre, chapitre, ordre)
    DELETE /<fid>      — suppression fichier + enregistrement disque

Types acceptés : PDF, JPEG, PNG, TIFF (validés côté serveur par python-magic).
Limite de taille : ``MAX_CONTENT_LENGTH`` (défaut 20 Mo).
Stockage : ``UPLOAD_FOLDER/<affaire_id>/<uuid>.<ext>``
"""
from __future__ import annotations

import os

from flask import (
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)
from flask_login import current_user, login_required
from werkzeug.wrappers.response import Response

from app.blueprints.fichiers import bp
from app.enums import Chapitre, Role
from app.extensions import db
from app.models.affaire import Affaire
from app.models.audit import AuditTrail
from app.models.fichier import FichierImporte
from app.models.user import User
from app.utils.decorators import role_required
from app.utils.file_handler import validate_mime

_EDIT_ROLES = (Role.REDACTEUR, Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)
_READ_ROLES = (Role.LECTEUR, Role.REDACTEUR, Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)


@bp.route("/manage", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def manage(affaire_id: int) -> Response:
    """Affiche la page de gestion des fichiers importés (drag & drop UI)."""
    affaire = _get_affaire(affaire_id)
    can_edit = _current_user().role in _EDIT_ROLES
    return render_template(  # type: ignore[return-value]
        "fichiers/index.html",
        affaire=affaire,
        can_edit=can_edit,
    )


@bp.route("/", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def index(affaire_id: int) -> Response:
    """Retourne la liste JSON des fichiers importés pour l'affaire."""
    affaire = _get_affaire(affaire_id)
    fichiers = (
        db.session.query(FichierImporte)
        .filter_by(affaire_id=affaire.id)
        .order_by(FichierImporte.chapitre, FichierImporte.ordre)
        .all()
    )
    return jsonify([_to_dict(f) for f in fichiers])  # type: ignore[return-value]


@bp.route("/upload", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def upload(affaire_id: int) -> Response:
    """Upload un fichier extérieur (multipart/form-data).

    Champs de formulaire attendus :
        - ``file`` : fichier binaire
        - ``chapitre`` : valeur de ``Chapitre`` (ex: ``"A"``)
        - ``titre`` : titre dans le dossier
        - ``ordre`` : entier (optionnel, défaut 99)

    Returns:
        JSON ``{"ok": true, "fichier": {...}}`` ou ``{"ok": false, "error": "..."}``
    """
    affaire = _get_affaire(affaire_id)

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Aucun fichier reçu."}), 400  # type: ignore[return-value]

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "Nom de fichier vide."}), 400  # type: ignore[return-value]

    # Validation MIME côté serveur (python-magic)
    if not validate_mime(file):
        return jsonify({"ok": False, "error": "Type de fichier non autorisé."}), 415  # type: ignore[return-value]

    import magic as _magic  # noqa: PLC0415
    header = file.read(2048)
    file.seek(0)
    mime_type = _magic.from_buffer(header, mime=True)

    # Validation chapitre
    chapitre_val = request.form.get("chapitre", "A").upper()
    try:
        chapitre = Chapitre(chapitre_val)
    except ValueError:
        return jsonify({"ok": False, "error": f"Chapitre invalide : {chapitre_val}"}), 400  # type: ignore[return-value]

    titre = (request.form.get("titre") or file.filename or "Sans titre")[:200]
    ordre = int(request.form.get("ordre") or 99)

    # Stockage sur disque
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    dest_dir = os.path.join(upload_folder, str(affaire.id))
    os.makedirs(dest_dir, exist_ok=True)

    filename = FichierImporte.make_filename(file.filename)
    filepath = os.path.join(dest_dir, filename)
    file.save(filepath)
    taille = os.path.getsize(filepath)

    fichier = FichierImporte(
        affaire_id=affaire.id,
        cree_par_id=_current_user().id,
        chapitre=chapitre,
        titre=titre,
        ordre=ordre,
        filename=filename,
        original_filename=file.filename[:255],
        mime_type=mime_type,
        taille=taille,
    )
    db.session.add(fichier)
    db.session.flush()

    AuditTrail.log(
        "fichier.uploaded",
        entity_type="fichier_importe",
        entity_id=fichier.id,
        new_value=titre,
        contexte={"affaire_id": affaire.id, "chapitre": chapitre.value, "mime": mime_type},
    )
    db.session.commit()

    current_app.logger.info(
        "fichier.upload_ok",
        extra={"affaire": affaire.numero_affaire, "titre": titre, "size": taille},
    )
    return jsonify({"ok": True, "fichier": _to_dict(fichier)})  # type: ignore[return-value]


@bp.route("/<int:fid>", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def download(affaire_id: int, fid: int) -> Response:
    """Télécharge un fichier importé."""
    fichier = _get_fichier(affaire_id, fid)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    filepath = os.path.join(upload_folder, str(affaire_id), fichier.filename)

    if not os.path.exists(filepath):
        abort(404)

    return send_file(  # type: ignore[return-value]
        filepath,
        mimetype=fichier.mime_type,
        as_attachment=True,
        download_name=fichier.original_filename,
    )


@bp.route("/<int:fid>", methods=["PATCH"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def update(affaire_id: int, fid: int) -> Response:
    """Met à jour les métadonnées d'un fichier (titre, chapitre, ordre).

    Attend un corps JSON avec les champs à modifier.
    """
    fichier = _get_fichier(affaire_id, fid)
    payload = request.get_json(silent=True) or {}

    if "titre" in payload and payload["titre"]:
        fichier.titre = str(payload["titre"])[:200]
    if "ordre" in payload:
        try:
            fichier.ordre = int(payload["ordre"])
        except (TypeError, ValueError):
            pass
    if "chapitre" in payload:
        try:
            fichier.chapitre = Chapitre(str(payload["chapitre"]).upper())
        except ValueError:
            return jsonify({"ok": False, "error": "Chapitre invalide."}), 400  # type: ignore[return-value]

    db.session.commit()
    return jsonify({"ok": True, "fichier": _to_dict(fichier)})  # type: ignore[return-value]


@bp.route("/<int:fid>", methods=["DELETE"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def delete(affaire_id: int, fid: int) -> Response:
    """Supprime un fichier importé (enregistrement DB + fichier disque)."""
    fichier = _get_fichier(affaire_id, fid)

    # Suppression fichier disque (non bloquante)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    filepath = os.path.join(upload_folder, str(affaire_id), fichier.filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError as exc:
        current_app.logger.warning(
            "fichier.delete_disk_failed",
            extra={"filepath": filepath, "error": str(exc)},
        )

    AuditTrail.log(
        "fichier.deleted",
        entity_type="fichier_importe",
        entity_id=fichier.id,
        old_value=fichier.titre,
        contexte={"affaire_id": affaire_id},
    )
    db.session.delete(fichier)
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


# ── Helpers ───────────────────────────────────────────────────────────────


def _current_user() -> User:
    from flask_login import current_user as cu  # noqa: PLC0415
    return cu._get_current_object()  # type: ignore[no-any-return]


def _get_affaire(affaire_id: int) -> Affaire:
    a = db.session.get(Affaire, affaire_id)
    if a is None:
        abort(404)
    return a


def _get_fichier(affaire_id: int, fid: int) -> FichierImporte:
    f = db.session.get(FichierImporte, fid)
    if f is None or f.affaire_id != affaire_id:
        abort(404)
    return f


def _to_dict(f: FichierImporte) -> dict:
    return {
        "id": f.id,
        "titre": f.titre,
        "chapitre": f.chapitre.value,
        "ordre": f.ordre,
        "original_filename": f.original_filename,
        "mime_type": f.mime_type,
        "taille": f.taille,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }
