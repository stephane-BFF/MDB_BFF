"""Tâches Celery — envoi périodique des alertes email MDB BFF.

Deux tâches planifiables via Celery Beat :
    - ``send_alertes_jalons``  : quotidienne (jalons en retard)
    - ``send_alertes_certs``   : hebdomadaire (certifications/étalonnages)

Configuration Celery Beat dans config.py :
    CELERY_BEAT_SCHEDULE = {
        "alertes-jalons-quotidien": {
            "task": "app.services.tasks_alertes.send_alertes_jalons",
            "schedule": crontab(hour=7, minute=0),          # 07h00 chaque jour
        },
        "alertes-certs-hebdo": {
            "task": "app.services.tasks_alertes.send_alertes_certs",
            "schedule": crontab(hour=7, minute=30, day_of_week=1),  # lundi 07h30
        },
    }
"""
from __future__ import annotations

from celery import shared_task


@shared_task(bind=True, max_retries=2, default_retry_delay=60)  # type: ignore[misc]
def send_alertes_jalons(self: object) -> dict:
    """Tâche quotidienne : envoie l'alerte des jalons en retard.

    Returns:
        Dict ``{"sent": bool, "nb_jalons": int}``.
    """
    try:
        from app.services import jalons as jalon_svc  # noqa: PLC0415
        from app.services.email import send_alerte_jalons_retard  # noqa: PLC0415

        jalons = jalon_svc.get_jalons_en_retard()
        sent = send_alerte_jalons_retard(jalons)
        return {"sent": sent, "nb_jalons": len(jalons)}
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)  # type: ignore[attr-defined]


@shared_task(bind=True, max_retries=2, default_retry_delay=60)  # type: ignore[misc]
def send_alertes_certs(self: object) -> dict:
    """Tâche hebdomadaire : envoie l'alerte des certifications expirées/proches.

    Returns:
        Dict ``{"sent": bool, "nb_alertes": int}``.
    """
    try:
        from app.services.alertes import get_alertes_actives  # noqa: PLC0415
        from app.services.email import send_alerte_certifications  # noqa: PLC0415

        alertes = [a for a in get_alertes_actives() if a.type != "jalon"]
        sent = send_alerte_certifications(alertes)
        return {"sent": sent, "nb_alertes": len(alertes)}
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)  # type: ignore[attr-defined]
