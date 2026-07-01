"""Tests d'intégration — API REST /api/v1/ (lecture seule, auth par jeton)."""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Chapitre, Role, Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.formulaire import Formulaire
from app.models.user import User
from app.services import jalons as jalon_svc


@pytest.fixture()
def api_token(app: Flask, affaire: Affaire) -> str:
    """Crée un utilisateur avec jeton d'API et retourne le jeton en clair."""
    u = User(email="api@bff.fr", prenom="Api", nom="User", role=Role.APPROBATEUR, actif=True)
    u.set_password("Test1234!")
    token = u.issue_api_token()
    db.session.add(u)
    db.session.commit()
    return token


@pytest.fixture()
def affaire_riche(app: Flask, affaire: Affaire) -> Affaire:
    """Affaire enrichie d'un formulaire signé et des jalons JP0–JP6."""
    f = Formulaire(
        affaire_id=affaire.id,
        code="HYDR",
        chapitre=Chapitre.E,
        statut=Statut.SIGNE,
        data={"ps": 10.0, "pt": 14.3, "fluide": "eau"},
        template_version=1,
    )
    db.session.add(f)
    jalon_svc.init_jalons_affaire(affaire)
    db.session.commit()
    return affaire


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestHealth:
    def test_health_sans_auth(self, client: FlaskClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "version" in data


class TestAuth:
    def test_sans_jeton_401(self, client: FlaskClient) -> None:
        resp = client.get("/api/v1/affaires")
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == 401

    def test_jeton_invalide_401(self, client: FlaskClient) -> None:
        resp = client.get("/api/v1/affaires", headers=_auth("mauvais-jeton"))
        assert resp.status_code == 401

    def test_jeton_valide_200(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires", headers=_auth(api_token))
        assert resp.status_code == 200

    def test_jeton_via_x_api_key(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires", headers={"X-API-Key": api_token})
        assert resp.status_code == 200

    def test_jeton_revoque_401(self, client: FlaskClient, api_token: str) -> None:
        u = db.session.query(User).filter_by(email="api@bff.fr").first()
        assert u is not None
        u.revoke_api_token()
        db.session.commit()
        resp = client.get("/api/v1/affaires", headers=_auth(api_token))
        assert resp.status_code == 401


class TestListAffaires:
    def test_liste_contient_affaire(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires", headers=_auth(api_token))
        data = resp.get_json()
        assert data["total"] >= 1
        assert any(a["numero_affaire"] == "BN2026-001" for a in data["items"])

    def test_pagination_bornee(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires?per_page=999", headers=_auth(api_token))
        assert resp.get_json()["per_page"] == 100  # plafonné

    def test_filtre_statut_invalide_400(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires?statut=nexiste_pas", headers=_auth(api_token))
        assert resp.status_code == 400

    def test_filtre_statut_valide(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires?statut=brouillon", headers=_auth(api_token))
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 1


class TestGetAffaire:
    def test_detail(self, client: FlaskClient, api_token: str, affaire_riche: Affaire) -> None:
        resp = client.get(f"/api/v1/affaires/{affaire_riche.id}", headers=_auth(api_token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["numero_affaire"] == "BN2026-001"
        assert "formulaires" in data and len(data["formulaires"]) == 1
        assert data["formulaires"][0]["code"] == "HYDR"
        assert "jalons" in data and len(data["jalons"]) == 7
        assert data["avancement"]["formulaires_signes"] == 1

    def test_introuvable_404(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires/99999", headers=_auth(api_token))
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == 404


class TestSousRessources:
    def test_formulaires(self, client: FlaskClient, api_token: str, affaire_riche: Affaire) -> None:
        resp = client.get(
            f"/api/v1/affaires/{affaire_riche.id}/formulaires", headers=_auth(api_token)
        )
        assert resp.status_code == 200
        items = resp.get_json()["items"]
        assert items[0]["code"] == "HYDR"
        assert "data" not in items[0]  # le contenu n'est pas exposé

    def test_jalons_ordonnes(self, client: FlaskClient, api_token: str, affaire_riche: Affaire) -> None:
        resp = client.get(
            f"/api/v1/affaires/{affaire_riche.id}/jalons", headers=_auth(api_token)
        )
        assert resp.status_code == 200
        codes = [j["code"] for j in resp.get_json()["items"]]
        assert codes == ["JP0", "JP1", "JP2", "JP3", "JP4", "JP5", "JP6"]

    def test_formulaires_affaire_introuvable_404(self, client: FlaskClient, api_token: str) -> None:
        resp = client.get("/api/v1/affaires/99999/formulaires", headers=_auth(api_token))
        assert resp.status_code == 404


class TestOpenApi:
    def test_openapi_sans_auth(self, client: FlaskClient) -> None:
        resp = client.get("/api/v1/openapi.json")
        assert resp.status_code == 200
        spec = resp.get_json()
        assert spec["openapi"].startswith("3.")
        assert "/affaires" in spec["paths"]
