"""Tests d'intégration — authentification (login / logout)."""
from __future__ import annotations

from flask.testing import FlaskClient

from app.extensions import db
from app.models.user import User


class TestLoginPage:
    def test_get_login_page(self, client: FlaskClient) -> None:
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_login_page_contains_form(self, client: FlaskClient) -> None:
        resp = client.get("/auth/login")
        body = resp.data.decode("utf-8")
        assert "email" in body.lower()
        assert "password" in body.lower() or "mot de passe" in body.lower()

    def test_unauthenticated_affaires_redirects_to_login(
        self, client: FlaskClient
    ) -> None:
        resp = client.get("/affaires/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


class TestLoginPost:
    def test_valid_credentials_redirect_to_dashboard(
        self, client: FlaskClient, user_redacteur: User
    ) -> None:
        resp = client.post(
            "/auth/login",
            data={"email": user_redacteur.email, "password": "Test1234!"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "/dashboard", "/dashboard/")

    def test_wrong_password_returns_401(
        self, client: FlaskClient, user_redacteur: User
    ) -> None:
        resp = client.post(
            "/auth/login",
            data={"email": user_redacteur.email, "password": "MauvaisMotDePasse!"},
        )
        assert resp.status_code == 401

    def test_unknown_email_returns_401(self, client: FlaskClient) -> None:
        resp = client.post(
            "/auth/login",
            data={"email": "inconnu@bff.fr", "password": "Test1234!"},
        )
        assert resp.status_code == 401

    def test_inactive_user_returns_403(
        self, client: FlaskClient, user_redacteur: User
    ) -> None:
        u = db.session.get(User, user_redacteur.id)
        assert u is not None
        u.actif = False
        db.session.commit()

        resp = client.post(
            "/auth/login",
            data={"email": user_redacteur.email, "password": "Test1234!"},
        )
        assert resp.status_code == 403

    def test_authenticated_user_redirected_away_from_login(
        self, client_redacteur: FlaskClient
    ) -> None:
        resp = client_redacteur.get("/auth/login", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "/dashboard", "/dashboard/")
