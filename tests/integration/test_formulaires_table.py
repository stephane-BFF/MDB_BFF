"""Tests d'intégration — formulaires tableau dynamique (gabarit _table.html).

Couvre le workflow complet (affichage → brouillon → validation → signature → PDF)
pour BIM, BIMSoud et PMI (``TableFormulaireService``).

Chaque cas fournit le payload minimal qui satisfait la validation :
- BIM / BIMSoud : ``{"lignes": [...]}`` avec les colonnes ``required``
- PMI : ``{"header": {...}, "lignes": [...]}`` avec en-tête requis
"""
from __future__ import annotations

import json

import pytest
from flask.testing import FlaskClient

from app.enums import Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.formulaire import Formulaire


# ── Cas de tests ───────────────────────────────────────────────────────────

_TABLE_CASES: list[tuple[str, dict]] = [
    (
        "BIM",
        {
            "lignes": [
                {
                    "repere_composant": "CO-001",
                    "designation": "Corps intermédiaire",
                    "norme_materiau": "EN 10028-2",
                    "num_coulee": "A123456",
                },
            ]
        },
    ),
    (
        "BIMSOUD",
        {
            "lignes": [
                {
                    "designation": "Électrode rutile 7018",
                    "norme": "EN ISO 2560-A",
                    "diametre": 3.2,
                    "num_lot": "LOT-2026-42",
                },
            ]
        },
    ),
    (
        "PMI",
        {
            "header": {
                "date_pmi": "2026-05-14",
                "procedure": "PMI-PROC-001",
            },
            "lignes": [
                {
                    "composant": "CO-001",
                    "grade_attendu": "P265GH",
                    "resultats": "P264GH",
                    "conformite": "conforme",
                },
            ],
        },
    ),
]

_IDS = [c[0] for c in _TABLE_CASES]


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


@pytest.mark.parametrize("code,payload", _TABLE_CASES, ids=_IDS)
class TestTableFormWorkflow:
    """Workflow complet sur chaque formulaire tableau."""

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
        assert code in resp.data.decode("utf-8")

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

    def test_lignes_stored_correctly(
        self, client_redacteur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/{code}",
            data=json.dumps(payload),
            content_type="application/json",
        )
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        assert "lignes" in f.data
        assert len(f.data["lignes"]) == len(payload["lignes"])

    def test_unknown_keys_stripped_in_lignes(
        self, client_redacteur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        dirty = json.loads(json.dumps(payload))  # deep copy
        dirty["lignes"][0]["evil_injection"] = "<script>alert(1)</script>"
        client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/{code}",
            data=json.dumps(dirty),
            content_type="application/json",
        )
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        for row in f.data.get("lignes", []):
            assert "evil_injection" not in row

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
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            assert resp.content_type == "application/pdf"


# ── Tests spécifiques ──────────────────────────────────────────────────────


class TestPmiHeaderValidation:
    """PMI : la validation échoue si les champs d'en-tête obligatoires sont absents."""

    def test_missing_header_flashes_danger(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        # Sauvegarde sans header requis
        client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PMI",
            data=json.dumps({
                "header": {},
                "lignes": [{"composant": "CO-001", "grade_attendu": "P265GH"}],
            }),
            content_type="application/json",
        )
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PMI/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "danger" in resp.data.decode("utf-8")

    def test_missing_lignes_flashes_danger(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        # Sauvegarde avec header correct mais aucune ligne
        client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PMI",
            data=json.dumps({
                "header": {"date_pmi": "2026-05-14", "procedure": "PMI-001"},
                "lignes": [],
            }),
            content_type="application/json",
        )
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PMI/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "danger" in resp.data.decode("utf-8")


class TestBimNoHeaderInData:
    """BIM : pas d'en-tête → la clé ``header`` ne doit pas apparaître dans data."""

    def test_no_header_key_in_bim_data(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/BIM",
            data=json.dumps({
                "lignes": [
                    {
                        "repere_composant": "X1",
                        "designation": "Bride entrée",
                        "norme_materiau": "EN 1092-1",
                        "num_coulee": "C9999",
                    }
                ]
            }),
            content_type="application/json",
        )
        f = _get_formulaire(affaire.id, "BIM")
        assert f is not None
        assert "header" not in f.data
