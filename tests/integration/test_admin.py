"""Tests d'intégration — Blueprint admin (gestion utilisateurs + audit global)."""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Role
from app.extensions import db as _db
from app.models.user import User
from tests.conftest import _login, _make_user


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture()
def user_admin(app: Flask) -> User:
    return _make_user("admin@bff.fr", "Admin", "BFF", Role.ADMIN)


@pytest.fixture()
def user_target(app: Flask) -> User:
    """Utilisateur cible pour les tests de modification."""
    return _make_user("target@bff.fr", "Cible", "Test", Role.REDACTEUR)


@pytest.fixture()
def client_admin(client: FlaskClient, user_admin: User) -> FlaskClient:
    _login(client, user_admin.email)
    return client


@pytest.fixture()
def client_verif_adm(app: Flask, client: FlaskClient) -> FlaskClient:
    u = _make_user("verif_adm@bff.fr", "Ver", "Adm", Role.VERIFICATEUR)
    _login(client, u.email)
    return client


# ── Accès réservé Admin ───────────────────────────────────────────────────


class TestAdminAccess:
    def test_index_requires_auth(self, client: FlaskClient) -> None:
        resp = client.get("/admin/")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_index_requires_admin_role(self, client_verif_adm: FlaskClient) -> None:
        resp = client_verif_adm.get("/admin/")
        assert resp.status_code == 403

    def test_index_ok_admin(self, client_admin: FlaskClient, user_admin: User) -> None:
        resp = client_admin.get("/admin/")
        assert resp.status_code == 200
        assert b"Gestion des utilisateurs" in resp.data
        assert b"admin@bff.fr" in resp.data


# ── Création d'un utilisateur ─────────────────────────────────────────────


