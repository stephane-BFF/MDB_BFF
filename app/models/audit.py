"""Modèle AuditTrail — journal immuable des actions métier.

**Insert only** : aucune ligne ne peut être modifiée ou supprimée a
posteriori (héritage de ``CreatedAtMixin`` + listeners SQLAlchemy qui
lèvent une exception sur UPDATE/DELETE). Pour défense en profondeur,
un trigger PostgreSQL côté migration peut bloquer ces opérations au
niveau base — voir ``migrations/versions/<initial>.py``.

Convention de nommage des actions (chaîne libre, dot-separated) :
    - ``auth.login`` / ``auth.logout`` / ``auth.failed``
    - ``affaire.created`` / ``affaire.wizard_step`` / ``affaire.status_changed``
    - ``formulaire.created`` / ``formulaire.submitted`` / ``formulaire.validated``
      / ``formulaire.rejected`` / ``formulaire.signed``
    - ``user.created`` / ``user.role_changed`` / ``user.deactivated``
    - ``referentiel.<entity>.created`` etc.

Le point d'entrée canonique est la méthode de classe ``AuditTrail.log()``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Mapper

    from app.models.user import User


class AuditTrail(db.Model, CreatedAtMixin):  # type: ignore[name-defined,misc]
    """Journal d'audit immuable.

    Chaque ligne enregistre une action métier avec son auteur (``user_id``),
    l'entité ciblée (``entity_type`` + ``entity_id``), la transition de
    valeur si applicable (``old_value`` → ``new_value``) et un contexte
    libre en JSONB (``contexte``).

    Attributes:
        user_id: Auteur de l'action (``NULL`` pour les événements système).
        action: Code d'action, ex: ``"formulaire.signed"`` (dot-separated).
        entity_type: Nom logique de l'entité affectée, ex: ``"formulaire"``.
        entity_id: Clé primaire de l'entité affectée.
        old_value: Valeur antérieure (statut, rôle, etc.), si applicable.
        new_value: Valeur postérieure.
        contexte: Métadonnées additionnelles (IP, user-agent, diff…) en JSONB.
    """

    __tablename__ = "audit_trail"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
        doc="Code d'action dot-separated, ex: 'formulaire.signed'.",
    )
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contexte: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        doc="Métadonnées libres (IP client, user-agent, diff before/after, …).",
    )

    user: Mapped[User | None] = relationship()

    @classmethod
    def log(
        cls,
        action: str,
        *,
        user: User | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        old_value: object = None,
        new_value: object = None,
        contexte: dict[str, Any] | None = None,
    ) -> AuditTrail:
        """Crée et enregistre une entrée d'audit dans la session courante.

        N'effectue **pas** de commit — laisse l'appelant gérer la transaction
        (atomicité avec l'action métier).

        Args:
            action: Code d'action, ex: ``"formulaire.signed"``.
            user: Utilisateur à l'origine de l'action (``None`` = système).
            entity_type: Type d'entité ciblée, ex: ``"formulaire"``.
            entity_id: ID de l'entité ciblée.
            old_value: Valeur antérieure (sera convertie en str ; accepte
                Enum, int, bool, etc.).
            new_value: Valeur postérieure (sera convertie en str).
            contexte: Métadonnées libres en JSON.

        Returns:
            L'entrée ``AuditTrail`` créée (déjà ajoutée à la session).
        """
        entry = cls(
            user_id=user.id if user is not None else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            contexte=contexte,
        )
        db.session.add(entry)
        return entry

    def __repr__(self) -> str:
        return (
            f"<AuditTrail #{self.id} {self.action} "
            f"user_id={self.user_id} entity={self.entity_type}:{self.entity_id}>"
        )


# ── Garde-fou ORM : aucune modification/suppression possible ─────────────
def _prevent_audit_mutation(
    mapper: Mapper[AuditTrail],
    connection: Connection,
    target: AuditTrail,
) -> None:
    """Bloque tout UPDATE/DELETE sur AuditTrail au niveau ORM.

    Défense en profondeur : un trigger PostgreSQL côté migration assure la
    même garantie au niveau base, même pour les requêtes SQL directes.
    """
    raise RuntimeError(
        "AuditTrail est insert-only — UPDATE/DELETE interdit "
        "(intégrité du journal d'audit MDB BFF)."
    )


event.listen(AuditTrail, "before_update", _prevent_audit_mutation, propagate=True)
event.listen(AuditTrail, "before_delete", _prevent_audit_mutation, propagate=True)
