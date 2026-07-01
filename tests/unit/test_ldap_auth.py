"""Tests unitaires — service d'authentification LDAP/AD (bind mocké).

Aucun serveur Active Directory n'est requis : la fonction de bind réelle
(``_ldap_bind``) est patchée. On couvre les deux stratégies (locale et LDAP)
et les codes d'échec exposés à l'audit.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask

from app.enums import Role
from app.extensions import db
from app.models.user import User
from app.services import ldap_auth
from app.services.ldap_auth import AuthMethod, LdapUnreachableError, authenticate


@pytest.fixture()
def bob(app: Flask) -> User:  # noqa: ARG001
    u = User(email="bob@bff.fr", prenom="Bob", nom="B", role=Role.REDACTEUR, actif=True)
    u.set_password("Secret123!")
    db.session.add(u)
    db.session.commit()
    return u


class TestLocalStrategy:
    def test_succes_local(self, app: Flask, bob: User) -> None:
        with app.test_request_context():
            res = authenticate("bob@bff.fr", "Secret123!")
        assert res.success is True
        assert res.method is AuthMethod.LOCAL
        assert res.user is not None and res.user.id == bob.id

    def test_mauvais_mot_de_passe(self, app: Flask, bob: User) -> None:
        with app.test_request_context():
            res = authenticate("bob@bff.fr", "faux")
        assert res.success is False
        assert res.reason == "bad_password"
        assert res.user is not None  # user résolu pour l'audit

    def test_utilisateur_inconnu(self, app: Flask) -> None:
        with app.test_request_context():
            res = authenticate("inconnu@bff.fr", "peu-importe")
        assert res.success is False
        assert res.reason == "user_not_found"
        assert res.user is None

    def test_mot_de_passe_vide_rejete(self, app: Flask, bob: User) -> None:
        with app.test_request_context():
            res = authenticate("bob@bff.fr", "")
        assert res.success is False
        assert res.reason == "empty_password"

    def test_email_insensible_a_la_casse(self, app: Flask, bob: User) -> None:
        with app.test_request_context():
            res = authenticate("BOB@BFF.FR", "Secret123!")
        assert res.success is True


class TestLdapStrategy:
    def test_succes_ldap(self, app: Flask, bob: User) -> None:
        app.config["WINDOWS_AUTH_ENABLED"] = True
        with app.test_request_context(), patch.object(
            ldap_auth, "_ldap_bind", return_value=True
        ) as mock_bind:
            res = authenticate("bob@bff.fr", "AnyADPassword")
        assert res.success is True
        assert res.method is AuthMethod.LDAP
        mock_bind.assert_called_once()

    def test_echec_bind_ldap(self, app: Flask, bob: User) -> None:
        app.config["WINDOWS_AUTH_ENABLED"] = True
        with app.test_request_context(), patch.object(
            ldap_auth, "_ldap_bind", return_value=False
        ):
            res = authenticate("bob@bff.fr", "mauvais")
        assert res.success is False
        assert res.reason == "bad_password"

    def test_serveur_injoignable(self, app: Flask, bob: User) -> None:
        app.config["WINDOWS_AUTH_ENABLED"] = True
        with app.test_request_context(), patch.object(
            ldap_auth, "_ldap_bind", side_effect=LdapUnreachableError("timeout")
        ):
            res = authenticate("bob@bff.fr", "x")
        assert res.success is False
        assert res.reason == "ldap_unreachable"

    def test_compte_absent_meme_si_bind_ok(self, app: Flask) -> None:
        app.config["WINDOWS_AUTH_ENABLED"] = True
        with app.test_request_context(), patch.object(
            ldap_auth, "_ldap_bind", return_value=True
        ):
            res = authenticate("fantome@bff.fr", "x")
        assert res.success is False
        assert res.reason == "user_not_found"


class TestLdapBindGuards:
    def test_bind_sans_serveur_configure_leve(self, app: Flask) -> None:
        app.config["WINDOWS_AUTH_ENABLED"] = True
        app.config["LDAP_SERVER"] = ""
        with app.test_request_context(), pytest.raises(LdapUnreachableError):
            ldap_auth._ldap_bind("bob@bff.fr", "x")
