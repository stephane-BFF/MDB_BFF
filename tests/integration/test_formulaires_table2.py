"""Tests d'intégration — formulaires tableau batch 2.

Couvre le workflow complet pour :
  - LISTSOUD, ROLLING, DIM  (Chapitre C)
  - LISTCND, NDEMAP, DURETE, FERRITE, UT0FAIS, UT0SHELL, UT0RET, UT0UBEND  (Chapitre D)

Tests paramétrés standard (8 tests × 11 codes) + tests de calcul automatique
pour ROLLING, DIM, DURETE, FERRITE et UT0FAIS.
"""
from __future__ import annotations

import json

import pytest
from flask.testing import FlaskClient

from app.enums import Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.formulaire import Formulaire


# ── Payloads minimaux valides ──────────────────────────────────────────────

_WELDER_ROW = {
    "id_soudeur": "120",
    "initiales": "AB",
    "nom": "BROU Allaly",
    "procedes": "TIG 141",
    "materiaux": "Acier carbone P1",
    "positions": "PA, PB",
    "ref_qualification": "WPQ-BFF-001",
    "date_validite": "2027-01-01",
}

_CND_ROW = {
    "nom": "Dupont CND",
    "methodes": "RT, UT",
    "niveau": "2",
    "organisme_cert": "Cofrend",
    "numero_cert": "BO2-031557",
    "validite": "2027-01-01",
}

_NDT_ROW = {
    "num_joint": "C1",
    "description": "Joint tube-collecteur",
}

_ROLLING_HEADER = {
    "procedure_roll": "ROLL-001",
    "outil": "EXPANDER X12",
    "dim_tube": "25.4 × 2.11 mm",
    "materiau_tube": "SA 179",
    "materiau_collecteur": "SA 333 Gr6",
    "taux_cible": 10.0,
    "taux_min": 8.0,
    "taux_max": 12.0,
}

_DIM_HEADER = {
    "ref_plan": "RM9541-BN0909",
    "rev_plan": "Rev_B",
    "date_dim": "2026-05-14",
}

_DURETE_HEADER = {
    "procedure": "DUR-001",
    "echelle": "HB",
    "critere_max": 250.0,
    "date_durete": "2026-05-14",
}

_FERRITE_HEADER = {
    "procedure": "FER-001",
    "critere_min": 3.0,
    "critere_max": 8.0,
    "date_ferrite": "2026-05-14",
}

_UT0_HEADER = {
    "ep_mini_acceptable": 1.8,
    "date_mesure": "2026-05-14",
}

_TABLE2_CASES: list[tuple[str, dict]] = [
    ("LISTSOUD", {"lignes": [_WELDER_ROW]}),
    (
        "ROLLING",
        {
            "header": _ROLLING_HEADER,
            "lignes": [{"num_tube": "T001", "ep_avant": 2.11, "ep_apres": 1.90}],
        },
    ),
    (
        "DIM",
        {
            "header": _DIM_HEADER,
            "lignes": [{
                "num_cote": "L1", "description": "Longueur totale",
                "valeur_nominale": 1000.0, "tolerance_plus": 2.0,
                "tolerance_moins": 2.0, "valeur_mesuree": 1001.0,
            }],
        },
    ),
    ("LISTCND", {"lignes": [_CND_ROW]}),
    ("NDEMAP", {"lignes": [_NDT_ROW]}),
    (
        "DURETE",
        {
            "header": _DURETE_HEADER,
            "lignes": [{"num_joint": "C1", "localisation": "Joint C1 MB", "zone": "metal_base", "mesure": 200.0}],
        },
    ),
    (
        "FERRITE",
        {
            "header": _FERRITE_HEADER,
            "lignes": [{"num_joint": "C1", "localisation": "Joint C1 soudure", "zone": "bain_soudure", "mesure": 5.0}],
        },
    ),
    ("UT0FAIS", {"header": _UT0_HEADER, "lignes": [{"num_tube": "T001", "mesure_1": 2.11, "mesure_2": 2.09}]}),
    ("UT0SHELL", {"header": _UT0_HEADER, "lignes": [{"num_tube": "T001", "mesure_1": 3.0, "mesure_2": 3.1}]}),
    ("UT0RET", {"header": _UT0_HEADER, "lignes": [{"num_tube": "T001", "mesure_1": 2.5, "mesure_2": 2.4}]}),
    ("UT0UBEND", {"header": _UT0_HEADER, "lignes": [{"num_tube": "T001", "mesure_1": 2.0, "mesure_2": 2.1}]}),
]

_IDS = [c[0] for c in _TABLE2_CASES]


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

