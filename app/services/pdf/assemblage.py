"""Service d'assemblage PDF — dossier constructeur complet MDB BFF.

Génère le dossier PDF assemblé (50-100 pages) à partir :
- D'une page de garde WeasyPrint avec QR code ;
- D'un sommaire automatique avec numéros de pages réels ;
- Des formulaires signés ou validés (rendus individuellement via WeasyPrint) ;
- Des fichiers extérieurs importés (PDFs inclus directement, images converties).

Structure du dossier assemblé :
    1. Page de garde (QR code, identification affaire)
    2. Sommaire (numéros de pages réels, généré après assemblage)
    3. Chapitres A → G (formulaires + fichiers importés par chapitre)

Signets pypdf hiérarchiques :
    Niveau 1 — Chapitres  (ex: « A — Certificat de conformité »)
    Niveau 2 — Documents  (ex: « CONFCOM — Conformité commerciale »)

Import de WeasyPrint retardé (lazy) : l'application démarre même sans GTK.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from flask import current_app, render_template

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.fichier import FichierImporte
    from app.models.formulaire import Formulaire


# ── Ordre canonique des chapitres et formulaires dans le dossier ──────────

_CHAPITRE_LABELS: dict[str, str] = {
    "A": "A — Certificat de conformité",
    "B": "B — Notes de calcul",
    "C": "C — Homologation procédés de soudage et qualification",
    "D": "D — Matériaux et certificats",
    "E": "E — Cahier de contrôle",
    "F": "F — Plan de l'appareil",
    "G": "G — Manuel installation, mise en route et maintenance",
}

_FORMULAIRE_ORDER: list[str] = [
    # Chapitre A
    "CONFCOM", "ATTDECR", "ATTREP", "ETATDESC",
    # Chapitre B
    "BIM", "BIMSOUD", "PMI",
    # Chapitre C
    "TTH1", "TTH2", "LISTSOUD", "ROLLING", "DIM",
    # Chapitre D
    "LISTCND", "NDEMAP", "DURETE", "FERRITE",
    "UT0FAIS", "UT0SHELL", "UT0RET", "UT0UBEND",
    # Chapitre E
    "HYDR", "RECORDHYDRO", "AIRSAV", "AZOTE",
    # Chapitre F
    "VISUFINAL", "PROPRETE", "SECHAGE", "PESAGE",
    # Chapitre G
    "PEDMOD",
]


@dataclass
class _EntreeDossier:
    """Entrée dans le plan d'assemblage du dossier."""

    titre: str
    chapitre: str
    pdf_bytes: bytes
    page_debut: int = 0  # rempli après assemblage


@dataclass
class _PlanAssemblage:
    """Plan complet d'assemblage avant fusion pypdf."""

    entrees: list[_EntreeDossier] = field(default_factory=list)

    def add(self, titre: str, chapitre: str, pdf_bytes: bytes) -> None:
        self.entrees.append(_EntreeDossier(titre=titre, chapitre=chapitre, pdf_bytes=pdf_bytes))

    def compute_page_offsets(self, cover_pages: int, toc_pages: int) -> None:
        """Calcule ``page_debut`` en tenant compte de la couverture + sommaire."""
        offset = cover_pages + toc_pages
        for e in self.entrees:
            e.page_debut = offset
            try:
                from pypdf import PdfReader  # noqa: PLC0415
                reader = PdfReader(io.BytesIO(e.pdf_bytes))
                offset += len(reader.pages)
            except Exception:  # noqa: BLE001
                offset += 1


# ── QR code ───────────────────────────────────────────────────────────────


def generate_qr_data_uri(affaire: Affaire) -> str:
    """Génère le QR code de l'affaire et le retourne en data URI PNG base64.

    Contenu encodé : ``BFF-MDB:{references_internes}:{annee}`` — la référence
    interne (``numero_affaire-item``) est utilisée plutôt que le seul n°
    d'affaire, car une même affaire BE peut porter plusieurs items/dossiers.

    Args:
        affaire: Affaire dont on encode l'identifiant.

    Returns:
        Chaîne ``data:image/png;base64,…`` prête pour un attribut ``src``.

    Raises:
        RuntimeError: Si la bibliothèque ``qrcode`` n'est pas installée.
    """
    try:
        import qrcode  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("qrcode non installé — pip install qrcode[pil]") from exc

    content = f"BFF-MDB:{affaire.references_internes}:{affaire.annee}"
    qr = qrcode.QRCode(version=1, box_size=8, border=3)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#003087", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


