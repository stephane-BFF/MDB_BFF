"""Routes du blueprint Référentiels — CRUD des ressources qualité partagées.

URL prefix : ``/referentiels``

Entités gérées :
    GET/POST  /soudeurs             — liste + création
    GET/PATCH/DELETE /soudeurs/<id> — détail + MAJ + suppression logique
    (idem pour operateurs-cnd, materiaux, instruments)

Toutes les routes d'écriture sont réservées aux rôles APPROBATEUR et ADMIN.
Les routes lecture sont accessibles à tous les rôles authentifiés.
"""
from __future__ import annotations

from datetime import date

from flask import abort, jsonify, render_template, request
from flask_login import login_required
from werkzeug.wrappers.response import Response

from app.blueprints.referentiels import bp
from app.enums import Role
from app.extensions import db
from app.models.referentiel import (
    Instrument,
    Materiau,
    OperateurCND,
    Soudeur,
    TypeEquipement,
)
from app.utils.decorators import role_required

_EDIT_ROLES = (Role.APPROBATEUR, Role.ADMIN)
_READ_ROLES = (Role.LECTEUR, Role.REDACTEUR, Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)


# ── Page principale (onglets) ─────────────────────────────────────────────


@bp.route("/", methods=["GET"])
@login_required  # type: ignore[untyped-decorator]
def index() -> Response:
    """Page principale avec les 5 onglets référentiels."""
    soudeurs = db.session.query(Soudeur).order_by(Soudeur.nom).all()
    operateurs = db.session.query(OperateurCND).order_by(OperateurCND.nom).all()
    materiaux = db.session.query(Materiau).order_by(Materiau.designation).all()
    instruments = db.session.query(Instrument).order_by(Instrument.reference).all()
    types_equipement = (
        db.session.query(TypeEquipement)
        .order_by(TypeEquipement.ordre, TypeEquipement.libelle)
        .all()
    )

    return render_template(  # type: ignore[return-value]
        "referentiels/index.html",
        soudeurs=soudeurs,
        operateurs=operateurs,
        materiaux=materiaux,
        instruments=instruments,
        types_equipement=types_equipement,
        today=date.today(),
    )


# ── Soudeurs ──────────────────────────────────────────────────────────────


