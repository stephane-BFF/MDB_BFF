"""Tests d'intégration — Blueprint jalons JP0-JP6."""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import JalonCode, Role, Statut, StatutJalon
from app.extensions import db as _db
from app.models.affaire import Affaire, ParametrageAffaire
from app.models.jalon import HoldPoint, Jalon
from app.models.user import User
from tests.conftest import _login, _make_user


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture()
def user_verificateur_j(app: Flask) -> User:
    return _make_user("verif_j@bff.fr", "Véra", "Jalons", Role.VERIFICATEUR)


@pytest.fixture()
def user_approbateur_j(app: Flask) -> User:
    return _make_user("appro_j@bff.fr", "Alain", "Jalons", Role.APPROBATEUR)


@pytest.fixture()
def user_lecteur_j(app: Flask) -> User:
    return _make_user("lecteur_j@bff.fr", "Luc", "Jalons", Role.LECTEUR)


@pytest.fixture()
def affaire_avec_jalons(app: Flask) -> Affaire:
    """Affaire BROUILLON avec 7 jalons JP0-JP6 initialisés."""
    from app.services.jalons import init_jalons_affaire

    owner = _make_user("owner_j@bff.fr", "Ow", "Jalons", Role.REDACTEUR)
    a = Affaire(
        numero_affaire="BN2026-JA1",
        annee=2026,
        client_nom="Client Jalons",
        statut=Statut.BROUILLON,
        cree_par_id=owner.id,
    )
    _db.session.add(a)
    _db.session.flush()
    _db.session.add(ParametrageAffaire(affaire_id=a.id, reponses={}, template_version=1))
    _db.session.flush()
    init_jalons_affaire(a)
    _db.session.commit()
    return a


@pytest.fixture()
def client_verif(client: FlaskClient, user_verificateur_j: User) -> FlaskClient:
    _login(client, user_verificateur_j.email)
    return client


@pytest.fixture()
def client_appro(client: FlaskClient, user_approbateur_j: User) -> FlaskClient:
    _login(client, user_approbateur_j.email)
    return client


@pytest.fixture()
def client_lecteur_j(client: FlaskClient, user_lecteur_j: User) -> FlaskClient:
    _login(client, user_lecteur_j.email)
    return client


# ── Index ─────────────────────────────────────────────────────────────────


class TestJalonsIndex:
    def test_requires_auth(self, client: FlaskClient, affaire_avec_jalons: Affaire) -> None:
        resp = client.get(f"/affaires/{affaire_avec_jalons.id}/jalons/")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_index_shows_seven_jalons(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.get(f"/affaires/{affaire_avec_jalons.id}/jalons/")
        assert resp.status_code == 200
        for code in ("JP0", "JP1", "JP2", "JP3", "JP4", "JP5", "JP6"):
            assert code.encode() in resp.data

    def test_index_404_unknown_affaire(self, client_verif: FlaskClient) -> None:
        resp = client_verif.get("/affaires/99999/jalons/")
        assert resp.status_code == 404


# ── Franchir ─────────────────────────────────────────────────────────────


class TestJalonsFranchir:
    def test_franchir_jp0_sans_prerequis(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        """JP0 n'a aucun prérequis → franchissement immédiat."""
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/franchir",
            data={"commentaire": "Test JP0"},
        )
        assert resp.status_code == 302
        jp0 = (
            _db.session.query(Jalon)
            .filter_by(affaire_id=affaire_avec_jalons.id, code=JalonCode.JP0)
            .first()
        )
        assert jp0 is not None
        assert jp0.statut is StatutJalon.FRANCHI

    def test_franchir_jp1_prerequis_manquants(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        """JP1 requiert BIM + LISTSOUD → refusé si formulaires absents."""
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP1/franchir",
            data={},
        )
        assert resp.status_code == 302
        jp1 = (
            _db.session.query(Jalon)
            .filter_by(affaire_id=affaire_avec_jalons.id, code=JalonCode.JP1)
            .first()
        )
        assert jp1 is not None
        assert jp1.statut is not StatutJalon.FRANCHI

    def test_franchir_lecteur_forbidden(
        self, client_lecteur_j: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_lecteur_j.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/franchir",
            data={},
        )
        assert resp.status_code == 403

    def test_franchir_code_invalide(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JPXX/franchir",
            data={},
        )
        assert resp.status_code == 404

    def test_franchir_json_response(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        """Retourne JSON si requête XHR."""
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/franchir",
            data={},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["statut"] == StatutJalon.FRANCHI.value


# ── Update date prévue ────────────────────────────────────────────────────


class TestJalonsUpdateDate:
    def test_update_date_ok(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.patch(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/date",
            json={"date_prevue": "2026-09-15"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["date_prevue"] == "2026-09-15"

    def test_update_date_clear(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.patch(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/date",
            json={"date_prevue": ""},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["date_prevue"] is None

    def test_update_date_invalide(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.patch(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/date",
            json={"date_prevue": "pas-une-date"},
        )
        assert resp.status_code == 400

    def test_update_date_lecteur_forbidden(
        self, client_lecteur_j: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_lecteur_j.patch(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/date",
            json={"date_prevue": "2026-09-15"},
        )
        assert resp.status_code == 403


# ── Hold Points ───────────────────────────────────────────────────────────


class TestHoldPoints:
    def test_creer_hold_point_ok(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/hold-point",
            json={"organisme": "LRQA", "nom_inspecteur": "Jean Dupont", "date_inspection": "2026-10-01"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["hold_point"]["organisme"] == "LRQA"
        assert data["hold_point"]["signe"] is False

    def test_creer_hold_point_sans_organisme(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/hold-point",
            json={"organisme": "", "nom_inspecteur": "Jean"},
        )
        assert resp.status_code == 400

    def test_creer_hold_point_date_invalide(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/hold-point",
            json={"organisme": "BV", "date_inspection": "not-a-date"},
        )
        assert resp.status_code == 400

    def test_creer_hold_point_lecteur_forbidden(
        self, client_lecteur_j: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_lecteur_j.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/hold-point",
            json={"organisme": "LRQA"},
        )
        assert resp.status_code == 403


class TestSignerHoldPoint:
    @pytest.fixture()
    def hold_point(self, app: Flask, affaire_avec_jalons: Affaire) -> HoldPoint:
        jp0 = (
            _db.session.query(Jalon)
            .filter_by(affaire_id=affaire_avec_jalons.id, code=JalonCode.JP0)
            .first()
        )
        assert jp0 is not None
        hp = HoldPoint(jalon_id=jp0.id, organisme="LRQA Test")
        _db.session.add(hp)
        _db.session.commit()
        return hp

    def test_signer_approbateur_ok(
        self, client_appro: FlaskClient, affaire_avec_jalons: Affaire, hold_point: HoldPoint
    ) -> None:
        resp = client_appro.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/hold-point/{hold_point.id}/signer",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["signe"] is True

    def test_signer_verificateur_forbidden(
        self, client_verif: FlaskClient, affaire_avec_jalons: Affaire, hold_point: HoldPoint
    ) -> None:
        """Vérificateur ne peut pas signer un hold point — APPROBATEUR requis."""
        resp = client_verif.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/hold-point/{hold_point.id}/signer",
        )
        assert resp.status_code == 403

    def test_signer_hp_inconnu(
        self, client_appro: FlaskClient, affaire_avec_jalons: Affaire
    ) -> None:
        resp = client_appro.post(
            f"/affaires/{affaire_avec_jalons.id}/jalons/JP0/hold-point/99999/signer",
        )
        assert resp.status_code == 404
