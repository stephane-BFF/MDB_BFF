"""Tests d'intégration — formulaire HYDR (Phase 1 pilote).

Couvre : affichage, sauvegarde AJAX + calcul PT, validation, signature + hash,
et accès à la route PDF.
"""
from __future__ import annotations

import json

import pytest
from flask.testing import FlaskClient

from app.enums import Role, Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.formulaire import Formulaire
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────

_VALID_PAYLOAD = {
    "ps": 10.0,
    "fluide": "eau",
    "date_epreuve": "2026-05-13",
    "conforme": True,
}


def _save(client: FlaskClient, affaire_id: int, payload: dict = _VALID_PAYLOAD) -> None:
    client.post(
        f"/affaires/{affaire_id}/formulaires/HYDR",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _valider(client: FlaskClient, affaire_id: int) -> None:
    client.post(
        f"/affaires/{affaire_id}/formulaires/HYDR/valider",
        follow_redirects=True,
    )


def _get_formulaire(affaire_id: int) -> Formulaire | None:
    return db.session.query(Formulaire).filter_by(affaire_id=affaire_id, code="HYDR").first()


# ── Affichage ─────────────────────────────────────────────────────────────


class TestHydrShow:
    def test_unauthenticated_redirects(
        self, client: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client.get(
            f"/affaires/{affaire.id}/formulaires/HYDR", follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_shows_form_when_authenticated(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/formulaires/HYDR")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "Pression" in body
        assert "hydrostatique" in body.lower()

    def test_unknown_code_returns_404(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/formulaires/NOEXIST")
        assert resp.status_code == 404

    def test_prefill_from_wizard_q5(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        # L'affaire fixture a q5_ps_bar=10.0 → PS=10.0 et PT=14.3 pré-remplis.
        resp = client_redacteur.get(f"/affaires/{affaire.id}/formulaires/HYDR")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "10" in body  # PS=10.0
        assert "14.3" in body  # PT pré-calculé


# ── Sauvegarde brouillon ──────────────────────────────────────────────────


class TestHydrSaveBrouillon:
    def test_creates_formulaire_returns_ok(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR",
            data=json.dumps({"ps": 10.0, "fluide": "eau", "date_epreuve": "2026-05-13"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["ok"] is True
        assert payload["statut"] == "brouillon"

    def test_pt_recomputed_server_side(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        # Le client envoie une valeur PT arbitraire — le serveur doit l'ignorer
        # et recalculer PT = round(10 × 1.43, 1) = 14.3.
        client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR",
            data=json.dumps({"ps": 10.0, "pt": 999.0}),
            content_type="application/json",
        )
        f = _get_formulaire(affaire.id)
        assert f is not None
        assert f.data.get("pt") == pytest.approx(14.3)

    def test_unknown_keys_stripped(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR",
            data=json.dumps({"ps": 10.0, "injection": "evil_payload"}),
            content_type="application/json",
        )
        f = _get_formulaire(affaire.id)
        assert "injection" not in (f.data if f else {})

    def test_missing_json_body_returns_400(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR",
            data="plain text",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_lecteur_cannot_save(
        self, client: FlaskClient, affaire: Affaire
    ) -> None:
        lecteur = User(
            email="lecteur@bff.fr",
            prenom="L",
            nom="Lecteur",
            role=Role.LECTEUR,
            actif=True,
        )
        lecteur.set_password("Test1234!")
        db.session.add(lecteur)
        db.session.commit()

        client.post(
            "/auth/login",
            data={"email": lecteur.email, "password": "Test1234!"},
        )
        resp = client.post(
            f"/affaires/{affaire.id}/formulaires/HYDR",
            data=json.dumps({"ps": 10.0}),
            content_type="application/json",
        )
        assert resp.status_code == 403


# ── Validation ────────────────────────────────────────────────────────────


class TestHydrValider:
    def test_redacteur_cannot_validate(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_redacteur, affaire.id)
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/valider",
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_verificateur_validates_ok(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_verificateur, affaire.id)
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_formulaire(affaire.id)
        assert f is not None
        assert f.statut is Statut.VALIDE

    def test_missing_required_fields_flash_danger(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        # Sauvegarde sans champs obligatoires (ps, pt, fluide, date_epreuve manquants).
        _save(client_verificateur, affaire.id, {"observations": "test sans champs clés"})
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/valider",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "danger" in resp.data.decode("utf-8")

    def test_cannot_validate_nonexistent_formulaire(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        # Aucun formulaire sauvegardé — abort 404 attendu.
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/valider",
            follow_redirects=False,
        )
        assert resp.status_code == 404


# ── Signature ─────────────────────────────────────────────────────────────


class TestHydrSigner:
    def _prepare_valide(self, client: FlaskClient, affaire_id: int) -> None:
        """Amène le formulaire HYDR au statut VALIDE."""
        _save(client, affaire_id)
        _valider(client, affaire_id)

    def test_verificateur_cannot_sign(
        self, client_verificateur: FlaskClient, affaire: Affaire
    ) -> None:
        self._prepare_valide(client_verificateur, affaire.id)
        resp = client_verificateur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/signer",
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_approbateur_signs_ok(
        self, client_approbateur: FlaskClient, affaire: Affaire
    ) -> None:
        self._prepare_valide(client_approbateur, affaire.id)
        resp = client_approbateur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/signer",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        f = _get_formulaire(affaire.id)
        assert f is not None
        assert f.statut is Statut.SIGNE
        assert len(f.signatures) == 1

    def test_hash_verifies_after_signing(
        self, client_approbateur: FlaskClient, affaire: Affaire
    ) -> None:
        self._prepare_valide(client_approbateur, affaire.id)
        client_approbateur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/signer",
            follow_redirects=True,
        )
        f = _get_formulaire(affaire.id)
        assert f is not None
        assert f.signatures[-1].verify(f) is True

    def test_hash_64_chars(
        self, client_approbateur: FlaskClient, affaire: Affaire
    ) -> None:
        self._prepare_valide(client_approbateur, affaire.id)
        client_approbateur.post(
            f"/affaires/{affaire.id}/formulaires/HYDR/signer",
            follow_redirects=True,
        )
        f = _get_formulaire(affaire.id)
        assert f is not None
        assert len(f.signatures[-1].hash_sha256) == 64


# ── PDF ───────────────────────────────────────────────────────────────────


class TestHydrPdf:
    def test_pdf_redirects_when_no_formulaire(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(
            f"/affaires/{affaire.id}/formulaires/HYDR/pdf",
            follow_redirects=False,
        )
        # Formulaire inexistant → 404
        assert resp.status_code == 404

    def test_pdf_redirects_with_warning_when_brouillon(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        # Save sans valider → brouillon
        _save(client_redacteur, affaire.id)
        resp = client_redacteur.get(
            f"/affaires/{affaire.id}/formulaires/HYDR/pdf",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "warning" in resp.data.decode("utf-8")

    def test_pdf_accessible_from_valide(
        self, client_approbateur: FlaskClient, affaire: Affaire
    ) -> None:
        _save(client_approbateur, affaire.id)
        _valider(client_approbateur, affaire.id)

        resp = client_approbateur.get(
            f"/affaires/{affaire.id}/formulaires/HYDR/pdf"
        )
        # WeasyPrint peut ne pas être disponible en CI → redirect avec flash danger
        # Si WeasyPrint est disponible → 200 application/pdf
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            assert resp.content_type == "application/pdf"
