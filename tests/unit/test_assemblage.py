"""Tests unitaires — assemblage du dossier PDF (`app.services.pdf.assemblage`).

WeasyPrint n'étant pas capable de *rendre* sans GTK/pango sur cet environnement,
les fonctions qui appellent ``weasyprint.HTML().write_pdf()`` sont testées en
mockant WeasyPrint (retour d'un PDF réel généré par pypdf) et ``render_template``.
Les helpers purs (QR code, conversion image, plan, sommaire, signets) sont
testés sur des données réelles (qrcode / Pillow / pypdf fonctionnent).
"""
from __future__ import annotations

import io
import os
import sys
import types
from unittest.mock import patch

from flask import Flask

from app.enums import Chapitre, Role, Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.fichier import FichierImporte
from app.models.formulaire import Formulaire
from app.models.user import User
from app.services.pdf import assemblage
from app.services.pdf.assemblage import (
    _PlanAssemblage,
    _add_bookmarks,
    _add_fichiers_importes,
    _add_formulaires,
    _build_toc_entries,
    _resolve_logo_uri,
    assemble_dossier,
    generate_qr_data_uri,
    image_to_pdf,
)


def _blank_pdf(pages: int = 1) -> bytes:
    """Génère un PDF réel (pages vierges) lisible par pypdf."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


def _fake_weasyprint() -> types.ModuleType:
    """Module ``weasyprint`` factice : ``HTML(...).write_pdf()`` → PDF réel 1 page.

    Évite le chargement des libs GTK/pango (absentes sur cet environnement) en
    remplaçant le module dans ``sys.modules`` le temps du test.
    """
    module = types.ModuleType("weasyprint")

    class _FakeHTML:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def write_pdf(self, *args: object, **kwargs: object) -> bytes:
            return _blank_pdf(1)

    module.HTML = _FakeHTML  # type: ignore[attr-defined]
    return module


# ── Helpers purs ────────────────────────────────────────────────────────────


class TestQrCode:
    def test_data_uri_png(self, app: Flask, affaire: Affaire) -> None:
        with app.app_context():
            uri = generate_qr_data_uri(affaire)
        assert uri.startswith("data:image/png;base64,")
        assert len(uri) > 100


class TestImageToPdf:
    def test_conversion_png_vers_pdf(self) -> None:
        pdf = image_to_pdf(_png_bytes())
        assert pdf.startswith(b"%PDF")


class TestResolveLogo:
    def test_logo_absent_retourne_none(self, app: Flask) -> None:
        app.config["LOGO_PATH"] = "static/img/nexiste_pas_12345.svg"
        with app.app_context():
            assert _resolve_logo_uri() is None

    def test_logo_present_retourne_file_uri(self, app: Flask, tmp_path) -> None:  # noqa: ANN001
        logo = tmp_path / "logo.svg"
        logo.write_text("<svg/>", encoding="utf-8")
        # Chemin relatif à root_path : on force un chemin absolu via un LOGO_PATH
        # relatif inexistant remplacé par un fichier réel sous root_path.
        rel = os.path.relpath(logo, app.root_path)
        app.config["LOGO_PATH"] = rel
        with app.app_context():
            uri = _resolve_logo_uri()
        assert uri is not None and uri.startswith("file:///")


class TestPlanAssemblage:
    def test_compute_offsets(self) -> None:
        plan = _PlanAssemblage()
        plan.add("Doc 1", "A", _blank_pdf(1))
        plan.add("Doc 2", "E", _blank_pdf(2))
        plan.compute_page_offsets(cover_pages=1, toc_pages=1)
        # offset initial = 1 (cover) + 1 (toc) = 2
        assert plan.entrees[0].page_debut == 2
        assert plan.entrees[1].page_debut == 3  # après 1 page du doc 1

    def test_compute_offsets_pdf_invalide(self) -> None:
        plan = _PlanAssemblage()
        plan.add("Corrompu", "A", b"pas un pdf")
        plan.compute_page_offsets(cover_pages=0, toc_pages=0)
        assert plan.entrees[0].page_debut == 0  # fallback : +1 page comptée


class TestToc:
    def test_build_toc_entries_groupe_par_chapitre(self) -> None:
        plan = _PlanAssemblage()
        plan.add("CONFCOM", "A", _blank_pdf(1))
        plan.add("HYDR", "E", _blank_pdf(1))
        plan.compute_page_offsets(1, 1)
        toc = _build_toc_entries(plan)
        chapitres = {e["chapitre"] for e in toc}
        assert chapitres == {"A", "E"}
        docs_a = next(e for e in toc if e["chapitre"] == "A")["documents"]
        assert docs_a[0]["titre"] == "CONFCOM"
        assert docs_a[0]["page"] >= 1


class TestBookmarks:
    def test_add_bookmarks(self) -> None:
        from pypdf import PdfReader, PdfWriter

        plan = _PlanAssemblage()
        plan.add("CONFCOM", "A", _blank_pdf(1))
        plan.add("HYDR", "E", _blank_pdf(1))
        plan.compute_page_offsets(1, 1)

        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=200, height=200)
        _add_bookmarks(writer, plan, cover_pages=1, toc_pages=1)

        buf = io.BytesIO()
        writer.write(buf)
        outline = PdfReader(io.BytesIO(buf.getvalue())).outline
        assert len(outline) >= 2  # 2 chapitres au moins


# ── Fichiers importés ───────────────────────────────────────────────────────


class TestAddFichiersImportes:
    def test_inclut_image_et_pdf_ignore_manquant(
        self, app: Flask, affaire: Affaire, user_redacteur: User
    ) -> None:
        upload = app.config["UPLOAD_FOLDER"]
        dest = os.path.join(upload, str(affaire.id))
        os.makedirs(dest, exist_ok=True)

        # Fichier image réel
        img_name = "img.png"
        with open(os.path.join(dest, img_name), "wb") as fh:
            fh.write(_png_bytes())
        # Fichier PDF réel
        pdf_name = "doc.pdf"
        with open(os.path.join(dest, pdf_name), "wb") as fh:
            fh.write(_blank_pdf(1))

        f_img = FichierImporte(
            affaire_id=affaire.id, cree_par_id=user_redacteur.id, chapitre=Chapitre.D,
            titre="Photo", ordre=1, filename=img_name, original_filename="p.png",
            mime_type="image/png", taille=100,
        )
        f_pdf = FichierImporte(
            affaire_id=affaire.id, cree_par_id=user_redacteur.id, chapitre=Chapitre.D,
            titre="Certificat", ordre=2, filename=pdf_name, original_filename="c.pdf",
            mime_type="application/pdf", taille=200,
        )
        f_manquant = FichierImporte(
            affaire_id=affaire.id, cree_par_id=user_redacteur.id, chapitre=Chapitre.D,
            titre="Absent", ordre=3, filename="absent.pdf", original_filename="a.pdf",
            mime_type="application/pdf", taille=0,
        )
        db.session.add_all([f_img, f_pdf, f_manquant])
        db.session.commit()

        plan = _PlanAssemblage()
        with app.app_context():
            _add_fichiers_importes(affaire, plan)

        titres = {e.titre for e in plan.entrees}
        assert "Photo" in titres and "Certificat" in titres
        assert "Absent" not in titres  # fichier manquant ignoré


# ── Formulaires & assemblage complet (WeasyPrint mocké) ─────────────────────


def _signed_hydr(affaire: Affaire) -> Formulaire:
    f = Formulaire(
        affaire_id=affaire.id, code="HYDR", chapitre=Chapitre.E,
        statut=Statut.SIGNE, data={"ps": 10.0, "pt": 14.3, "fluide": "eau"},
        template_version=1,
    )
    db.session.add(f)
    db.session.commit()
    return f


class TestAddFormulaires:
    def test_ajoute_formulaire_signe(self, app: Flask, affaire: Affaire) -> None:
        _signed_hydr(affaire)
        plan = _PlanAssemblage()
        with app.app_context(), patch.dict(
            sys.modules, {"weasyprint": _fake_weasyprint()}
        ), patch.object(assemblage, "render_template", return_value="<html></html>"):
            _add_formulaires(affaire, plan, logo_uri=None)
        assert any(e.chapitre == "E" for e in plan.entrees)


class TestAssembleDossier:
    def test_assemblage_complet_retourne_pdf(self, app: Flask, affaire: Affaire) -> None:
        _signed_hydr(affaire)
        with app.app_context(), patch.dict(
            sys.modules, {"weasyprint": _fake_weasyprint()}
        ), patch.object(assemblage, "render_template", return_value="<html></html>"):
            pdf = assemble_dossier(affaire)
        assert pdf.startswith(b"%PDF")
        # Cover + sommaire + formulaire ⇒ au moins 3 pages.
        from pypdf import PdfReader

        assert len(PdfReader(io.BytesIO(pdf)).pages) >= 3
