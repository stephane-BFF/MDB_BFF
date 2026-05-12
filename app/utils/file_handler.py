"""Gestion des fichiers : sauvegarde sur chemin réseau BFF et validation MIME."""
import os
import magic
from flask import current_app
from werkzeug.datastructures import FileStorage


# Types MIME autorisés pour les uploads (validés côté serveur)
ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
})


def validate_mime(file: FileStorage) -> bool:
    """Valide le type MIME réel du fichier (indépendant de l'extension déclarée).

    Args:
        file: Fichier uploadé via Flask/Werkzeug.

    Returns:
        True si le type MIME est dans la liste autorisée.
    """
    header = file.read(2048)
    file.seek(0)
    detected = magic.from_buffer(header, mime=True)
    return detected in ALLOWED_MIME_TYPES


def build_network_path(num_affaire: str, code_formulaire: str, filename: str) -> str:
    """Construit le chemin réseau UNC complet pour un fichier d'affaire.

    Args:
        num_affaire: Numéro d'affaire au format BN{AAAA}-{NNN}.
        code_formulaire: Code du formulaire (ex: 'hydr', 'dim').
        filename: Nom du fichier final.

    Returns:
        Chemin complet vers le fichier sur le NAS BFF.
    """
    base = current_app.config["NETWORK_BASE_PATH"]
    annee = num_affaire[2:6]  # "BN2026-042" → "2026"
    return os.path.join(base, annee, num_affaire, "MDB", code_formulaire, filename)


def save_file(file: FileStorage, dest_path: str) -> str:
    """Sauvegarde un fichier sur le chemin réseau BFF avec création des dossiers.

    Args:
        file: Fichier uploadé à sauvegarder.
        dest_path: Chemin complet de destination (construit via build_network_path).

    Returns:
        Chemin absolu du fichier sauvegardé.

    Raises:
        OSError: Si le chemin réseau est inaccessible.
    """
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    file.save(dest_path)
    return dest_path
