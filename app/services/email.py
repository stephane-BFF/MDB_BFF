"""Service email Flask-Mail — alertes jalons et certifications.

Deux types d'alertes :
    - Quotidienne : jalons en retard → chargés d'affaires + responsable qualité
    - Hebdomadaire : certifications/étalonnages expirés/bientôt expirés → responsable qualité

La configuration SMTP est dans .env via les variables MAIL_* (Flask-Mail).
Les destinataires sont configurables via ALERT_EMAILS_QUALITE et
ALERT_EMAILS_CHARGE dans la config.
"""
from __future__ import annotations

import logging

from flask import current_app

log = logging.getLogger(__name__)


def send_alerte_jalons_retard(jalons: list) -> bool:
    """Envoie l'email quotidien des jalons en retard.

    Args:
        jalons: Liste d'objets Jalon au statut EN_RETARD.

    Returns:
        True si l'email a été envoyé sans erreur, False sinon.
    """
    if not jalons:
        return True

    destinataires = current_app.config.get("ALERT_EMAILS_QUALITE", [])
    if not destinataires:
        log.warning("email.alerte_jalons: aucun destinataire configuré (ALERT_EMAILS_QUALITE)")
        return False

    lignes = [
        f"  • {j.code.value} — {j.affaire.numero_affaire if j.affaire else '?'} "
        f"(prévu le {j.date_prevue.strftime('%d/%m/%Y') if j.date_prevue else '?'})"
        for j in jalons
    ]
    corps = (
        "Bonjour,\n\n"
        f"Les {len(jalons)} jalon(s) suivants sont en retard :\n\n"
        + "\n".join(lignes)
        + "\n\nVeuillez vous connecter à l'application MDB BFF pour mettre à jour l'avancement.\n\n"
        "Cordialement,\nApplication MDB BFF"
    )
    return _send(
        subject=f"[MDB BFF] {len(jalons)} jalon(s) en retard",
        recipients=destinataires,
        body=corps,
    )


def send_alerte_certifications(alertes: list) -> bool:
    """Envoie l'email hebdomadaire des certifications expirées/bientôt expirées.

    Args:
        alertes: Liste d'objets Alerte (type soudeur/operateur_cnd/instrument).

    Returns:
        True si l'email a été envoyé sans erreur, False sinon.
    """
    if not alertes:
        return True

    destinataires = current_app.config.get("ALERT_EMAILS_QUALITE", [])
    if not destinataires:
        log.warning("email.alerte_certs: aucun destinataire configuré (ALERT_EMAILS_QUALITE)")
        return False

    expirees = [a for a in alertes if a.niveau == "expire"]
    bientot = [a for a in alertes if a.niveau == "bientot"]

    sections = []
    if expirees:
        sections.append("EXPIRÉ :\n" + "\n".join(f"  • {a.label} — {a.detail}" for a in expirees))
    if bientot:
        sections.append("BIENTÔT EXPIRÉ (≤ 30 jours) :\n" + "\n".join(f"  • {a.label} — {a.detail}" for a in bientot))

    corps = (
        "Bonjour,\n\n"
        "Récapitulatif hebdomadaire des certifications et étalonnages :\n\n"
        + "\n\n".join(sections)
        + "\n\nVeuillez vous connecter à l'application MDB BFF pour mettre à jour les référentiels.\n\n"
        "Cordialement,\nApplication MDB BFF"
    )
    return _send(
        subject=f"[MDB BFF] {len(expirees)} certification(s) expirée(s), {len(bientot)} bientôt",
        recipients=destinataires,
        body=corps,
    )


def _send(subject: str, recipients: list[str], body: str) -> bool:
    """Envoi effectif via Flask-Mail."""
    try:
        from flask_mail import Message  # noqa: PLC0415

        from app.extensions import mail  # noqa: PLC0415

        sender = current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@bff-mdb.local")
        msg = Message(subject=subject, sender=sender, recipients=recipients, body=body)
        mail.send(msg)
        log.info("email.sent", extra={"subject": subject, "recipients": recipients})
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("email.send_failed", extra={"subject": subject, "error": str(exc)})
        return False