# ── Conversion image → PDF ────────────────────────────────────────────────


def image_to_pdf(image_bytes: bytes) -> bytes:
    """Convertit une image (JPEG/PNG/TIFF) en PDF A4 via Pillow.

    Args:
        image_bytes: Contenu binaire de l'image source.

    Returns:
        Contenu PDF encodé en bytes.

    Raises:
        RuntimeError: Si Pillow n'est pas installé.
    """
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("Pillow non installé — pip install Pillow") from exc

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


# ── Assemblage principal ──────────────────────────────────────────────────


def assemble_dossier(affaire: Affaire) -> bytes:
    """Assemble le dossier MDB complet en un seul PDF.

    Workflow :
        1. Génère la page de garde (WeasyPrint + QR code).
        2. Pour chaque formulaire signé/validé dans l'ordre canonique, génère
           son PDF individuel.
        3. Pour chaque fichier importé, inclut le PDF ou convertit l'image.
        4. Calcule les numéros de page et génère le sommaire.
        5. Fusionne tous les PDFs avec pypdf.
        6. Ajoute les signets hiérarchiques.

    Args:
        affaire: Affaire dont on génère le dossier.

    Returns:
        Contenu du dossier PDF assemblé en bytes.

    Raises:
        RuntimeError: Si WeasyPrint ou GTK sont absents.
    """
    try:
        import weasyprint  # noqa: PLC0415
        from pypdf import PdfReader, PdfWriter  # noqa: PLC0415
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "WeasyPrint ou pypdf non disponible. "
            "WeasyPrint nécessite GTK Runtime sur Windows."
        ) from exc

    logo_uri = _resolve_logo_uri()

    # ── 1. Page de garde ──────────────────────────────────────────────────
    qr_uri = generate_qr_data_uri(affaire)
    cover_html = render_template(
        "pdf/page_de_garde.html",
        affaire=affaire,
        logo_uri=logo_uri,
        qr_uri=qr_uri,
    )
    cover_bytes = weasyprint.HTML(
        string=cover_html, base_url=current_app.root_path
    ).write_pdf()
    cover_reader = PdfReader(io.BytesIO(cover_bytes))
    cover_pages = len(cover_reader.pages)

    # ── 2. PDFs des formulaires ───────────────────────────────────────────
    plan = _PlanAssemblage()
    _add_formulaires(affaire, plan, logo_uri)

    # ── 3. Fichiers importés ──────────────────────────────────────────────
    _add_fichiers_importes(affaire, plan)

    # ── 4. Sommaire (nécessite de connaître les pages) ────────────────────
    toc_placeholder_pages = 1  # estimation initiale pour calcul offsets
    plan.compute_page_offsets(cover_pages, toc_placeholder_pages)

    toc_entries = _build_toc_entries(plan)
    toc_html = render_template(
        "pdf/sommaire.html",
        affaire=affaire,
        logo_uri=logo_uri,
        toc_entries=toc_entries,
    )
    toc_bytes = weasyprint.HTML(
        string=toc_html, base_url=current_app.root_path
    ).write_pdf()
    toc_reader = PdfReader(io.BytesIO(toc_bytes))
    toc_pages = len(toc_reader.pages)

    # Recalcule les offsets avec le vrai nombre de pages du sommaire
    plan.compute_page_offsets(cover_pages, toc_pages)

    # ── 5. Fusion pypdf ───────────────────────────────────────────────────
    writer = PdfWriter()

    # Couverture
    for page in cover_reader.pages:
        writer.add_page(page)

    # Sommaire (régénéré avec les bons numéros si le TOC a changé)
    if toc_pages != toc_placeholder_pages:
        toc_entries = _build_toc_entries(plan)
        toc_html = render_template(
            "pdf/sommaire.html",
            affaire=affaire,
            logo_uri=logo_uri,
            toc_entries=toc_entries,
        )
        toc_bytes = weasyprint.HTML(
            string=toc_html, base_url=current_app.root_path
        ).write_pdf()
        toc_reader = PdfReader(io.BytesIO(toc_bytes))

    for page in toc_reader.pages:
        writer.add_page(page)

    # Entrées du dossier
    for entree in plan.entrees:
        try:
            reader = PdfReader(io.BytesIO(entree.pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)
        except Exception:  # noqa: BLE001
            current_app.logger.warning(
                "assemblage.skip_entry",
                extra={"titre": entree.titre},
            )

    # ── 6. Signets hiérarchiques ──────────────────────────────────────────
    _add_bookmarks(writer, plan, cover_pages, toc_pages)

    # ── 7. Sérialisation ──────────────────────────────────────────────────
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


# ── Helpers internes ──────────────────────────────────────────────────────


def _add_formulaires(
    affaire: Affaire,
    plan: _PlanAssemblage,
    logo_uri: str | None,
) -> None:
    """Génère et ajoute les PDFs des formulaires validés/signés au plan."""
    from app.enums import Statut  # noqa: PLC0415
    from app.services.formulaires import get_service  # noqa: PLC0415

    try:
        import weasyprint  # noqa: PLC0415
    except (ImportError, OSError):
        return

    # Index des formulaires de l'affaire par code
    formulaires_by_code: dict[str, Any] = {
        f.code: f for f in affaire.formulaires
        if f.statut in (Statut.VALIDE, Statut.SIGNE)
    }

    for code in _FORMULAIRE_ORDER:
        formulaire = formulaires_by_code.get(code)
        if formulaire is None:
            continue

        svc = get_service(code)
        if svc is None:
            continue

        try:
            template_name = svc.get_pdf_template()
            html_content = render_template(
                template_name,
                affaire=affaire,
                formulaire=formulaire,
                svc=svc,
                form_data=formulaire.data,
                logo_uri=logo_uri,
                signatures=formulaire.signatures,
            )
            pdf_bytes = weasyprint.HTML(
                string=html_content, base_url=current_app.root_path
            ).write_pdf()
            plan.add(
                titre=svc.TITLE,
                chapitre=formulaire.chapitre.value,
                pdf_bytes=pdf_bytes,
            )
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning(
                "assemblage.formulaire_failed",
                extra={"code": code, "error": str(exc)},
            )


def _add_fichiers_importes(affaire: Affaire, plan: _PlanAssemblage) -> None:
    """Ajoute les fichiers importés au plan (conversion image→PDF si nécessaire)."""
    import os  # noqa: PLC0415

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")

    for fichier in affaire.fichiers_importes:
        filepath = os.path.join(upload_folder, str(affaire.id), fichier.filename)
        if not os.path.exists(filepath):
            current_app.logger.warning(
                "assemblage.fichier_manquant",
                # NB : ne pas utiliser la clé réservée ``filename`` dans ``extra``
                # (collision avec LogRecord.filename → KeyError).
                extra={"fichier": fichier.filename, "titre": fichier.titre},
            )
            continue
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            if fichier.is_image:
                pdf_bytes = image_to_pdf(raw)
            else:
                pdf_bytes = raw
            plan.add(
                titre=fichier.titre,
                chapitre=fichier.chapitre.value,
                pdf_bytes=pdf_bytes,
            )
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning(
                "assemblage.fichier_failed",
                extra={"titre": fichier.titre, "error": str(exc)},
            )


def _build_toc_entries(plan: _PlanAssemblage) -> list[dict[str, Any]]:
    """Construit la structure du sommaire : chapitres + documents avec pages."""
    chapitres: dict[str, dict[str, Any]] = {}
    for entree in plan.entrees:
        chap = entree.chapitre
        if chap not in chapitres:
            chapitres[chap] = {
                "label": _CHAPITRE_LABELS.get(chap, f"Chapitre {chap}"),
                "documents": [],
            }
        chapitres[chap]["documents"].append({
            "titre": entree.titre,
            "page": entree.page_debut + 1,  # numérotation 1-based
        })
    return [{"chapitre": k, **v} for k, v in chapitres.items()]


def _add_bookmarks(
    writer: Any,
    plan: _PlanAssemblage,
    cover_pages: int,
    toc_pages: int,
) -> None:
    """Ajoute les signets hiérarchiques (niveau 1 chapitres, niveau 2 documents)."""
    current_chap: str | None = None
    chap_outline: Any = None

    for entree in plan.entrees:
        chap = entree.chapitre
        if chap != current_chap:
            current_chap = chap
            label = _CHAPITRE_LABELS.get(chap, f"Chapitre {chap}")
            chap_outline = writer.add_outline_item(label, entree.page_debut)

        writer.add_outline_item(entree.titre, entree.page_debut, parent=chap_outline)


def _resolve_logo_uri() -> str | None:
    """Retourne l'URI absolue du logo BFF ou None si absent."""
    import os  # noqa: PLC0415
    logo_rel = current_app.config.get("LOGO_PATH", "static/img/logo_bff.svg")
    logo_abs = os.path.join(current_app.root_path, logo_rel)
    if not os.path.exists(logo_abs):
        return None
    return "file:///" + logo_abs.replace("\\", "/")
