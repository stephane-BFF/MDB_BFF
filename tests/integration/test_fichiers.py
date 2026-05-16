"""Tests d'intégration — blueprint Fichiers (import drag & drop).

Vérifie :
    GET    /affaires/<id>/fichiers/manage   — page HTML
    GET    /affaires/<id>/fichiers/         — liste JSON
    POST   /affaires/<id>/fichiers/upload   — import multipart
    GET    /affaires/<id>/fichiers/<fid>    — téléchargement
    PATCH  /affaires/<id>/fichiers/<fid>    — mise à jour métadonnées
    DELETE /affaires/<id>/fichiers/<fid>    — suppression
"""
from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Chapitre, Role, Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.fichier import FichierImporte
from app.models.user import User


# ── Constantes ────────────────────────────────────────────────────────────

# Bytes minimaux reconnus par python-magic comme PDF / PNG
_FAKE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\nstartxref\n9\n%%EOF"
_FAKE_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"  # signature
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ── Helpers / fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def upload_dir(app: Flask) -> str:
    """Crée le dossier d'upload de test et le retourne."""
    folder = app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    return folder


@pytest.fixture()
def user_lecteur(app: Flask) -> User:  # noqa: ARG001
    from tests.conftest import _make_user
    return _make_user("lecteur@bff.fr", "Luc", "Lecteur", Role.LECTEUR)


@pytest.fixture()
def client_lecteur(client: FlaskClient, user_lecteur: User) -> FlaskClient:
    client.post("/auth/login", data={"email": user_lecteur.email, "password": "Test1234!"})
    return client


@pytest.fixture()
def fichier_db(
    app: Flask,  # noqa: ARG001
    affaire: Affaire,
    user_redacteur: User,
    upload_dir: str,
) -> FichierImporte:
    """FichierImporte en base + fichier factice sur disque."""
    dest_dir = os.path.join(upload_dir, str(affaire.id))
    os.makedirs(dest_dir, exist_ok=True)

    f = FichierImporte(
        affaire_id=affaire.id,
        cree_par_id=user_redacteur.id,
        chapitre=Chapitre.F,
        titre="Plan de masse test",
        ordre=10,
        filename="test_fichier.pdf",
        original_filename="plan_masse.pdf",
        mime_type="application/pdf",
        taille=len(_FAKE_PDF_BYTES),
    )
    db.session.add(f)
    db.session.commit()

    filepath = os.path.join(dest_dir, "test_fichier.pdf")
    with open(filepath, "wb") as fp:
        fp.write(_FAKE_PDF_BYTES)

    return f


def _upload(
    client: FlaskClient,
    affaire: Affaire,
    file_bytes: bytes = _FAKE_PDF_BYTES,
    filename: str = "plan.pdf",
    mime_return: str = "application/pdf",
    chapitre: str = "F",
    titre: str = "Mon plan",
    ordre: str = "10",
) -> object:
    """Helper : poste un fichier vers /upload avec les MIME mockés."""
    with patch(
        "app.blueprints.fichiers.routes.validate_mime", return_value=True
    ), patch("magic.from_buffer", return_value=mime_return):
        return client.post(
            f"/affaires/{affaire.id}/fichiers/upload",
            data={
                "file": (io.BytesIO(file_bytes), filename),
                "titre": titre,
                "chapitre": chapitre,
                "ordre": ordre,
            },
            content_type="multipart/form-data",
        )


# ── Manage (page HTML) ────────────────────────────────────────────────────


