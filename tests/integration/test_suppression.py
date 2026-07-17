"""Tests d'intégration — suppression admin avec export préalable (V1.2 Lot 5)."""
from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Role, Statut, StatutWizard
from app.extensions import db as _db
from app.models.affaire import Affaire
from app.models.audit import AuditTrail
from app.models.user import User
from tests.conftest import _login, _make_user


@pytest.fixture()
def client_admin(client: FlaskClient, app: Flask) -> FlaskClient:  # noqa: ARG001
    """Client HTTP authentifié en tant qu'Admin."""
    _make_user("admin.suppr@bff.fr", "Ad", "Min", Role.ADMIN)
    _login(client, "admin.suppr@bff.fr")
    return client


@pytest.fixture()
def export_mocke(app: Flask, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Simule l'assemblage PDF et route les exports vers un répertoire temporaire."""
    monkeypatch.setattr(
        "app.services.pdf.assemblage.assemble_dossier",
        lambda affaire: b"%PDF-1.4 export factice",
    )
    export_dir = tmp_path / "exports"
    app.config["EXPORT_SUPPRESSION_FOLDER"] = str(export_dir)
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    return export_dir


class TestSuppressionDossier:
    def test_suppression_avec_export_prealable(
        self,
        client_admin: FlaskClient,
        affaire: Affaire,
        export_mocke: Path,
        tmp_path: Path,
    ) -> None:
        # Un fichier importé sur disque doit disparaître avec le dossier.
        upload_dir = tmp_path / "uploads" / str(affaire.id)
        upload_dir.mkdir(parents=True)
        (upload_dir / "certificat.pdf").write_bytes(b"pdf")
        affaire_id = affaire.id

        resp = client_admin.post(
            f"/affaires/{affaire_id}/supprimer",
            data={"confirmation": affaire.references_internes},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        assert _db.session.get(Affaire, affaire_id) is None
        exports = list(export_mocke.glob("*.pdf"))
        assert len(exports) == 1
        assert exports[0].read_bytes().startswith(b"%PDF")
        assert not upload_dir.exists()
        # L'audit (insert-only) garde la trace détaillée.
        trace = (
            _db.session.query(AuditTrail)
            .filter_by(action="affaire.supprimee", entity_id=affaire_id)
            .one()
        )
        assert trace.contexte["references_internes"] == "INT-001"

    def test_echec_export_bloque_la_suppression(
        self,
        client_admin: FlaskClient,
        affaire: Affaire,
        export_mocke: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _boom(affaire: Affaire) -> bytes:
            raise RuntimeError("WeasyPrint indisponible")

        monkeypatch.setattr("app.services.pdf.assemblage.assemble_dossier", _boom)
        resp = client_admin.post(
            f"/affaires/{affaire.id}/supprimer",
            data={"confirmation": affaire.references_internes},
            follow_redirects=True,
        )
        assert "suppression refusée".encode() in resp.data
        assert _db.session.get(Affaire, affaire.id) is not None

    def test_confirmation_incorrecte_refusee(
        self, client_admin: FlaskClient, affaire: Affaire, export_mocke: Path
    ) -> None:
        resp = client_admin.post(
            f"/affaires/{affaire.id}/supprimer",
            data={"confirmation": "MAUVAISE-REF"},
            follow_redirects=True,
        )
        assert b"Confirmation incorrecte" in resp.data
        assert _db.session.get(Affaire, affaire.id) is not None

    def test_non_admin_refuse(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/supprimer",
            data={"confirmation": affaire.references_internes},
        )
        assert resp.status_code == 403

    def test_dossier_wizard_supprime_sans_export(
        self,
        client_admin: FlaskClient,
        user_redacteur: User,
        export_mocke: Path,
    ) -> None:
        brouillon = Affaire(
            statut=Statut.WIZARD_BROUILLON,
            statut_wizard=StatutWizard.Q1,
            annee=2026,
            cree_par_id=user_redacteur.id,
        )
        _db.session.add(brouillon)
        _db.session.commit()

        resp = client_admin.post(
            f"/affaires/{brouillon.id}/supprimer",
            data={"confirmation": "SUPPRIMER"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _db.session.get(Affaire, brouillon.id) is None
        assert not list(export_mocke.glob("*.pdf"))  # aucun export pour un wizard


class TestSuppressionAffaireComplete:
    def test_supprime_tous_les_items(
        self,
        client_admin: FlaskClient,
        user_redacteur: User,
        export_mocke: Path,
    ) -> None:
        for item in ("8975", "8976"):
            _db.session.add(
                Affaire(
                    numero_affaire="BN0811",
                    item=item,
                    references_internes=f"BN0811-{item}",
                    annee=2026,
                    statut=Statut.BROUILLON,
                    cree_par_id=user_redacteur.id,
                )
            )
        _db.session.commit()

        resp = client_admin.post(
            "/affaires/par-affaire/BN0811/supprimer",
            data={"confirmation": "BN0811"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"2 dossier(s)" in resp.data
        restants = (
            _db.session.query(Affaire)
            .filter(Affaire.numero_affaire == "BN0811")
            .count()
        )
        assert restants == 0
        assert len(list(export_mocke.glob("*.pdf"))) == 2

    def test_echec_export_ne_supprime_rien(
        self,
        client_admin: FlaskClient,
        user_redacteur: User,
        export_mocke: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for item in ("8975", "8976"):
            _db.session.add(
                Affaire(
                    numero_affaire="BN0812",
                    item=item,
                    references_internes=f"BN0812-{item}",
                    annee=2026,
                    statut=Statut.BROUILLON,
                    cree_par_id=user_redacteur.id,
                )
            )
        _db.session.commit()

        appels = {"n": 0}

        def _second_echoue(affaire: Affaire) -> bytes:
            appels["n"] += 1
            if appels["n"] >= 2:
                raise RuntimeError("plus de place disque")
            return b"%PDF-1.4 ok"

        monkeypatch.setattr(
            "app.services.pdf.assemblage.assemble_dossier", _second_echoue
        )
        client_admin.post(
            "/affaires/par-affaire/BN0812/supprimer",
            data={"confirmation": "BN0812"},
        )
        # Tout ou rien : les 2 dossiers sont intacts malgré le 1er export OK.
        restants = (
            _db.session.query(Affaire)
            .filter(Affaire.numero_affaire == "BN0812")
            .count()
        )
        assert restants == 2
