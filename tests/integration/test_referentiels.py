"""Tests d'intégration — Blueprint référentiels (Soudeur, OperateurCND, Materiau, Instrument)."""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Role
from app.extensions import db as _db
from app.models.referentiel import Instrument, Materiau, OperateurCND, Soudeur
from app.models.user import User
from tests.conftest import _login, _make_user


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture()
def user_appro_r(app: Flask) -> User:
    return _make_user("appro_ref@bff.fr", "App", "Ref", Role.APPROBATEUR)


@pytest.fixture()
def user_verif_r(app: Flask) -> User:
    return _make_user("verif_ref@bff.fr", "Ver", "Ref", Role.VERIFICATEUR)


@pytest.fixture()
def client_appro_r(client: FlaskClient, user_appro_r: User) -> FlaskClient:
    _login(client, user_appro_r.email)
    return client


@pytest.fixture()
def client_verif_r(client: FlaskClient, user_verif_r: User) -> FlaskClient:
    _login(client, user_verif_r.email)
    return client


@pytest.fixture()
def soudeur_db(app: Flask) -> Soudeur:
    s = Soudeur(nom="Jean Martin", qualification="WPQR-001")
    _db.session.add(s)
    _db.session.commit()
    return s


@pytest.fixture()
def operateur_db(app: Flask) -> OperateurCND:
    o = OperateurCND(nom="Marie Dupont", qualification="RT", niveau="2")
    _db.session.add(o)
    _db.session.commit()
    return o


@pytest.fixture()
def materiau_db(app: Flask) -> Materiau:
    m = Materiau(designation="316L", norme="EN 10028-7")
    _db.session.add(m)
    _db.session.commit()
    return m


@pytest.fixture()
def instrument_db(app: Flask) -> Instrument:
    i = Instrument(reference="MAN-001", type_instrument="Manomètre")
    _db.session.add(i)
    _db.session.commit()
    return i


# ── Index ─────────────────────────────────────────────────────────────────


class TestReferentielsIndex:
    def test_requires_auth(self, client: FlaskClient) -> None:
        resp = client.get("/referentiels/")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_index_ok(self, client_verif_r: FlaskClient) -> None:
        resp = client_verif_r.get("/referentiels/")
        assert resp.status_code == 200
        assert b"Soudeurs" in resp.data
        assert b"ND" in resp.data  # CND tab

    def test_index_shows_soudeur(
        self, client_verif_r: FlaskClient, soudeur_db: Soudeur
    ) -> None:
        resp = client_verif_r.get("/referentiels/")
        assert resp.status_code == 200
        assert b"Jean Martin" in resp.data


# ── Soudeurs ──────────────────────────────────────────────────────────────


