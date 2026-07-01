"""Tests d'intégration — flux 2FA TOTP (login à deux étapes + enrôlement)."""
from __future__ import annotations

import pyotp
import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Role
from app.extensions import db
from app.models.audit import AuditTrail
from app.models.user import User

_SECRET = "JBSWY3DPEHPK3PXP"  # secret TOTP de test déterministe


@pytest.fixture()
def user_2fa(app: Flask) -> User:  # noqa: ARG001
    """Approbateur avec 2FA activée (secret connu)."""
    u = User(email="appro2fa@bff.fr", prenom="A", nom="B", role=Role.APPROBATEUR, actif=True)
    u.set_password("Test1234!")
    u.totp_secret = _SECRET
    u.totp_enabled = True
    db.session.add(u)
    db.session.commit()
    return u


def _now_code() -> str:
    return pyotp.TOTP(_SECRET).now()


class TestLoginAvec2FA:
    def test_login_redirige_vers_2fa(self, client: FlaskClient, user_2fa: User) -> None:
        resp = client.post(
            "/auth/login",
            data={"email": user_2fa.email, "password": "Test1234!"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/auth/2fa" in resp.headers["Location"]

    def test_2fa_code_valide_connecte(self, client: FlaskClient, user_2fa: User) -> None:
        client.post("/auth/login", data={"email": user_2fa.email, "password": "Test1234!"})
        resp = client.post("/auth/2fa", data={"code": _now_code()}, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "/dashboard", "/dashboard/")
        # La session est désormais authentifiée : /affaires ne redirige plus vers login.
        resp2 = client.get("/affaires/", follow_redirects=False)
        assert resp2.status_code == 200

    def test_2fa_code_invalide_401(self, client: FlaskClient, user_2fa: User) -> None:
        client.post("/auth/login", data={"email": user_2fa.email, "password": "Test1234!"})
        resp = client.post("/auth/2fa", data={"code": "000000"})
        assert resp.status_code == 401

    def test_2fa_sans_challenge_redirige_login(self, client: FlaskClient) -> None:
        resp = client.get("/auth/2fa", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_2fa_echoue_est_audite(self, client: FlaskClient, user_2fa: User) -> None:
        client.post("/auth/login", data={"email": user_2fa.email, "password": "Test1234!"})
        client.post("/auth/2fa", data={"code": "000000"})
        trail = (
            db.session.query(AuditTrail)
            .filter_by(action="auth.2fa_failed", entity_id=user_2fa.id)
            .first()
        )
        assert trail is not None


class TestLoginBackupCode:
    def test_login_via_code_de_secours(self, client: FlaskClient, user_2fa: User) -> None:
        codes = user_2fa.generate_backup_codes()
        db.session.commit()

        client.post("/auth/login", data={"email": user_2fa.email, "password": "Test1234!"})
        resp = client.post("/auth/2fa", data={"code": codes[0]}, follow_redirects=False)
        assert resp.status_code == 302

        # Le code de secours est consommé (usage unique).
        u = db.session.get(User, user_2fa.id)
        assert u is not None
        assert u._hash_token(codes[0]) not in (u.backup_codes or [])


class TestEnrollment:
    def test_setup_affiche_qr(self, client: FlaskClient, app: Flask) -> None:
        from tests.conftest import _make_user

        u = _make_user("redac@bff.fr", "R", "D", Role.REDACTEUR)
        client.post("/auth/login", data={"email": u.email, "password": "Test1234!"})
        resp = client.get("/auth/2fa/setup")
        assert resp.status_code == 200
        assert b"data:image/png;base64" in resp.data

    def test_setup_active_2fa_avec_code_valide(self, client: FlaskClient, app: Flask) -> None:
        from tests.conftest import _make_user

        u = _make_user("redac2@bff.fr", "R", "D", Role.REDACTEUR)
        client.post("/auth/login", data={"email": u.email, "password": "Test1234!"})
        # GET pour générer le secret
        client.get("/auth/2fa/setup")
        fresh = db.session.get(User, u.id)
        assert fresh is not None and fresh.totp_secret is not None
        code = pyotp.TOTP(fresh.totp_secret).now()

        resp = client.post("/auth/2fa/setup", data={"code": code})
        assert resp.status_code == 200
        assert "activée".encode() in resp.data or b"secours" in resp.data
        fresh = db.session.get(User, u.id)
        assert fresh is not None and fresh.totp_enabled is True
        assert fresh.backup_codes and len(fresh.backup_codes) == 8


class TestLoginSansChangement:
    """Garde-fou : sans 2FA, le login reste direct (non régressif)."""

    def test_login_normal_va_au_dashboard(self, client: FlaskClient, app: Flask) -> None:
        from tests.conftest import _make_user

        u = _make_user("normal@bff.fr", "N", "O", Role.REDACTEUR)
        resp = client.post(
            "/auth/login",
            data={"email": u.email, "password": "Test1234!"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "/dashboard", "/dashboard/")
