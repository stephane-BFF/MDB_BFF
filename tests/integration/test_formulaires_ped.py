"""Tests d'intégration — formulaire PEDMOD (Déclaration UE de conformité).

Couvre :
- Workflow complet (affichage → brouillon → validation → signature → PDF)
- Pré-remplissage depuis parametrage (PS, millesime, lieu)
- Les 4 langues (FR/EN/DE/IT) et les 4 modules (A/D1/H/H1)
- Template PDF dédié (pdf/ped.html, pas _simple.html)
- Module A : validation sans champs ON (non requis)
- Modules D1/H/H1 : champs ON stockés correctement
"""
from __future__ import annotations

import json

import pytest
from flask.testing import FlaskClient

from app.enums import Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.formulaire import Formulaire
from app.services.formulaires.ped import PedModService


# ── Payload minimal valide (module A, FR) ─────────────────────────────────

_PAYLOAD_BASE: dict = {
    "module_ped": "A",
    "langue": "FR",
    "categorie_ped": "III",
    "date_signature": "2026-05-16",
    "ps": 10.0,
    "ts_max": 120.0,
    "ts_min": 5.0,
    "volume": 450.0,
    "dn": "DN200",
    "surface": 52.5,
    "groupe_fluide": "2",
    "millesime": "2014/68/UE",
    "lieu_signature": "Thonon-les-Bains",
    "signataire_nom": "Jean Dupont",
    "signataire_titre": "Directeur technique",
}


# ── Helpers ────────────────────────────────────────────────────────────────


