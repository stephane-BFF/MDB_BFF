"""Tests d'intégration — formulaires simples (gabarit générique _simple.html).

Couvre le workflow complet (affichage → brouillon → validation → signature → PDF)
pour tous les formulaires qui utilisent ``SimpleFormulaireService`` et
``formulaires/_simple.html``.

Un seul jeu de tests paramétrés sur 11 codes ; chaque tuple fournit le payload
minimal qui satisfait ``REQUIRED_FOR_VALIDATION`` du service correspondant.
"""
from __future__ import annotations

import json

import pytest
from flask.testing import FlaskClient

from app.enums import Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.formulaire import Formulaire


# ── Cas de tests : (code, payload minimal valide) ─────────────────────────

_SIMPLE_CASES: list[tuple[str, dict]] = [
    # Chapitre F — simples
    (
        "VISUFINAL",
        {
            "date_controle_visuel": "2026-05-14",
            "etat_general": "conforme",
            "etat_surface": "conforme",
            "peinture": "conforme",
        },
    ),
    (
        "PROPRETE",
        {
            "date_controle": "2026-05-14",
            "methode": "visuelle",
            "resultat": "conforme",
        },
    ),
    (
        "SECHAGE",
        {
            "date_sechage": "2026-05-14",
            "methode": "air_sec",
            "resultat": "conforme",
            "point_rosee_mesure": -35.0,
        },
    ),
    (
        "PESAGE",
        {
            "date_pesage": "2026-05-14",
            "poids_mesure": 500.0,
            "poids_plan": 490.0,
            "tolerance": 10.0,
        },
    ),
    # Chapitre A
    (
        "CONFCOM",
        {"date_emission": "2026-05-14"},
    ),
    (
        "ATTDECR",
        {"date_emission": "2026-05-14", "conformite_ped": True},
    ),
    (
        "ATTREP",
        {"date_emission": "2026-05-14", "nom_representant": "Marie Dupont"},
    ),
    (
        "ETATDESC",
        {"date_emission": "2026-05-14"},
    ),
    # Chapitre E — calculs / tests spéciaux
    (
        "AIRSAV",
        {
            "date_airsav": "2026-05-14",
            "pression_test": 3.0,
            "duree": 30.0,
            "resultat": "pas_de_fuite",
        },
    ),
    (
        "RECORDHYDRO",
        {
            "date_enregistrement": "2026-05-14",
            "echelle_pression": 20.0,
            "echelle_temps": 60.0,
            "pression_stabilisee": 14.3,
        },
    ),
    (
        "AZOTE",
        {
            "date_azote": "2026-05-14",
            "pression_azote": 0.5,
            "pression_verifiee": 0.5,
            "resultat": "conforme",
        },
    ),
    # Chapitre C — traitements thermiques
    (
        "TTH1",
        {
            "date_tth": "2026-05-14",
            "procedure_tth": "TTH-001",
            "type_tth": "pwht",
            "temperature_cible": 600.0,
            "duree_palier": 120.0,
            "resultat": "conforme",
        },
    ),
    (
        "TTH2",
        {
            "date_tth": "2026-05-14",
            "procedure_tth": "TTH-002",
            "type_tth": "detente",
            "temperature_cible": 250.0,
            "duree_palier": 60.0,
            "resultat": "conforme",
        },
    ),
]

_IDS = [c[0] for c in _SIMPLE_CASES]


# ── Helpers ────────────────────────────────────────────────────────────────


def _save(client: FlaskClient, affaire_id: int, code: str, payload: dict) -> None:
    client.post(
        f"/affaires/{affaire_id}/formulaires/{code}",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _valider(client: FlaskClient, affaire_id: int, code: str) -> None:
    client.post(
        f"/affaires/{affaire_id}/formulaires/{code}/valider",
        follow_redirects=True,
    )


def _get_formulaire(affaire_id: int, code: str) -> Formulaire | None:
    return (
        db.session.query(Formulaire)
        .filter_by(affaire_id=affaire_id, code=code)
        .first()
    )


# ── Tests paramétrés ───────────────────────────────────────────────────────


@pytest.mark.parametrize("code,payload", _SIMPLE_CASES, ids=_IDS)
class TestSimpleFormWorkflow:
    """Workflow complet sur chaque formulaire simple."""

    def test_show_unauthenticated_redirects(
        self, client: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        resp = client.get(
            f"/affaires/{affaire.id}/formulaires/{code}",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_show_authenticated_returns_200(
        self, client_redacteur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/formulaires/{code}")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        # Le code et le titre du formulaire doivent apparaître
        assert code in body

    def test_save_creates_brouillon(
        self, client_redacteur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/{code}",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["statut"] == "brouillon"

    def test_unknown_keys_stripped(
        self, client_redacteur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        dirty = {**payload, "evil_injection": "<script>alert(1)</script>"}
        client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/{code}",
            data=json.dumps(dirty),
            content_type="application/json",
        )
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        assert "evil_injection" not in f.data

    def test_validate_ok(
        self, client_verificateur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        _save(client_verificateur, affaire.id, code, payload)
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/{code}/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        assert f.statut is Statut.VALIDE

    def test_sign_ok(
        self, client_approbateur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        _save(client_approbateur, affaire.id, code, payload)
        _valider(client_approbateur, affaire.id, code)
        resp = client_approbateur.post(
            f"/affaires/{affaire.id}/formulaires/{code}/signer",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        assert f.statut is Statut.SIGNE
        assert len(f.signatures) == 1

    def test_hash_verifies_after_signing(
        self, client_approbateur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        _save(client_approbateur, affaire.id, code, payload)
        _valider(client_approbateur, affaire.id, code)
        client_approbateur.post(
            f"/affaires/{affaire.id}/formulaires/{code}/signer",
            follow_redirects=True,
        )
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        assert f.signatures[-1].verify(f) is True

    def test_pdf_accessible_from_valide(
        self, client_approbateur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        _save(client_approbateur, affaire.id, code, payload)
        _valider(client_approbateur, affaire.id, code)
        resp = client_approbateur.get(
            f"/affaires/{affaire.id}/formulaires/{code}/pdf"
        )
        # WeasyPrint peut être absent en CI → redirect avec flash danger
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            assert resp.content_type == "application/pdf"


# ── Tests ponctuels supplémentaires ───────────────────────────────────────


class TestPesageEcartCalcule:
    """Vérifie le calcul automatique de ecart_pct dans PESAGE."""

    def test_ecart_pct_computed(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/PESAGE",
            data=json.dumps({
                "date_pesage": "2026-05-14",
                "poids_mesure": 550.0,
                "poids_plan": 500.0,
                "tolerance": 15.0,
            }),
            content_type="application/json",
        )
        f = _get_formulaire(affaire.id, "PESAGE")
        assert f is not None
        # écart = |550-500| / 500 × 100 = 10 %
        assert f.data.get("ecart_pct") == pytest.approx(10.0)

    def test_missing_required_fields_flashes_danger(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        # Sauvegarde sans poids_plan → validation doit échouer
        client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PESAGE",
            data=json.dumps({"date_pesage": "2026-05-14", "poids_mesure": 500.0}),
            content_type="application/json",
        )
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PESAGE/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "danger" in resp.data.decode("utf-8")
