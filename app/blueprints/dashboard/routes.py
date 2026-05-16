"""Route du tableau de bord post-login."""
from __future__ import annotations

from flask import render_template
from flask_login import login_required
from sqlalchemy import func

from app.blueprints.dashboard import bp
from app.enums import Statut, StatutJalon
from app.extensions import db
from app.models.affaire import Affaire
from app.models.audit import AuditTrail
from app.models.jalon import Jalon


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def index() -> str:
    """Tableau de bord : compteurs, jalons en retard, alertes, activité récente."""
    rows = (
        db.session.query(Affaire.statut, func.count(Affaire.id))
        .group_by(Affaire.statut)
        .all()
    )
    statut_counts: dict[Statut, int] = {row[0]: row[1] for row in rows}

    recent_affaires = (
        db.session.query(Affaire)
        .order_by(Affaire.created_at.desc())
        .limit(8)
        .all()
    )

    jalons_retard = (
        db.session.query(Jalon)
        .filter(Jalon.statut == StatutJalon.EN_RETARD)
        .order_by(Jalon.date_prevue)
        .limit(10)
        .all()
    )

    try:
        from app.services.alertes import get_alertes_actives  # noqa: PLC0415
        alertes = get_alertes_actives()[:10]
    except Exception:  # noqa: BLE001
        alertes = []

    recent_audit = (
        db.session.query(AuditTrail)
        .order_by(AuditTrail.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "dashboard/index.html",
        statut_counts=statut_counts,
        recent_affaires=recent_affaires,
        statuts=list(Statut),
        jalons_retard=jalons_retard,
        alertes=alertes,
        recent_audit=recent_audit,
    )