def _save(client: FlaskClient, affaire_id: int, payload: dict) -> None:
    client.post(
        f"/affaires/{affaire_id}/formulaires/PEDMOD",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _valider(client: FlaskClient, affaire_id: int) -> None:
    client.post(
        f"/affaires/{affaire_id}/formulaires/PEDMOD/valider",
        follow_redirects=True,
    )


def _get_form(affaire_id: int) -> Formulaire | None:
    return (
        db.session.query(Formulaire)
        .filter_by(affaire_id=affaire_id, code="PEDMOD")
        .first()
    )


# ── Workflow complet ───────────────────────────────────────────────────────


class TestPedWorkflow:
    """Workflow standard BROUILLON → VALIDE → SIGNE pour PEDMOD."""

    def test_show_unauthenticated_redirects(
        self, client: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client.get(
            f"/affaires/{affaire.id}/formulaires/PEDMOD",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_show_authenticated_returns_200(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/formulaires/PEDMOD")
        assert resp.status_code == 200
        assert "PEDMOD" in resp.data.decode("utf-8")

    def test_save_creates_brouillon(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/PEDMOD",
            data=json.dumps(_PAYLOAD_BASE),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["statut"] == "brouillon"

    def test_unknown_keys_stripped(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        dirty = {**_PAYLOAD_BASE, "evil_injection": "<script>alert(1)</script>"}
        _save(client_redacteur, affaire.id, dirty)
        f = _get_form(affaire.id)
        assert f is not None
        assert "evil_injection" not in f.data

    def test_validate_ok(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_verificateur, affaire.id, _PAYLOAD_BASE)
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PEDMOD/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_form(affaire.id)
        assert f is not None
        assert f.statut is Statut.VALIDE

    def test_sign_ok(
        self, client_approbateur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_approbateur, affaire.id, _PAYLOAD_BASE)
        _valider(client_approbateur, affaire.id)
        resp = client_approbateur.post(
            f"/affaires/{affaire.id}/formulaires/PEDMOD/signer",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_form(affaire.id)
        assert f is not None
        assert f.statut is Statut.SIGNE
        assert len(f.signatures) == 1

    def test_hash_verifies_after_signing(
        self, client_approbateur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_approbateur, affaire.id, _PAYLOAD_BASE)
        _valider(client_approbateur, affaire.id)
        client_approbateur.post(
            f"/affaires/{affaire.id}/formulaires/PEDMOD/signer",
            follow_redirects=True,
        )
        f = _get_form(affaire.id)
        assert f is not None
        assert f.signatures[-1].verify(f) is True

    def test_pdf_accessible_from_valide(
        self, client_approbateur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_approbateur, affaire.id, _PAYLOAD_BASE)
        _valider(client_approbateur, affaire.id)
        resp = client_approbateur.get(
            f"/affaires/{affaire.id}/formulaires/PEDMOD/pdf"
        )
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            assert resp.content_type == "application/pdf"


# ── Pré-remplissage ────────────────────────────────────────────────────────


class TestPedPrefill:
    """Vérifie le pré-remplissage depuis ParametrageAffaire."""

    def test_ps_prefilled_from_q5(self, affaire: Affaire) -> None:
        data = PedModService.prefill_from_parametrage(affaire)
        # conftest crée ParametrageAffaire(reponses={"q5_ps_bar": 10.0})
        assert data.get("ps") == pytest.approx(10.0)

    def test_millesime_default(self, affaire: Affaire) -> None:
        data = PedModService.prefill_from_parametrage(affaire)
        assert data.get("millesime") == "2014/68/UE"

    def test_lieu_default(self, affaire: Affaire) -> None:
        data = PedModService.prefill_from_parametrage(affaire)
        assert data.get("lieu_signature") == "Thonon-les-Bains"

    def test_no_parametrage_returns_defaults_only(self, app, user_redacteur) -> None:
        from app.enums import Statut
        from app.models.affaire import Affaire as AffaireModel

        a = AffaireModel(
            numero_affaire="BN2026-099",
            annee=2026,
            client_nom="Test",
            repere="REP",
            type_echangeur="H1",
            nombre=1,
            annee_construction=2026,
            statut=Statut.BROUILLON,
            cree_par_id=user_redacteur.id,
        )
        db.session.add(a)
        db.session.commit()

        data = PedModService.prefill_from_parametrage(a)
        assert "ps" not in data
        assert data.get("millesime") == "2014/68/UE"
        assert data.get("lieu_signature") == "Thonon-les-Bains"


# ── Langues ────────────────────────────────────────────────────────────────


class TestPedLangues:
    """Vérifie que les 4 langues sauvegardent et valident correctement."""

    @pytest.mark.parametrize("langue", ["FR", "EN", "DE", "IT"])
    def test_langue_saves_and_validates(
        self, client_verificateur: FlaskClient, affaire: Affaire, langue: str
    ) -> None:
        payload = {**_PAYLOAD_BASE, "langue": langue}
        _save(client_verificateur, affaire.id, payload)
        _valider(client_verificateur, affaire.id)
        f = _get_form(affaire.id)
        assert f is not None
        assert f.statut is Statut.VALIDE
        assert f.data.get("langue") == langue


# ── Modules ────────────────────────────────────────────────────────────────


class TestPedModules:
    """Vérifie que les 4 modules PED fonctionnent à la validation."""

    @pytest.mark.parametrize("module", ["A", "D1", "H", "H1"])
    def test_module_validates(
        self, client_verificateur: FlaskClient, affaire: Affaire, module: str
    ) -> None:
        payload = {**_PAYLOAD_BASE, "module_ped": module}
        _save(client_verificateur, affaire.id, payload)
        _valider(client_verificateur, affaire.id)
        f = _get_form(affaire.id)
        assert f is not None
        assert f.statut is Statut.VALIDE
        assert f.data.get("module_ped") == module

    def test_module_d1_stores_on_fields(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        payload = {
            **_PAYLOAD_BASE,
            "module_ped": "D1",
            "on_nom": "Bureau Veritas",
            "on_numero": "0062",
            "on_certificat": "BV-QS-2026-001",
        }
        _save(client_redacteur, affaire.id, payload)
        f = _get_form(affaire.id)
        assert f is not None
        assert f.data.get("on_nom") == "Bureau Veritas"
        assert f.data.get("on_numero") == "0062"
        assert f.data.get("on_certificat") == "BV-QS-2026-001"

    def test_module_h1_stores_on_certificat(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        payload = {
            **_PAYLOAD_BASE,
            "module_ped": "H1",
            "on_nom": "TÜV Rheinland",
            "on_numero": "0035",
            "on_certificat": "TUV-H1-CE-2026-999",
        }
        _save(client_redacteur, affaire.id, payload)
        f = _get_form(affaire.id)
        assert f is not None
        assert f.data.get("on_certificat") == "TUV-H1-CE-2026-999"


# ── Template PDF ───────────────────────────────────────────────────────────


class TestPedPdfTemplate:
    """Vérifie que PEDMOD utilise le template PDF dédié."""

    def test_get_pdf_template(self) -> None:
        assert PedModService.get_pdf_template() == "pdf/ped.html"

    def test_get_web_template(self) -> None:
        assert PedModService.get_web_template() == "formulaires/_simple.html"


# ── Validation — champs requis ─────────────────────────────────────────────


class TestPedValidationRequired:
    """Vérifie que les champs obligatoires bloquent la validation."""

    def test_validate_without_module_ped_fails(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        payload = {k: v for k, v in _PAYLOAD_BASE.items() if k != "module_ped"}
        _save(client_verificateur, affaire.id, payload)
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PEDMOD/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_form(affaire.id)
        assert f is None or f.statut is Statut.BROUILLON

    def test_validate_without_date_signature_fails(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        payload = {k: v for k, v in _PAYLOAD_BASE.items() if k != "date_signature"}
        _save(client_verificateur, affaire.id, payload)
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/PEDMOD/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_form(affaire.id)
        assert f is None or f.statut is Statut.BROUILLON
