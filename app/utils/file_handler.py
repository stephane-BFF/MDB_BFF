"""Gestion des fichiers : sauvegarde sur chemin réseau BFF et validation MIME."""
import os

import magic
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


def save_file(file: FileStorage, dest_path: str) -> str:
    """Sauvegarde un fichier sur le chemin réseau BFF avec création des dossiers.

    Args:
        file: Fichier uploadé à sauvegarder.
        dest_path: Chemin complet de destination (voir ``app.services.network``
            pour la construction du chemin NAS).

    Returns:
        Chemin absolu du fichier sauvegardé.

    Raises:
        OSError: Si le chemin réseau est inaccessible.
    """
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    file.save(dest_path)
    return dest_path
