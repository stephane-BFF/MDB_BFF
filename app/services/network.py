"""Sauvegarde des fichiers PDF sur le NAS BFF.

En production, ``NETWORK_BASE_PATH`` pointe vers le partage UNC Windows :
    ``\\\\BFF-FICHIERS\\Affaires``

Structure cible :
    {NETWORK_BASE_PATH}/{annee}/{numero_affaire}/MDB/{code}.pdf
    ex: \\\\BFF-FICHIERS\\Affaires\\2026\\BN0811-8975\\MDB\\HYDR.pdf

Le paramètre ``numero_affaire`` accepte en pratique la référence interne
complète (``Affaire.references_internes``, ex: ``BN0811-8975``) plutôt que
le seul n° d'affaire BE : une même affaire peut porter plusieurs items, et
seule la référence interne identifie un dossier de façon unique.

En développement, ``NETWORK_BASE_PATH`` vaut ``pdf_output`` (répertoire local).
La fonction ``save_pdf`` crée les dossiers intermédiaires si nécessaire et
lève ``OSError`` si le NAS est inaccessible (catch côté route → flash warning).
"""
from __future__ import annotations

from pathlib import Path

from flask import current_app


def build_nas_path(annee: int, numero_affaire: str, code: str) -> Path:
    """Construit le chemin de destination d'un PDF sur le NAS.

    Args:
        annee: Année de l'affaire (ex: 2026).
        numero_affaire: Numéro formaté (ex: ``"BN2026-042"``).
        code: Code du formulaire (ex: ``"HYDR"``).

    Returns:
        Chemin absolu ``Path`` vers le fichier PDF cible.
    """
    base = Path(current_app.config["NETWORK_BASE_PATH"])
    return base / str(annee) / numero_affaire / "MDB" / f"{code}.pdf"


def save_pdf(content: bytes, annee: int, numero_affaire: str, code: str) -> Path:
    """Sauvegarde un PDF sur le NAS et retourne son chemin absolu.

    Crée les répertoires intermédiaires (``parents=True``) si nécessaire.
    N'écrase pas silencieusement — si le fichier existe déjà il est remplacé
    (comportement de ``Path.write_bytes``).

    Args:
        content: Contenu du PDF en bytes.
        annee: Année de l'affaire.
        numero_affaire: Numéro d'affaire (ex: ``"BN2026-042"``).
        code: Code du formulaire (ex: ``"HYDR"``).

    Returns:
        Chemin ``Path`` où le fichier a été écrit.

    Raises:
        OSError: Si le répertoire NAS est inaccessible (réseau, permissions).
    """
    path = build_nas_path(annee, numero_affaire, code)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    current_app.logger.info(
        "pdf.saved_to_nas",
        extra={"path": str(path), "size_bytes": len(content)},
    )
    return path