class TestFichiersManage:
    """GET /affaires/<id>/fichiers/manage."""

    def test_returns_200_html(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/fichiers/manage")
        assert resp.status_code == 200
        assert b"Fichiers import" in resp.data

    def test_unauthenticated_redirected(self, client: FlaskClient, affaire: Affaire) -> None:
        resp = client.get(f"/affaires/{affaire.id}/fichiers/manage", follow_redirects=False)
        assert resp.status_code == 302

    def test_affaire_not_found(self, client_redacteur: FlaskClient) -> None:
        resp = client_redacteur.get("/affaires/99999/fichiers/manage")
        assert resp.status_code == 404

    def test_lecteur_sees_readonly_flag(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        """Le lecteur accède à la page (lecture seule)."""
        resp = client_lecteur.get(f"/affaires/{affaire.id}/fichiers/manage")
        assert resp.status_code == 200
        # JS reçoit can_edit=false
        assert b"false" in resp.data


# ── Index JSON ────────────────────────────────────────────────────────────


class TestFichiersIndex:
    """GET /affaires/<id>/fichiers/."""

    def test_empty_list(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/fichiers/")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_uploaded_fichiers(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        upload_dir: str,
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/fichiers/")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["titre"] == "Plan de masse test"
        assert data[0]["chapitre"] == "F"
        assert data[0]["id"] == fichier_db.id

    def test_unauthenticated_redirected(self, client: FlaskClient, affaire: Affaire) -> None:
        resp = client.get(f"/affaires/{affaire.id}/fichiers/", follow_redirects=False)
        assert resp.status_code == 302

    def test_ordered_by_chapitre_then_ordre(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        user_redacteur: User,
        upload_dir: str,
    ) -> None:
        """Les fichiers sont triés par chapitre puis ordre."""
        for chap, ordre in [("G", 5), ("A", 1), ("F", 2)]:
            f = FichierImporte(
                affaire_id=affaire.id,
                cree_par_id=user_redacteur.id,
                chapitre=Chapitre(chap),
                titre=f"Doc {chap}",
                ordre=ordre,
                filename=f"f_{chap}.pdf",
                original_filename=f"doc_{chap}.pdf",
                mime_type="application/pdf",
                taille=100,
            )
            db.session.add(f)
        db.session.commit()

        resp = client_redacteur.get(f"/affaires/{affaire.id}/fichiers/")
        data = resp.get_json()
        chapitres = [d["chapitre"] for d in data]
        assert chapitres == sorted(chapitres)


# ── Upload ────────────────────────────────────────────────────────────────


class TestFichiersUpload:
    """POST /affaires/<id>/fichiers/upload."""

    def test_upload_pdf_success(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        upload_dir: str,
    ) -> None:
        resp = _upload(client_redacteur, affaire)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["fichier"]["titre"] == "Mon plan"
        assert data["fichier"]["chapitre"] == "F"
        assert data["fichier"]["mime_type"] == "application/pdf"

    def test_upload_creates_db_entry(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        upload_dir: str,
    ) -> None:
        _upload(client_redacteur, affaire)
        count = db.session.query(FichierImporte).filter_by(affaire_id=affaire.id).count()
        assert count == 1

    def test_upload_saves_file_to_disk(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        upload_dir: str,
    ) -> None:
        dest_dir = os.path.join(upload_dir, str(affaire.id))
        os.makedirs(dest_dir, exist_ok=True)
        before = set(os.listdir(dest_dir))
        _upload(client_redacteur, affaire)
        after = set(os.listdir(dest_dir))
        assert len(after - before) == 1

    def test_upload_creates_audit_trail(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        upload_dir: str,
    ) -> None:
        from app.models.audit import AuditTrail
        _upload(client_redacteur, affaire)
        trail = (
            db.session.query(AuditTrail)
            .filter_by(action="fichier.uploaded")
            .first()
        )
        assert trail is not None

    def test_upload_no_file_returns_400(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/fichiers/upload",
            data={"titre": "Test", "chapitre": "F"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_upload_invalid_mime_returns_415(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        with patch("app.blueprints.fichiers.routes.validate_mime", return_value=False):
            resp = client_redacteur.post(
                f"/affaires/{affaire.id}/fichiers/upload",
                data={"file": (io.BytesIO(b"not a real file"), "script.exe"), "titre": "X"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 415

    def test_upload_invalid_chapitre_returns_400(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        upload_dir: str,
    ) -> None:
        resp = _upload(client_redacteur, affaire, chapitre="Z")
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_upload_lecteur_forbidden(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = _upload(client_lecteur, affaire)
        assert resp.status_code == 403

    def test_upload_unauthenticated_redirected(
        self,
        client: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = client.post(
            f"/affaires/{affaire.id}/fichiers/upload",
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_titre_defaults_to_filename(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        upload_dir: str,
    ) -> None:
        """Si titre est absent, utilise le nom du fichier."""
        with patch(
            "app.blueprints.fichiers.routes.validate_mime", return_value=True
        ), patch("magic.from_buffer", return_value="application/pdf"):
            resp = client_redacteur.post(
                f"/affaires/{affaire.id}/fichiers/upload",
                data={
                    "file": (io.BytesIO(_FAKE_PDF_BYTES), "mon_fichier.pdf"),
                    "chapitre": "A",
                },
                content_type="multipart/form-data",
            )
        data = resp.get_json()
        assert data["ok"] is True
        assert "mon_fichier" in data["fichier"]["titre"]


# ── Téléchargement ────────────────────────────────────────────────────────


class TestFichiersDownload:
    """GET /affaires/<id>/fichiers/<fid>."""

    def test_download_returns_file(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/fichiers/{fichier_db.id}")
        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"
        assert resp.data == _FAKE_PDF_BYTES

    def test_download_wrong_affaire_returns_404(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        user_redacteur: User,
    ) -> None:
        """Un fichier d'une autre affaire retourne 404."""
        other_affaire = Affaire(
            numero_affaire="BN2026-999",
            annee=2026,
            client_nom="Autre",
            statut=Statut.BROUILLON,
            cree_par_id=user_redacteur.id,
        )
        db.session.add(other_affaire)
        db.session.commit()

        resp = client_redacteur.get(
            f"/affaires/{other_affaire.id}/fichiers/{fichier_db.id}"
        )
        assert resp.status_code == 404

    def test_download_missing_disk_file_returns_404(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        upload_dir: str,
    ) -> None:
        """Si le fichier disque est absent, 404."""
        filepath = os.path.join(upload_dir, str(affaire.id), fichier_db.filename)
        os.remove(filepath)
        resp = client_redacteur.get(f"/affaires/{affaire.id}/fichiers/{fichier_db.id}")
        assert resp.status_code == 404

    def test_download_nonexistent_id_returns_404(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/fichiers/99999")
        assert resp.status_code == 404

    def test_download_unauthenticated_redirected(
        self,
        client: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
    ) -> None:
        resp = client.get(
            f"/affaires/{affaire.id}/fichiers/{fichier_db.id}",
            follow_redirects=False,
        )
        assert resp.status_code == 302


# ── Mise à jour ───────────────────────────────────────────────────────────


class TestFichiersUpdate:
    """PATCH /affaires/<id>/fichiers/<fid>."""

    def test_update_titre(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
    ) -> None:
        resp = client_redacteur.patch(
            f"/affaires/{affaire.id}/fichiers/{fichier_db.id}",
            json={"titre": "Nouveau titre"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["fichier"]["titre"] == "Nouveau titre"

        db.session.refresh(fichier_db)
        assert fichier_db.titre == "Nouveau titre"

    def test_update_chapitre_and_ordre(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
    ) -> None:
        resp = client_redacteur.patch(
            f"/affaires/{affaire.id}/fichiers/{fichier_db.id}",
            json={"chapitre": "A", "ordre": 3},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["fichier"]["chapitre"] == "A"
        assert data["fichier"]["ordre"] == 3

    def test_update_invalid_chapitre_returns_400(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
    ) -> None:
        resp = client_redacteur.patch(
            f"/affaires/{affaire.id}/fichiers/{fichier_db.id}",
            json={"chapitre": "Z"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_update_lecteur_forbidden(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
    ) -> None:
        resp = client_lecteur.patch(
            f"/affaires/{affaire.id}/fichiers/{fichier_db.id}",
            json={"titre": "Tentative"},
        )
        assert resp.status_code == 403

    def test_update_nonexistent_returns_404(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = client_redacteur.patch(
            f"/affaires/{affaire.id}/fichiers/99999",
            json={"titre": "Test"},
        )
        assert resp.status_code == 404


# ── Suppression ───────────────────────────────────────────────────────────


class TestFichiersDelete:
    """DELETE /affaires/<id>/fichiers/<fid>."""

    def test_delete_removes_db_entry(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        upload_dir: str,
    ) -> None:
        fid = fichier_db.id
        resp = client_redacteur.delete(f"/affaires/{affaire.id}/fichiers/{fid}")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        assert db.session.get(FichierImporte, fid) is None

    def test_delete_removes_disk_file(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        upload_dir: str,
    ) -> None:
        filepath = os.path.join(upload_dir, str(affaire.id), fichier_db.filename)
        assert os.path.exists(filepath)

        client_redacteur.delete(f"/affaires/{affaire.id}/fichiers/{fichier_db.id}")

        assert not os.path.exists(filepath)

    def test_delete_disk_missing_still_succeeds(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        upload_dir: str,
    ) -> None:
        """Si le fichier disque est déjà absent, la suppression DB réussit quand même."""
        filepath = os.path.join(upload_dir, str(affaire.id), fichier_db.filename)
        os.remove(filepath)

        resp = client_redacteur.delete(f"/affaires/{affaire.id}/fichiers/{fichier_db.id}")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_delete_creates_audit_trail(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        upload_dir: str,
    ) -> None:
        from app.models.audit import AuditTrail
        client_redacteur.delete(f"/affaires/{affaire.id}/fichiers/{fichier_db.id}")

        trail = (
            db.session.query(AuditTrail)
            .filter_by(action="fichier.deleted")
            .first()
        )
        assert trail is not None

    def test_delete_lecteur_forbidden(
        self,
        client_lecteur: FlaskClient,
        affaire: Affaire,
        fichier_db: FichierImporte,
        upload_dir: str,
    ) -> None:
        resp = client_lecteur.delete(f"/affaires/{affaire.id}/fichiers/{fichier_db.id}")
        assert resp.status_code == 403

    def test_delete_nonexistent_returns_404(
        self,
        client_redacteur: FlaskClient,
        affaire: Affaire,
    ) -> None:
        resp = client_redacteur.delete(f"/affaires/{affaire.id}/fichiers/99999")
        assert resp.status_code == 404
