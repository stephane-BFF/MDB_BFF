"""Route du tableau de bord post-login."""
from __future__ import annotations

from flask import render_template
from flask_login import login_required
from sqlalchemy import func

from app.blueprints.dashboard import bp
from app.enums import Statut
from app.extensions import db
from app.models.affaire import Affaire


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def index() -> str:
    """Tableau de bord : compteurs par statut + 10 dernières affaires.

    Phase 1 minimal — sera enrichi en Phase 4 avec jalons, alertes et activité.
    """
    rows = (
        db.session.query(Affaire.statut, func.count(Affaire.id))
        .group_by(Affaire.statut)
        .all()
    )
    statut_counts: dict[Statut, int] = {row[0]: row[1] for row in rows}
    recent_affaires = (
        db.session.query(Affaire)
        .order_by(Affaire.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "dashboard/index.html",
        statut_counts=statut_counts,
        recent_affaires=recent_affaires,
        statuts=list(Statut),
    )
