"""Tests d'intégration — accès et navigation dans les affaires."""
from __future__ import annotations

from flask.testing import FlaskClient

from app.models.affaire import Affaire


class TestAffairesAccess:
    def test_unauthenticated_list_redirects(self, client: FlaskClient) -> None:
        resp = client.get("/affaires/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_authenticated_list_returns_200(
        self, client_redacteur: FlaskClient
    ) -> None:
        resp = client_redacteur.get("/affaires/")
        assert resp.status_code == 200

    def test_affaire_detail_returns_200(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}")
        assert resp.status_code == 200

    def test_affaire_detail_shows_numero(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}")
        assert b"BN2026-001" in resp.data

    def test_affaire_404_for_unknown_id(
        self, client_redacteur: FlaskClient
    ) -> None:
        resp = client_redacteur.get("/affaires/99999")
        assert resp.status_code == 404

    def test_affaire_shows_hydr_formulaire_link(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}")
        assert b"HYDR" in resp.data
