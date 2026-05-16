"""Modèle FichierImporte — fichiers extérieurs attachés à une affaire.

Les fichiers importés (certificats matière, PV labo, plans, photos) sont
stockés sur disque dans ``UPLOAD_FOLDER/<affaire_id>/`` et référencés ici
avec leurs métadonnées. Ils sont inclus dans le dossier PDF assemblé selon
l'ordre défini par ``chapitre`` + ``ordre``.

Les images (JPEG, PNG, TIFF) sont converties en PDF au moment de l'assemblage.
Les PDFs sont inclus directement.

Note : nécessite une migration Alembic : ``flask db migrate -m "add fichiers_importes"``
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import Chapitre
from app.extensions import db
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.user import User


class FichierImporte(db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Fichier extérieur importé dans le dossier constructeur d'une affaire.

    Stockage physique : ``UPLOAD_FOLDER/<affaire_id>/<filename>``
    (``filename`` est un UUID + extension pour éviter les conflits de noms).
    """

    __tablename__ = "fichiers_importes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    affaire_id: Mapped[int] = mapped_column(
        ForeignKey("affaires.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cree_par_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Classement dans le dossier ──────────────────────────────────────────
    chapitre: Mapped[Chapitre] = mapped_column(
        SQLEnum(Chapitre, name="chapitre_fichier", native_enum=False, length=2),
        nullable=False,
        index=True,
        doc="Chapitre cible du dossier (A–G).",
    )
    titre: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Titre affiché dans le dossier et le sommaire.",
    )
    ordre: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=99,
        doc="Ordre d'insertion dans le chapitre (croissant).",
    )

    # ── Stockage physique ───────────────────────────────────────────────────
    filename: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Nom de fichier sur disque (UUID + extension).",
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nom original du fichier uploadé (affiché à l'utilisateur).",
    )
    mime_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Type MIME détecté par python-magic au moment de l'upload.",
    )
    taille: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Taille en octets.",
    )

    # ── Relations ───────────────────────────────────────────────────────────
    affaire: Mapped[Affaire] = relationship(back_populates="fichiers_importes")
    cree_par: Mapped[User] = relationship(foreign_keys=[cree_par_id])

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def make_filename(original: str) -> str:
        """Génère un nom de fichier unique (UUID4 + extension originale)."""
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else "bin"
        return f"{uuid.uuid4().hex}.{ext}"

    @property
    def is_image(self) -> bool:
        """True si le fichier est une image (JPEG, PNG, TIFF)."""
        return self.mime_type in ("image/jpeg", "image/png", "image/tiff")

    @property
    def is_pdf(self) -> bool:
        """True si le fichier est un PDF."""
        return self.mime_type == "application/pdf"