class TestSoudeurs:
    def test_create_ok(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/soudeurs",
            json={"nom": "Pierre Renaud", "qualification": "WPQR-002", "indice": "A"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert "id" in data
        s = _db.session.get(Soudeur, data["id"])
        assert s is not None
        assert s.nom == "Pierre Renaud"
        assert s.actif is True

    def test_create_missing_fields(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/soudeurs",
            json={"nom": ""},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_create_verif_forbidden(self, client_verif_r: FlaskClient) -> None:
        resp = client_verif_r.post(
            "/referentiels/soudeurs",
            json={"nom": "Test", "qualification": "Q1"},
        )
        assert resp.status_code == 403

    def test_update_ok(self, client_appro_r: FlaskClient, soudeur_db: Soudeur) -> None:
        resp = client_appro_r.patch(
            f"/referentiels/soudeurs/{soudeur_db.id}",
            json={"nom": "Jean Martin Modifié"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        _db.session.expire(soudeur_db)
        assert soudeur_db.nom == "Jean Martin Modifié"

    def test_update_404(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.patch(
            "/referentiels/soudeurs/99999",
            json={"nom": "Ghost"},
        )
        assert resp.status_code == 404

    def test_delete_soft(self, client_appro_r: FlaskClient, soudeur_db: Soudeur) -> None:
        """DELETE désactive logiquement (actif=False), ne supprime pas la ligne."""
        resp = client_appro_r.delete(f"/referentiels/soudeurs/{soudeur_db.id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        _db.session.expire(soudeur_db)
        assert soudeur_db.actif is False
        # La ligne est toujours en base
        assert _db.session.get(Soudeur, soudeur_db.id) is not None

    def test_delete_verif_forbidden(
        self, client_verif_r: FlaskClient, soudeur_db: Soudeur
    ) -> None:
        resp = client_verif_r.delete(f"/referentiels/soudeurs/{soudeur_db.id}")
        assert resp.status_code == 403


# ── Opérateurs CND ────────────────────────────────────────────────────────


class TestOperateursCND:
    def test_create_ok(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/operateurs-cnd",
            json={"nom": "Paul Leclerc", "qualification": "UT", "niveau": "2"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True

    def test_create_missing_niveau(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/operateurs-cnd",
            json={"nom": "Test", "qualification": "RT"},
        )
        assert resp.status_code == 400

    def test_update_ok(self, client_appro_r: FlaskClient, operateur_db: OperateurCND) -> None:
        resp = client_appro_r.patch(
            f"/referentiels/operateurs-cnd/{operateur_db.id}",
            json={"niveau": "3"},
        )
        assert resp.status_code == 200
        _db.session.expire(operateur_db)
        assert operateur_db.niveau == "3"

    def test_delete_soft(self, client_appro_r: FlaskClient, operateur_db: OperateurCND) -> None:
        resp = client_appro_r.delete(f"/referentiels/operateurs-cnd/{operateur_db.id}")
        assert resp.status_code == 200
        _db.session.expire(operateur_db)
        assert operateur_db.actif is False


# ── Matériaux ─────────────────────────────────────────────────────────────


class TestMateriaux:
    def test_create_ok(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/materiaux",
            json={"designation": "304L", "norme": "EN 10028-7", "certificat": "3.1"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True

    def test_create_missing_norme(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/materiaux",
            json={"designation": "304L"},
        )
        assert resp.status_code == 400

    def test_update_ok(self, client_appro_r: FlaskClient, materiau_db: Materiau) -> None:
        resp = client_appro_r.patch(
            f"/referentiels/materiaux/{materiau_db.id}",
            json={"certificat": "3.2"},
        )
        assert resp.status_code == 200
        _db.session.expire(materiau_db)
        assert materiau_db.certificat == "3.2"

    def test_delete_soft(self, client_appro_r: FlaskClient, materiau_db: Materiau) -> None:
        resp = client_appro_r.delete(f"/referentiels/materiaux/{materiau_db.id}")
        assert resp.status_code == 200
        _db.session.expire(materiau_db)
        assert materiau_db.actif is False


# ── Instruments ───────────────────────────────────────────────────────────


class TestInstruments:
    def test_create_ok(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/instruments",
            json={"reference": "MAN-002", "type_instrument": "Thermomètre", "date_prochain_etalonnage": "2027-01-01"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True

    def test_create_missing_type(self, client_appro_r: FlaskClient) -> None:
        resp = client_appro_r.post(
            "/referentiels/instruments",
            json={"reference": "MAN-002"},
        )
        assert resp.status_code == 400

    def test_update_date_etalonnage(
        self, client_appro_r: FlaskClient, instrument_db: Instrument
    ) -> None:
        resp = client_appro_r.patch(
            f"/referentiels/instruments/{instrument_db.id}",
            json={"date_prochain_etalonnage": "2026-12-31"},
        )
        assert resp.status_code == 200
        _db.session.expire(instrument_db)
        assert str(instrument_db.date_prochain_etalonnage) == "2026-12-31"

    def test_delete_soft(
        self, client_appro_r: FlaskClient, instrument_db: Instrument
    ) -> None:
        resp = client_appro_r.delete(f"/referentiels/instruments/{instrument_db.id}")
        assert resp.status_code == 200
        _db.session.expire(instrument_db)
        assert instrument_db.actif is False

    def test_statut_expiration_response(
        self, client_appro_r: FlaskClient, instrument_db: Instrument
    ) -> None:
        resp = client_appro_r.patch(
            f"/referentiels/instruments/{instrument_db.id}",
            json={"date_prochain_etalonnage": "2099-12-31"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["statut_expiration"] == "ok"
