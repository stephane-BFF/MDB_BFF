"""Tests d'intégration — blueprint Dossier (génération PDF assemblé).

Vérifie :
    - GET  /affaires/<id>/dossier/pdf         (synchrone)
    - POST /affaires/<id>/dossier/pdf/async   (Celery, TASK_ALWAYS_EAGER=True)
    - GET  /affaires/<id>/dossier/pdf/status/<task_id>

WeasyPrint est mocké dans tous les cas (GTK absent sur le serveur CI).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from app.enums import Role, Statut
from app.extensions import db
from app.models.affaire import Affaire


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def client_lecteur(client: FlaskClient, app) -> FlaskClient:  # noqa: ANN001
    """Client authentifié Lecteur (rôle lecture seule)."""
    from tests.conftest import _make_user
    u = _make_user("lecteur@bff.fr", "Luc", "Lecteur", Role.LECTEUR)
    client.post("/auth/login", data={"email": u.email, "password": "Test1234!"})
    return client


# ── Tests PDF synchrone ────────────────────────────────────────────────────


class TestDossierPdfSync:
    """GET /affaires/<id>/dossier/pdf — génération synchrone."""

    # assemble_dossier est importé de façon lazy (inside try block) dans les routes,
    # donc on patche à la source, pas dans le module routes.
    _ASSEMBLE = "app.services.pdf.assemblage.assemble_dossier"

    def test_weasyprint_absent_redirects_with_flash(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """Si WeasyPrint est absent (RuntimeError), redirige vers la page affaire."""
        with patch(self._ASSEMBLE, side_effect=RuntimeError("WeasyPrint non disponible.")):
            resp = client_lecteur.get(
                f"/affaires/{affaire.id}/dossier/pdf",
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert f"/affaires/{affaire.id}" in resp.headers["Location"]

    def test_pdf_served_as_attachment(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """Si assemble_dossier réussit, le PDF est servi en ligne."""
        fake_pdf = b"%PDF-1.4\n%%EOF"
        with patch(self._ASSEMBLE, return_value=fake_pdf), \
             patch("app.blueprints.dossier.routes.net_svc") as mock_net:
            mock_net.save_pdf.return_value = None
            resp = client_lecteur.get(f"/affaires/{affaire.id}/dossier/pdf")

        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"
        assert resp.data == fake_pdf

    def test_nas_failure_does_not_block_pdf(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """Une erreur NAS (OSError) ne bloque pas la réponse PDF."""
        fake_pdf = b"%PDF-1.4\n%%EOF"
        with patch(self._ASSEMBLE, return_value=fake_pdf), \
             patch("app.blueprints.dossier.routes.net_svc.save_pdf",
                   side_effect=OSError("NAS inaccessible")):
            resp = client_lecteur.get(
                f"/affaires/{affaire.id}/dossier/pdf",
                follow_redirects=True,
            )

        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"

    def test_unauthenticated_redirected(self, client: FlaskClient, affaire: Affaire) -> None:
        resp = client.get(f"/affaires/{affaire.id}/dossier/pdf", follow_redirects=False)
        assert resp.status_code == 302

    def test_affaire_not_found_returns_404(
        self,
        client_lecteur: FlaskClient,
    ) -> None:
        resp = client_lecteur.get("/affaires/99999/dossier/pdf")
        assert resp.status_code == 404

    def test_audit_trail_created(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """Vérifie qu'un AuditTrail est enregistré au téléchargement."""
        from app.models.audit import AuditTrail

        fake_pdf = b"%PDF-1.4\n%%EOF"
        with patch(self._ASSEMBLE, return_value=fake_pdf), \
             patch("app.blueprints.dossier.routes.net_svc") as mock_net:
            mock_net.save_pdf.return_value = None
            client_lecteur.get(f"/affaires/{affaire.id}/dossier/pdf")

        trail = (
            db.session.query(AuditTrail)
            .filter_by(action="dossier.pdf_downloaded", entity_type="affaire")
            .first()
        )
        assert trail is not None
        assert trail.entity_id == affaire.id


# ── Tests PDF asynchrone ───────────────────────────────────────────────────


class TestDossierPdfAsync:
    """POST /affaires/<id>/dossier/pdf/async — Celery TASK_ALWAYS_EAGER=True."""

    def test_returns_task_id(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """La route retourne {"ok": true, "task_id": "..."}."""
        from unittest.mock import MagicMock

        mock_task_result = MagicMock()
        mock_task_result.id = "test-task-uuid-1234"

        # Patch la méthode .delay() pour éviter toute connexion Redis
        with patch(
            "app.services.pdf.tasks.generate_dossier_pdf.delay",
            return_value=mock_task_result,
        ):
            resp = client_lecteur.post(f"/affaires/{affaire.id}/dossier/pdf/async")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["task_id"] == "test-task-uuid-1234"

    def test_unauthenticated_redirected(self, client: FlaskClient, affaire: Affaire) -> None:
        resp = client.post(f"/affaires/{affaire.id}/dossier/pdf/async", follow_redirects=False)
        assert resp.status_code == 302


# ── Tests statut tâche ─────────────────────────────────────────────────────


class TestDossierPdfStatus:
    """GET /affaires/<id>/dossier/pdf/status/<task_id>."""

    def test_unknown_task_returns_state(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """La route retourne un état JSON pour n'importe quelle task_id."""
        from unittest.mock import MagicMock
        from celery.result import AsyncResult

        mock_result = MagicMock(spec=AsyncResult)
        mock_result.state = "PENDING"
        mock_result.ready.return_value = False

        # AsyncResult est importé lazy dans la route; on patche à la source
        with patch("celery.result.AsyncResult", return_value=mock_result):
            resp = client_lecteur.get(
                f"/affaires/{affaire.id}/dossier/pdf/status/nonexistent-task-id"
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "state" in data

    def test_completed_task_includes_result(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """Une tâche SUCCESS retourne l'état et le résultat."""
        from unittest.mock import MagicMock
        from celery.result import AsyncResult

        mock_result = MagicMock(spec=AsyncResult)
        mock_result.state = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {"size_bytes": 1024}

        with patch("celery.result.AsyncResult", return_value=mock_result):
            resp = client_lecteur.get(
                f"/affaires/{affaire.id}/dossier/pdf/status/fake-task-id"
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["state"] == "SUCCESS"
        assert data["result"] == {"size_bytes": 1024}
