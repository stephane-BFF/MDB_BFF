"""Tâches Celery — génération asynchrone du dossier PDF complet MDB BFF.

L'assemblage d'un dossier complet (50-100 pages) peut prendre plusieurs
secondes. La tâche ``generate_dossier_pdf`` délègue le travail à un worker
Celery pour ne pas bloquer le thread HTTP.

Lancement d'un worker en développement :
    celery -A make_celery worker --loglevel=info

La tâche est exécutée en synchrone dans les tests (``CELERY_TASK_ALWAYS_EAGER=True``).
"""
from __future__ import annotations

from celery import shared_task
from flask import current_app

from app.extensions import db
from app.models.affaire import Affaire
from app.models.audit import AuditTrail
from app.services import network as net_svc
from app.services.pdf.assemblage import assemble_dossier


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_dossier_pdf(self, affaire_id: int) -> dict:
    """Génère le dossier PDF complet et le sauvegarde sur le NAS.

    Args:
        affaire_id: Identifiant de l'affaire à assembler.

    Returns:
        Dict ``{"ok": True, "path": "...", "size": N}`` ou
        ``{"ok": False, "error": "..."}`` en cas d'échec non retryable.

    Raises:
        self.retry: Si WeasyPrint est temporairement indisponible.
    """
    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        return {"ok": False, "error": f"Affaire {affaire_id} introuvable."}

    try:
        pdf_bytes = assemble_dossier(affaire)
    except RuntimeError as exc:
        current_app.logger.error(
            "dossier.assemble_failed",
            extra={"affaire_id": affaire_id, "error": str(exc)},
        )
        raise self.retry(exc=exc)

    try:
        path = net_svc.save_pdf(
            pdf_bytes,
            affaire.annee,
            affaire.references_internes,
            "DOSSIER_COMPLET",
        )
        AuditTrail.log(
            "dossier.pdf_generated",
            entity_type="affaire",
            entity_id=affaire_id,
            new_value=str(path),
            contexte={"size_bytes": len(pdf_bytes)},
        )
        db.session.commit()
        current_app.logger.info(
            "dossier.pdf_saved",
            extra={"affaire": affaire.numero_affaire, "path": str(path)},
        )
        return {"ok": True, "path": str(path), "size": len(pdf_bytes)}
    except OSError as exc:
        current_app.logger.warning(
            "dossier.nas_save_failed",
            extra={"affaire_id": affaire_id, "error": str(exc)},
        )
        return {"ok": False, "error": f"PDF généré mais non sauvegardé sur le NAS : {exc}"}