@bp.route("/soudeurs", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def soudeur_create() -> Response:
    """Crée un soudeur."""
    p = request.get_json(silent=True) or {}
    nom = (p.get("nom") or "").strip()
    qualification = (p.get("qualification") or "").strip()
    if not nom or not qualification:
        return jsonify({"ok": False, "error": "Nom et qualification requis."}), 400  # type: ignore[return-value]

    s = Soudeur(
        nom=nom[:200],
        qualification=qualification[:100],
        indice=(p.get("indice") or "")[:20] or None,
        date_expiration=_parse_date(p.get("date_expiration")),
        commentaire=(p.get("commentaire") or "")[:500] or None,
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({"ok": True, "id": s.id}), 201  # type: ignore[return-value]


@bp.route("/soudeurs/<int:sid>", methods=["PATCH"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def soudeur_update(sid: int) -> Response:
    """Met à jour un soudeur."""
    s = db.session.get(Soudeur, sid)
    if s is None:
        abort(404)
    p = request.get_json(silent=True) or {}
    if "nom" in p and p["nom"]:
        s.nom = str(p["nom"])[:200]
    if "qualification" in p and p["qualification"]:
        s.qualification = str(p["qualification"])[:100]
    if "indice" in p:
        s.indice = (str(p["indice"])[:20] or None)
    if "date_expiration" in p:
        s.date_expiration = _parse_date(p["date_expiration"])
    if "actif" in p:
        s.actif = bool(p["actif"])
    if "commentaire" in p:
        s.commentaire = str(p["commentaire"])[:500] or None
    db.session.commit()
    return jsonify({"ok": True, "statut_expiration": s.statut_expiration})  # type: ignore[return-value]


@bp.route("/soudeurs/<int:sid>", methods=["DELETE"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def soudeur_delete(sid: int) -> Response:
    """Désactive un soudeur (suppression logique)."""
    s = db.session.get(Soudeur, sid)
    if s is None:
        abort(404)
    s.actif = False
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


# ── Opérateurs CND ────────────────────────────────────────────────────────


@bp.route("/operateurs-cnd", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def operateur_create() -> Response:
    """Crée un opérateur CND."""
    p = request.get_json(silent=True) or {}
    nom = (p.get("nom") or "").strip()
    qualification = (p.get("qualification") or "").strip()
    niveau = (p.get("niveau") or "").strip()
    if not nom or not qualification or not niveau:
        return jsonify({"ok": False, "error": "Nom, qualification et niveau requis."}), 400  # type: ignore[return-value]

    o = OperateurCND(
        nom=nom[:200],
        qualification=qualification[:50],
        niveau=niveau[:10],
        date_expiration=_parse_date(p.get("date_expiration")),
        commentaire=(p.get("commentaire") or "")[:500] or None,
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"ok": True, "id": o.id}), 201  # type: ignore[return-value]


@bp.route("/operateurs-cnd/<int:oid>", methods=["PATCH"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def operateur_update(oid: int) -> Response:
    """Met à jour un opérateur CND."""
    o = db.session.get(OperateurCND, oid)
    if o is None:
        abort(404)
    p = request.get_json(silent=True) or {}
    if "nom" in p and p["nom"]:
        o.nom = str(p["nom"])[:200]
    if "qualification" in p and p["qualification"]:
        o.qualification = str(p["qualification"])[:50]
    if "niveau" in p and p["niveau"]:
        o.niveau = str(p["niveau"])[:10]
    if "date_expiration" in p:
        o.date_expiration = _parse_date(p["date_expiration"])
    if "actif" in p:
        o.actif = bool(p["actif"])
    if "commentaire" in p:
        o.commentaire = str(p["commentaire"])[:500] or None
    db.session.commit()
    return jsonify({"ok": True, "statut_expiration": o.statut_expiration})  # type: ignore[return-value]


@bp.route("/operateurs-cnd/<int:oid>", methods=["DELETE"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def operateur_delete(oid: int) -> Response:
    """Désactive un opérateur CND."""
    o = db.session.get(OperateurCND, oid)
    if o is None:
        abort(404)
    o.actif = False
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


# ── Matériaux ─────────────────────────────────────────────────────────────


@bp.route("/materiaux", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def materiau_create() -> Response:
    """Crée un matériau."""
    p = request.get_json(silent=True) or {}
    designation = (p.get("designation") or "").strip()
    norme = (p.get("norme") or "").strip()
    if not designation or not norme:
        return jsonify({"ok": False, "error": "Désignation et norme requises."}), 400  # type: ignore[return-value]

    m = Materiau(
        designation=designation[:255],
        norme=norme[:100],
        certificat=(p.get("certificat") or "")[:100] or None,
        commentaire=(p.get("commentaire") or "")[:500] or None,
    )
    db.session.add(m)
    db.session.commit()
    return jsonify({"ok": True, "id": m.id}), 201  # type: ignore[return-value]


@bp.route("/materiaux/<int:mid>", methods=["PATCH"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def materiau_update(mid: int) -> Response:
    """Met à jour un matériau."""
    m = db.session.get(Materiau, mid)
    if m is None:
        abort(404)
    p = request.get_json(silent=True) or {}
    if "designation" in p and p["designation"]:
        m.designation = str(p["designation"])[:255]
    if "norme" in p and p["norme"]:
        m.norme = str(p["norme"])[:100]
    if "certificat" in p:
        m.certificat = str(p["certificat"])[:100] or None
    if "actif" in p:
        m.actif = bool(p["actif"])
    if "commentaire" in p:
        m.commentaire = str(p["commentaire"])[:500] or None
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


@bp.route("/materiaux/<int:mid>", methods=["DELETE"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def materiau_delete(mid: int) -> Response:
    """Désactive un matériau."""
    m = db.session.get(Materiau, mid)
    if m is None:
        abort(404)
    m.actif = False
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


# ── Types d'équipement (V1.2, D7) ─────────────────────────────────────────


@bp.route("/types-equipement", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def type_equipement_create() -> Response:
    """Crée un type d'équipement."""
    p = request.get_json(silent=True) or {}
    libelle = (p.get("libelle") or "").strip()
    if not libelle:
        return jsonify({"ok": False, "error": "Le libellé est requis."}), 400  # type: ignore[return-value]
    existing = db.session.query(TypeEquipement).filter_by(libelle=libelle[:100]).first()
    if existing is not None:
        return jsonify({"ok": False, "error": "Ce type d'équipement existe déjà."}), 400  # type: ignore[return-value]

    t = TypeEquipement(
        libelle=libelle[:100],
        ordre=int(p.get("ordre") or 0),
        commentaire=(p.get("commentaire") or "")[:500] or None,
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({"ok": True, "id": t.id}), 201  # type: ignore[return-value]


@bp.route("/types-equipement/<int:tid>", methods=["PATCH"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def type_equipement_update(tid: int) -> Response:
    """Met à jour un type d'équipement."""
    t = db.session.get(TypeEquipement, tid)
    if t is None:
        abort(404)
    p = request.get_json(silent=True) or {}
    if "libelle" in p and p["libelle"]:
        t.libelle = str(p["libelle"])[:100]
    if "ordre" in p:
        t.ordre = int(p["ordre"] or 0)
    if "actif" in p:
        t.actif = bool(p["actif"])
    if "commentaire" in p:
        t.commentaire = str(p["commentaire"])[:500] or None
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


@bp.route("/types-equipement/<int:tid>", methods=["DELETE"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def type_equipement_delete(tid: int) -> Response:
    """Désactive un type d'équipement (suppression logique)."""
    t = db.session.get(TypeEquipement, tid)
    if t is None:
        abort(404)
    t.actif = False
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


# ── Instruments ───────────────────────────────────────────────────────────


@bp.route("/instruments", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def instrument_create() -> Response:
    """Crée un instrument de métrologie."""
    p = request.get_json(silent=True) or {}
    reference = (p.get("reference") or "").strip()
    type_instrument = (p.get("type_instrument") or "").strip()
    if not reference or not type_instrument:
        return jsonify({"ok": False, "error": "Référence et type requis."}), 400  # type: ignore[return-value]

    i = Instrument(
        reference=reference[:100],
        type_instrument=type_instrument[:100],
        date_etalonnage=_parse_date(p.get("date_etalonnage")),
        date_prochain_etalonnage=_parse_date(p.get("date_prochain_etalonnage")),
        commentaire=(p.get("commentaire") or "")[:500] or None,
    )
    db.session.add(i)
    db.session.commit()
    return jsonify({"ok": True, "id": i.id}), 201  # type: ignore[return-value]


@bp.route("/instruments/<int:iid>", methods=["PATCH"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def instrument_update(iid: int) -> Response:
    """Met à jour un instrument."""
    i = db.session.get(Instrument, iid)
    if i is None:
        abort(404)
    p = request.get_json(silent=True) or {}
    if "reference" in p and p["reference"]:
        i.reference = str(p["reference"])[:100]
    if "type_instrument" in p and p["type_instrument"]:
        i.type_instrument = str(p["type_instrument"])[:100]
    if "date_etalonnage" in p:
        i.date_etalonnage = _parse_date(p["date_etalonnage"])
    if "date_prochain_etalonnage" in p:
        i.date_prochain_etalonnage = _parse_date(p["date_prochain_etalonnage"])
    if "actif" in p:
        i.actif = bool(p["actif"])
    if "commentaire" in p:
        i.commentaire = str(p["commentaire"])[:500] or None
    db.session.commit()
    return jsonify({"ok": True, "statut_expiration": i.statut_expiration})  # type: ignore[return-value]


@bp.route("/instruments/<int:iid>", methods=["DELETE"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_EDIT_ROLES)
def instrument_delete(iid: int) -> Response:
    """Désactive un instrument."""
    i = db.session.get(Instrument, iid)
    if i is None:
        abort(404)
    i.actif = False
    db.session.commit()
    return jsonify({"ok": True})  # type: ignore[return-value]


# ── Helper ────────────────────────────────────────────────────────────────


def _parse_date(val: object) -> date | None:
    """Parse une chaîne ISO 8601 en date, retourne None si invalide."""
    if not val:
        return None
    try:
        return date.fromisoformat(str(val))
    except ValueError:
        return None
