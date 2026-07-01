"""Tests unitaires — 2FA TOTP, codes de secours et jeton d'API du modèle User."""
from __future__ import annotations

import pyotp
import pytest
from flask import Flask

from app.enums import Role
from app.models.user import User


@pytest.fixture(autouse=True)
def _app_context(app: Flask) -> None:  # noqa: ARG001
    """Garantit que tous les mappers sont configurés (app importe les modèles).

    Sans cela, instancier ``User`` hors contexte déclenche une configuration
    de mapper incomplète (relation ``Affaire`` non résolue).
    """


def _user(role: Role = Role.APPROBATEUR) -> User:
    u = User(email="x@bff.fr", prenom="X", nom="Y", role=role, actif=True)
    u.set_password("Test1234!")
    return u


class TestRequires2FA:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (Role.LECTEUR, False),
            (Role.REDACTEUR, False),
            (Role.VERIFICATEUR, False),
            (Role.APPROBATEUR, True),
            (Role.ADMIN, True),
        ],
    )
    def test_requires_2fa_par_role(self, role: Role, expected: bool) -> None:
        assert _user(role).requires_2fa is expected


class TestTotp:
    def test_enrollment_genere_secret_non_actif(self) -> None:
        u = _user()
        secret = u.start_totp_enrollment()
        assert secret and len(secret) >= 16
        assert u.totp_secret == secret
        assert u.totp_enabled is False

    def test_provisioning_uri_sans_secret_leve(self) -> None:
        with pytest.raises(ValueError, match="Aucun secret"):
            _user().totp_provisioning_uri()

    def test_provisioning_uri_contient_issuer_et_email(self) -> None:
        u = _user()
        u.start_totp_enrollment()
        uri = u.totp_provisioning_uri(issuer="MDB BFF")
        assert uri.startswith("otpauth://totp/")
        assert "issuer=MDB%20BFF" in uri or "issuer=MDB+BFF" in uri

    def test_verify_totp_code_valide(self) -> None:
        u = _user()
        secret = u.start_totp_enrollment()
        code = pyotp.TOTP(secret).now()
        assert u.verify_totp(code) is True

    def test_verify_totp_code_invalide(self) -> None:
        u = _user()
        u.start_totp_enrollment()
        assert u.verify_totp("000000") is False

    def test_verify_totp_sans_secret(self) -> None:
        assert _user().verify_totp("123456") is False

    def test_confirm_totp_active_si_code_valide(self) -> None:
        u = _user()
        secret = u.start_totp_enrollment()
        assert u.confirm_totp(pyotp.TOTP(secret).now()) is True
        assert u.totp_enabled is True

    def test_confirm_totp_refuse_si_code_invalide(self) -> None:
        u = _user()
        u.start_totp_enrollment()
        assert u.confirm_totp("000000") is False
        assert u.totp_enabled is False

    def test_disable_totp_purge_tout(self) -> None:
        u = _user()
        secret = u.start_totp_enrollment()
        u.confirm_totp(pyotp.TOTP(secret).now())
        u.generate_backup_codes()
        u.disable_totp()
        assert u.totp_secret is None
        assert u.totp_enabled is False
        assert u.backup_codes is None


class TestBackupCodes:
    def test_generate_retourne_codes_clairs_et_stocke_hash(self) -> None:
        u = _user()
        codes = u.generate_backup_codes(count=8)
        assert len(codes) == 8
        assert all(c.isdigit() and len(c) == 8 for c in codes)
        # Les codes en clair ne doivent jamais être stockés tels quels.
        assert u.backup_codes is not None
        assert all(c not in u.backup_codes for c in codes)

    def test_consume_code_valide_une_seule_fois(self) -> None:
        u = _user()
        codes = u.generate_backup_codes()
        assert u.consume_backup_code(codes[0]) is True
        # Réutilisation refusée
        assert u.consume_backup_code(codes[0]) is False
        # Les autres restent utilisables
        assert u.consume_backup_code(codes[1]) is True

    def test_consume_code_inconnu(self) -> None:
        u = _user()
        u.generate_backup_codes()
        assert u.consume_backup_code("99999999") is False

    def test_consume_sans_codes(self) -> None:
        assert _user().consume_backup_code("12345678") is False


class TestApiToken:
    def test_issue_retourne_token_et_stocke_hash(self) -> None:
        u = _user()
        token = u.issue_api_token()
        assert token and len(token) >= 32
        assert u.api_token_hash is not None
        assert u.api_token_hash != token  # jamais en clair

    def test_check_api_token_valide(self) -> None:
        u = _user()
        token = u.issue_api_token()
        assert u.check_api_token(token) is True

    def test_check_api_token_invalide(self) -> None:
        u = _user()
        u.issue_api_token()
        assert u.check_api_token("mauvais-token") is False

    def test_check_sans_token_emis(self) -> None:
        assert _user().check_api_token("peu-importe") is False

    def test_revoke_supprime_le_hash(self) -> None:
        u = _user()
        token = u.issue_api_token()
        u.revoke_api_token()
        assert u.api_token_hash is None
        assert u.check_api_token(token) is False

    def test_reemission_revoque_lancien(self) -> None:
        u = _user()
        ancien = u.issue_api_token()
        nouveau = u.issue_api_token()
        assert u.check_api_token(ancien) is False
        assert u.check_api_token(nouveau) is True