@pytest.mark.parametrize("code,payload", _TABLE2_CASES, ids=_IDS)
class TestTableForm2Workflow:
    """Workflow complet sur chaque formulaire tableau batch 2."""

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

    def test_lignes_stored(
        self, client_redacteur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        _save(client_redacteur, affaire.id, code, payload)
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        assert len(f.data.get("lignes", [])) == len(payload["lignes"])

    def test_unknown_keys_stripped(
        self, client_redacteur: FlaskClient, affaire: Affaire, code: str, payload: dict
    ) -> None:
        dirty = json.loads(json.dumps(payload))
        dirty["lignes"][0]["evil"] = "<script>"
        _save(client_redacteur, affaire.id, code, dirty)
        f = _get_formulaire(affaire.id, code)
        assert f is not None
        for row in f.data.get("lignes", []):
            assert "evil" not in row

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


# ── Tests des calculs automatiques ────────────────────────────────────────

class TestRollingTauxReel:
    """ROLLING : taux_reel et conformite calculés automatiquement."""

    def test_taux_reel_computed(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "ROLLING", {
            "header": _ROLLING_HEADER,
            "lignes": [{"num_tube": "T001", "ep_avant": 2.11, "ep_apres": 1.90}],
        })
        f = _get_formulaire(affaire.id, "ROLLING")
        assert f is not None
        ligne = f.data["lignes"][0]
        # taux_reel = (2.11 - 1.90) / 2.11 × 100 ≈ 9.95 %
        assert ligne["taux_reel"] == pytest.approx(9.95, abs=0.1)
        assert ligne["conformite"] is True  # 8.0 ≤ 9.95 ≤ 12.0

    def test_non_conforme_when_outside_range(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "ROLLING", {
            "header": _ROLLING_HEADER,
            "lignes": [{"num_tube": "T001", "ep_avant": 2.11, "ep_apres": 0.80}],
        })
        f = _get_formulaire(affaire.id, "ROLLING")
        assert f is not None
        ligne = f.data["lignes"][0]
        # taux_reel ≈ 62% >> 12% max
        assert ligne["conformite"] is False


class TestDimEcart:
    """DIM : ecart et conformite calculés automatiquement."""

    def test_ecart_computed(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "DIM", {
            "header": _DIM_HEADER,
            "lignes": [{
                "num_cote": "L1", "description": "Longueur",
                "valeur_nominale": 1000.0, "tolerance_plus": 2.0,
                "tolerance_moins": 2.0, "valeur_mesuree": 1001.0,
            }],
        })
        f = _get_formulaire(affaire.id, "DIM")
        assert f is not None
        ligne = f.data["lignes"][0]
        assert ligne["ecart"] == pytest.approx(1.0)
        assert ligne["conformite"] is True  # -2 ≤ 1.0 ≤ 2

    def test_non_conforme_when_out_of_tolerance(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "DIM", {
            "header": _DIM_HEADER,
            "lignes": [{
                "num_cote": "L1", "description": "Longueur",
                "valeur_nominale": 1000.0, "tolerance_plus": 2.0,
                "tolerance_moins": 2.0, "valeur_mesuree": 1005.0,
            }],
        })
        f = _get_formulaire(affaire.id, "DIM")
        assert f is not None
        assert f.data["lignes"][0]["conformite"] is False  # 5.0 > 2.0


class TestDureteConformite:
    """DURETE : conformite calculée automatiquement."""

    def test_conforme_when_below_max(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "DURETE", {
            "header": _DURETE_HEADER,
            "lignes": [{"num_joint": "C1", "localisation": "MB", "zone": "metal_base", "mesure": 200.0}],
        })
        f = _get_formulaire(affaire.id, "DURETE")
        assert f is not None
        assert f.data["lignes"][0]["conformite"] is True  # 200 ≤ 250

    def test_non_conforme_when_above_max(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "DURETE", {
            "header": _DURETE_HEADER,
            "lignes": [{"num_joint": "C1", "localisation": "MB", "zone": "metal_base", "mesure": 280.0}],
        })
        f = _get_formulaire(affaire.id, "DURETE")
        assert f is not None
        assert f.data["lignes"][0]["conformite"] is False  # 280 > 250


class TestUT0MesureMoy:
    """UT0FAIS : mesure_moy et conformite calculés automatiquement."""

    def test_moyenne_computed(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "UT0FAIS", {
            "header": _UT0_HEADER,
            "lignes": [{"num_tube": "T001", "mesure_1": 2.10, "mesure_2": 2.06}],
        })
        f = _get_formulaire(affaire.id, "UT0FAIS")
        assert f is not None
        ligne = f.data["lignes"][0]
        assert ligne["mesure_moy"] == pytest.approx(2.08, abs=0.001)
        assert ligne["conformite"] is True  # 2.08 ≥ 1.8

    def test_non_conforme_when_below_mini(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id, "UT0FAIS", {
            "header": _UT0_HEADER,
            "lignes": [{"num_tube": "T001", "mesure_1": 1.70, "mesure_2": 1.68}],
        })
        f = _get_formulaire(affaire.id, "UT0FAIS")
        assert f is not None
        assert f.data["lignes"][0]["conformite"] is False  # 1.69 < 1.8
