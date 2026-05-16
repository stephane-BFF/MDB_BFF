"""Modèle Signature — empreinte cryptographique d'un formulaire signé.

Une **signature** matérialise l'engagement d'un utilisateur (Vérificateur,
Approbateur ou Admin) sur le contenu d'un formulaire à un instant précis.
Elle stocke le hash SHA-256 canonique du couple ``(code, template_version,
data)`` au moment de la signature, ce qui permet à chaque affichage
ultérieur de **détecter toute altération** du formulaire post-signature.

**Insert only** : aucune signature ne peut être modifiée a posteriori
(héritage de ``CreatedAtMixin`` plutôt que ``TimestampMixin``). Pour
révoquer une signature, on crée une nouvelle ligne d'audit + on change
le statut du formulaire — la trace originale reste.
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.formulaire import Formulaire
    from app.models.user import User


class Signature(db.Model, CreatedAtMixin):  # type: ignore[name-defined,misc]
    """Signature électronique d'un formulaire — immuable.

    Attributes:
        formulaire_id: FK vers le formulaire signé.
        user_id: FK vers le signataire.
        hash_sha256: Empreinte hexadécimale (64 chars) du contenu canonique
            du formulaire au moment de la signature.
        created_at: Horodatage de la signature (UTC, défini par PostgreSQL).
    """

    __tablename__ = "signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    formulaire_id: Mapped[int] = mapped_column(
        ForeignKey("formulaires.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    hash_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Hash SHA-256 hexa (64 chars) du formulaire au moment de la signature.",
    )

    # ── Relations ────────────────────────────────────────────────────────
    formulaire: Mapped[Formulaire] = relationship(back_populates="signatures")
    user: Mapped[User] = relationship()

    # ── Calcul du hash canonique ─────────────────────────────────────────
    @staticmethod
    def compute_hash(code: str, template_version: int, data: dict[str, Any]) -> str:
        """Calcule le hash SHA-256 canonique d'un formulaire.

        Le payload est sérialisé en JSON trié (``sort_keys=True``) pour garantir
        un hash reproductible quel que soit l'ordre d'insertion des champs dans
        ``data``. ``ensure_ascii=False`` préserve les caractères accentués
        utilisés dans les valeurs métier (libellés FR).

        Args:
            code: Code du formulaire (ex: ``"HYDR"``).
            template_version: Version du template utilisée.
            data: Dictionnaire des champs spécifiques (``Formulaire.data``).

        Returns:
            Chaîne hexadécimale de 64 caractères représentant le hash SHA-256.
        """
        payload = {
            "code": code,
            "template_version": template_version,
            "data": data,
        }
        serialized = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify(self, formulaire: Formulaire) -> bool:
        """Vérifie que le hash stocké correspond au contenu actuel du formulaire.

        Retourne ``False`` si le contenu a été altéré depuis la signature
        (le statut SIGNE est censé être verrouillé, mais on vérifie quand même).
        """
        expected = self.compute_hash(
            formulaire.code,
            formulaire.template_version,
            formulaire.data,
        )
        return self.hash_sha256 == expected

    def __repr__(self) -> str:
        return (
            f"<Signature formulaire_id={self.formulaire_id} "
            f"user_id={self.user_id} hash={self.hash_sha256[:8]}…>"
        )
