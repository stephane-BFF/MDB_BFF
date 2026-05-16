"""Service PDF synchrone — rendu d'un formulaire individuel via WeasyPrint.

**Dépendance système** : WeasyPrint nécessite GTK Runtime sur Windows.
    Installateur : https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer

Import de WeasyPrint retardé (lazy) pour que l'application démarre même sans GTK.
Si WeasyPrint est absent, les fonctions de rendu lèvent ``RuntimeError`` avec un
message explicite — la route appelante le transforme en flash "danger" + redirect.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from flask import current_app, render_template

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.formulaire import Formulaire


def render_formulaire_pdf(formulaire: Formulaire, affaire: Affaire, svc: Any) -> bytes:
    """Génère le PDF d'un formulaire via WeasyPrint.

    Sélectionne le template WeasyPrint selon ``svc.CUSTOM_TEMPLATE`` :
    - True  → ``pdf/<code_lower>.html`` (template dédié)
    - False → ``pdf/_simple.html`` (gabarit générique piloté par svc.SECTIONS)

    Args:
        formulaire: Instance ``Formulaire`` (data JSONB pré-chargé).
        affaire: Affaire propriétaire (pour l'en-tête BFF).
        svc: Classe service du formulaire (attributs CODE, TITLE, SECTIONS…).

    Returns:
        Contenu PDF encodé en bytes.

    Raises:
        RuntimeError: Si WeasyPrint ou GTK ne sont pas disponibles.
    """
    try:
        import weasyprint  # noqa: PLC0415 — import intentionnellement lazy
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "WeasyPrint non disponible — GTK Runtime requis sur Windows. "
            "Installez-le depuis : "
            "https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer"
        ) from exc

    logo_uri = _resolve_logo_uri()

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

    doc = weasyprint.HTML(
        string=html_content,
        base_url=current_app.root_path,
    )
    return doc.write_pdf()  # type: ignore[return-value]


def render_hydr_pdf(formulaire: Formulaire, affaire: Affaire) -> bytes:
    """Rétrocompat Phase 1 — délègue à ``render_formulaire_pdf``.

    Args:
        formulaire: Instance ``Formulaire`` HYDR.
        affaire: Affaire propriétaire.

    Returns:
        Contenu PDF encodé en bytes.

    Raises:
        RuntimeError: Si WeasyPrint ou GTK ne sont pas disponibles.
    """
    from app.services.formulaires.hydr import HydrService  # noqa: PLC0415

    return render_formulaire_pdf(formulaire, affaire, HydrService)


# ── Helpers internes ─────────────────────────────────────────────────────


def _resolve_logo_uri() -> str | None:
    """Retourne l'URI ``file:///…`` absolue vers le logo BFF, ou None si absent.

    WeasyPrint exige une URI absolue (pas un chemin relatif) pour charger
    les images locales sous Windows.
    """
    logo_rel = current_app.config.get("LOGO_PATH", "static/img/logo_bff.svg")
    logo_abs = os.path.join(current_app.root_path, logo_rel)
    if not os.path.exists(logo_abs):
        return None
    return "file:///" + logo_abs.replace("\\", "/")
