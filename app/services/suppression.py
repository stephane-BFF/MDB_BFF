"""Suppression admin d'un dossier ou d'une affaire complète (V1.2 Lot 5).

Décision D6 (arbitrage S. Paumelle, 2026-07-17) : la suppression est
possible **quel que soit le statut**, mais un **export PDF complet du
dossier est obligatoire au préalable** — si l'assemblage échoue
(WeasyPrint/GTK indisponible), la suppression est refusée. Exception : les
dossiers encore en ``WIZARD_BROUILLON`` (aucun contenu) sont supprimés sans
export.

L'assemblage est appelé en **synchrone** (pas de Celery/Redis — compatible
PC pilote). L'audit trail étant insert-only, la trace détaillée de chaque
suppression survit au dossier supprimé. Les fichiers importés sur disque
(``UPLOAD_FOLDER/<affaire_id>/``) sont également effacés.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from flask import current_app

from app.enums import Statut
from app.extensions import db
from app.models.affaire import Affaire
from app.models.audit import AuditTrail
from app.services.pdf import assemblage

if TYPE_CHECKING:
    from app.models.user import User

#: Clé de config du répertoire d'archivage des exports pré-suppression.
#: Défaut : ``<instance>/exports_suppression``.
CONFIG_EXPORT_DIR = "EXPORT_SUPPRESSION_FOLDER"


class ExportPrealableError(RuntimeError):
    """L'export PDF pré-suppression a échoué — la suppression est refusée."""


def supprimer_dossier(affaire: Affaire, user: User) -> Path | None:
    """Supprime un dossier après export PDF obligatoire (décision D6).

    Args:
        affaire: Le dossier à supprimer.
        user: L'Admin effectuant la suppression (déjà contrôlé côté route).

    Returns:
        Le chemin du PDF d'export archivé, ou ``None`` pour un dossier
        encore en wizard (rien à exporter).

    Raises:
        ExportPrealableError: Si l'assemblage PDF échoue — rien n'est
            supprimé dans ce cas.
    """
    export_path = _exporter(affaire)
    _supprimer(affaire, user, export_path)
    db.session.commit()
    return export_path


def supprimer_affaire_complete(
    numero_affaire: str, user: User
) -> tuple[int, list[Path]]:
    """Supprime tous les dossiers d'une affaire, exports préalables compris.

    Sécurité « tout ou rien » : **tous** les exports PDF sont réalisés avant
    la moindre suppression — un échec d'export laisse l'affaire intacte.

    Args:
        numero_affaire: N° d'affaire BE dont tous les items sont supprimés.
        user: L'Admin effectuant la suppression.

    Returns:
        ``(nb_dossiers_supprimés, chemins_des_exports)``.

    Raises:
        ExportPrealableError: Si un export échoue (aucune suppression faite).
    """
    dossiers = (
        db.session.query(Affaire)
        .filter(Affaire.numero_affaire == numero_affaire)
        .all()
    )
    exports: list[tuple[Affaire, Path | None]] = [
        (dossier, _exporter(dossier)) for dossier in dossiers
    ]
    for dossier, export_path in exports:
        _supprimer(dossier, user, export_path)
    db.session.commit()
    return len(exports), [p for _, p in exports if p is not None]


# ── Internes ─────────────────────────────────────────────────────────────


def _exporter(affaire: Affaire) -> Path | None:
    """Assemble et archive le PDF complet du dossier avant suppression.

    Les dossiers en ``WIZARD_BROUILLON`` (aucun formulaire, aucun contenu)
    sont exemptés d'export.
    """
    if affaire.statut is Statut.WIZARD_BROUILLON:
        return None

    try:
        pdf_bytes = assemblage.assemble_dossier(affaire)
    except Exception as exc:
        raise ExportPrealableError(
            f"Export PDF pré-suppression impossible ({exc}) — "
            "suppression refusée (décision D6). Vérifiez WeasyPrint/GTK."
        ) from exc

    export_dir = Path(
        current_app.config.get(CONFIG_EXPORT_DIR)
        or Path(current_app.instance_path) / "exports_suppression"
    )
    export_dir.mkdir(parents=True, exist_ok=True)
    reference = affaire.references_internes or f"dossier-{affaire.id}"
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    export_path = export_dir / f"{reference}_{horodatage}.pdf"
    export_path.write_bytes(pdf_bytes)
    return export_path


def _supprimer(affaire: Affaire, user: User, export_path: Path | None) -> None:
    """Efface les fichiers disque, trace l'audit et supprime le dossier."""
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / str(affaire.id)
    if upload_dir.is_dir():
        shutil.rmtree(upload_dir, ignore_errors=True)

    AuditTrail.log(
        "affaire.supprimee",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=affaire.statut.value,
        contexte={
            "numero_affaire": affaire.numero_affaire,
            "item": affaire.item,
            "references_internes": affaire.references_internes,
            "client_nom": affaire.client_nom,
            "nb_formulaires": len(affaire.formulaires),
            "nb_fichiers_importes": len(affaire.fichiers_importes),
            "export_pdf": str(export_path) if export_path else None,
        },
    )
    db.session.delete(affaire)