class TestUserCreate:
    def test_get_form(self, client_admin: FlaskClient) -> None:
        resp = client_admin.get("/admin/users/new")
        assert resp.status_code == 200
        assert b"Nouvel utilisateur" in resp.data

    def test_create_ok(self, client_admin: FlaskClient) -> None:
        resp = client_admin.post(
            "/admin/users/new",
            data={
                "prenom": "Jean",
                "nom": "Dupont",
                "email": "jean.dupont@bff.fr",
                "role": Role.REDACTEUR.value,
                "password": "SecurePass1!",
                "password_confirm": "SecurePass1!",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        u = _db.session.query(User).filter_by(email="jean.dupont@bff.fr").first()
        assert u is not None
        assert u.role is Role.REDACTEUR
        assert u.actif is True

    def test_create_duplicate_email(
        self, client_admin: FlaskClient, user_target: User
    ) -> None:
        resp = client_admin.post(
            "/admin/users/new",
            data={
                "prenom": "Autre",
                "nom": "User",
                "email": user_target.email,
                "role": Role.LECTEUR.value,
                "password": "SecurePass1!",
                "password_confirm": "SecurePass1!",
            },
        )
        assert resp.status_code == 200
        assert "déjà utilisée".encode() in resp.data

    def test_create_password_mismatch(self, client_admin: FlaskClient) -> None:
        resp = client_admin.post(
            "/admin/users/new",
            data={
                "prenom": "Test",
                "nom": "Mismatch",
                "email": "mismatch@bff.fr",
                "role": Role.LECTEUR.value,
                "password": "Pass1234!",
                "password_confirm": "DifferentPass!",
            },
        )
        assert resp.status_code == 200
        assert "ne correspondent pas".encode() in resp.data

    def test_create_password_too_short(self, client_admin: FlaskClient) -> None:
        resp = client_admin.post(
            "/admin/users/new",
            data={
                "prenom": "Test",
                "nom": "Short",
                "email": "short@bff.fr",
                "role": Role.LECTEUR.value,
                "password": "abc",
                "password_confirm": "abc",
            },
        )
        assert resp.status_code == 200
        assert "8 caract".encode() in resp.data

    def test_create_non_admin_forbidden(self, client_verif_adm: FlaskClient) -> None:
        resp = client_verif_adm.post(
            "/admin/users/new",
            data={
                "prenom": "X",
                "nom": "Y",
                "email": "xy@bff.fr",
                "role": Role.LECTEUR.value,
                "password": "Pass1234!",
                "password_confirm": "Pass1234!",
            },
        )
        assert resp.status_code == 403


# ── Édition d'un utilisateur ──────────────────────────────────────────────


class TestUserEdit:
    def test_get_form(
        self, client_admin: FlaskClient, user_target: User
    ) -> None:
        resp = client_admin.get(f"/admin/users/{user_target.id}/edit")
        assert resp.status_code == 200
        assert user_target.email.encode() in resp.data

    def test_edit_role(
        self, client_admin: FlaskClient, user_target: User
    ) -> None:
        resp = client_admin.post(
            f"/admin/users/{user_target.id}/edit",
            data={
                "prenom": user_target.prenom,
                "nom": user_target.nom,
                "email": user_target.email,
                "role": Role.VERIFICATEUR.value,
                "actif": "y",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        _db.session.expire(user_target)
        assert user_target.role is Role.VERIFICATEUR

    def test_edit_404(self, client_admin: FlaskClient) -> None:
        resp = client_admin.get("/admin/users/99999/edit")
        assert resp.status_code == 404


# ── Toggle actif / inactif ────────────────────────────────────────────────


class TestUserToggle:
    def test_toggle_deactivate(
        self, client_admin: FlaskClient, user_target: User
    ) -> None:
        assert user_target.actif is True
        resp = client_admin.post(f"/admin/users/{user_target.id}/toggle")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["actif"] is False
        _db.session.expire(user_target)
        assert user_target.actif is False

    def test_toggle_reactivate(
        self, client_admin: FlaskClient, user_target: User
    ) -> None:
        user_target.actif = False
        _db.session.commit()
        resp = client_admin.post(f"/admin/users/{user_target.id}/toggle")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["actif"] is True

    def test_cannot_toggle_self(
        self, client_admin: FlaskClient, user_admin: User
    ) -> None:
        resp = client_admin.post(f"/admin/users/{user_admin.id}/toggle")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False


# ── Reset mot de passe ────────────────────────────────────────────────────


class TestResetPassword:
    def test_reset_ok(
        self, client_admin: FlaskClient, user_target: User
    ) -> None:
        resp = client_admin.post(
            f"/admin/users/{user_target.id}/reset-pwd",
            data={
                "password": "NewSecure1!",
                "password_confirm": "NewSecure1!",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        _db.session.expire(user_target)
        assert user_target.check_password("NewSecure1!")

    def test_reset_mismatch(
        self, client_admin: FlaskClient, user_target: User
    ) -> None:
        resp = client_admin.post(
            f"/admin/users/{user_target.id}/reset-pwd",
            data={
                "password": "NewSecure1!",
                "password_confirm": "Different!",
            },
        )
        assert resp.status_code == 200
        assert "ne correspondent pas".encode() in resp.data


# ── Journal d'audit global ────────────────────────────────────────────────


class TestAuditLog:
    def test_audit_requires_admin(self, client_verif_adm: FlaskClient) -> None:
        resp = client_verif_adm.get("/admin/audit")
        assert resp.status_code == 403

    def test_audit_ok(self, client_admin: FlaskClient) -> None:
        resp = client_admin.get("/admin/audit")
        assert resp.status_code == 200
        assert "Journal d'audit".encode() in resp.data

    def test_audit_filter_action(self, client_admin: FlaskClient) -> None:
        resp = client_admin.get("/admin/audit?action=auth.login")
        assert resp.status_code == 200

    def test_audit_filter_entity(self, client_admin: FlaskClient) -> None:
        resp = client_admin.get("/admin/audit?entity_type=affaire")
        assert resp.status_code == 200
