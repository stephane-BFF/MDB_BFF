"""Tests unitaires — tâche Celery de génération du dossier PDF (`app.services.pdf.tasks`)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from celery.exceptions import Retry
from flask import Flask

from app.models.affaire import Affaire
from app.models.audit import AuditTrail
from app.services.pdf import tasks
from app.extensions import db

_FAKE_PDF = b"%PDF-1.4\n%%EOF"


class TestGenerateDossierPdf:
    def test_affaire_introuvable(self, app: Flask) -> None:
        with app.app_context():
            result = tasks.generate_dossier_pdf.run(999999)
        assert result["ok"] is False
        assert "introuvable" in result["error"]

    def test_succes_sauvegarde_nas(self, app: Flask, affaire: Affaire) -> None:
        with app.app_context(), patch.object(
            tasks, "assemble_dossier", return_value=_FAKE_PDF
        ), patch.object(
            tasks.net_svc, "save_pdf", return_value=Path("X:/MDB/DOSSIER_COMPLET.pdf")
        ):
            result = tasks.generate_dossier_pdf.run(affaire.id)
        assert result["ok"] is True
        assert result["size"] == len(_FAKE_PDF)
        # Un audit trail de génération est écrit.
        trail = (
            db.session.query(AuditTrail)
            .filter_by(action="dossier.pdf_generated", entity_id=affaire.id)
            .first()
        )
        assert trail is not None

    def test_echec_nas_nefait_pas_echouer_la_generation(self, app: Flask, affaire: Affaire) -> None:
        with app.app_context(), patch.object(
            tasks, "assemble_dossier", return_value=_FAKE_PDF
        ), patch.object(
            tasks.net_svc, "save_pdf", side_effect=OSError("NAS injoignable")
        ):
            result = tasks.generate_dossier_pdf.run(affaire.id)
        assert result["ok"] is False
        assert "non sauvegardé" in result["error"]

    def test_weasyprint_absent_declenche_retry(self, app: Flask, affaire: Affaire) -> None:
        # Appelée hors worker (``.run()``), ``self.retry`` relance l'exception
        # d'origine plutôt qu'une ``Retry`` — on couvre la branche de retry.
        with app.app_context(), patch.object(
            tasks, "assemble_dossier", side_effect=RuntimeError("WeasyPrint absent")
        ), pytest.raises((Retry, RuntimeError)):
            tasks.generate_dossier_pdf.run(affaire.id)
