"""Service alertes — certifications expirées et jalons en retard.

Centralise le calcul des alertes pour :
    - Le badge de navigation (nombre total d'alertes actives).
    - Le widget dashboard "Alertes actives".
    - Les tâches Celery d'envoi d'email.

Une alerte est soit :
    - "bientot" : expiration dans les 30 prochains jours
    - "expire"  : déjà expirée (invalide)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.enums import StatutJalon
from app.extensions import db
from app.models.jalon import Jalon
from app.models.referentiel import Instrument, OperateurCND, Soudeur


@dataclass
class Alerte:
    """Représentation d'une alerte active."""

    type: str          # "soudeur", "operateur_cnd", "instrument", "jalon"
    niveau: str        # "bientot" ou "expire" (jalons : toujours "retard")
    label: str         # Nom/référence de la ressource concernée
    detail: str        # Info complémentaire (date, code jalon…)
    url: str = ""      # URL vers la ressource dans l'interface


def get_alertes_actives() -> list[Alerte]:
    """Retourne toutes les alertes actives (certifications + jalons en retard).

    Args : aucun (requête globale toutes affaires / tous référentiels).

    Returns:
        Liste triée : expirations d'abord, puis approches d'expiration,
        puis jalons en retard.
    """
    alertes: list[Alerte] = []

    today = date.today()

    # ── Soudeurs ──────────────────────────────────────────────────────────
    for s in db.session.query(Soudeur).filter(Soudeur.actif.is_(True)).all():
        statut = s.statut_expiration
        if statut != "ok":
            alertes.append(Alerte(
                type="soudeur",
                niveau=statut,
                label=s.nom,
                detail=f"Qualification expire le {s.date_expiration.strftime('%d/%m/%Y') if s.date_expiration else '?'}",
                url="/referentiels#tab-soudeurs",
            ))

    # ── Opérateurs CND ────────────────────────────────────────────────────
    for o in db.session.query(OperateurCND).filter(OperateurCND.actif.is_(True)).all():
        statut = o.statut_expiration
        if statut != "ok":
            alertes.append(Alerte(
                type="operateur_cnd",
                niveau=statut,
                label=o.nom,
                detail=f"Certification {o.qualification} expire le {o.date_expiration.strftime('%d/%m/%Y') if o.date_expiration else '?'}",
                url="/referentiels#tab-cnd",
            ))

    # ── Instruments ───────────────────────────────────────────────────────
    for i in db.session.query(Instrument).filter(Instrument.actif.is_(True)).all():
        statut = i.statut_expiration
        if statut != "ok":
            alertes.append(Alerte(
                type="instrument",
                niveau=statut,
                label=i.reference,
                detail=f"Étalonnage dû le {i.date_prochain_etalonnage.strftime('%d/%m/%Y') if i.date_prochain_etalonnage else '?'}",
                url="/referentiels#tab-inst",
            ))

    # ── Jalons en retard ──────────────────────────────────────────────────
    jalons_retard = (
        db.session.query(Jalon)
        .filter(Jalon.statut == StatutJalon.EN_RETARD)
        .all()
    )
    for j in jalons_retard:
        alertes.append(Alerte(
            type="jalon",
            niveau="retard",
            label=f"{j.code.value} — {j.affaire.numero_affaire if j.affaire else '?'}",
            detail=f"Prévu le {j.date_prevue.strftime('%d/%m/%Y') if j.date_prevue else '?'}",
            url=f"/affaires/{j.affaire_id}/jalons#{j.code.value}",
        ))

    # Trier : expiré > bientôt > retard
    _ordre = {"expire": 0, "bientot": 1, "retard": 2}
    alertes.sort(key=lambda a: _ordre.get(a.niveau, 9))
    return alertes


def count_alertes() -> int:
    """Retourne le nombre total d'alertes actives (pour badge nav)."""
    return len(get_alertes_actives())
