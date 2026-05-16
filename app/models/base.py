"""Base déclarative SQLAlchemy 2.0 typée et mixins communs aux modèles MDB BFF.

``Base`` est inscrite auprès de Flask-SQLAlchemy dans ``app/extensions.py``
via ``SQLAlchemy(model_class=Base)``. Tous les modèles concrets héritent
de ``db.Model``, qui n'est autre que cette classe ``Base``.

Deux mixins d'horodatage sont fournis :
    - ``CreatedAtMixin`` : ``created_at`` seul, pour les tables insert-only
      (``AuditTrail``, ``Signature``) où toute mise à jour a posteriori est
      interdite par convention métier.
    - ``TimestampMixin`` : ``created_at`` + ``updated_at`` (rafraîchi à
      chaque UPDATE), pour tous les autres modèles.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base déclarative SQLAlchemy 2.0 pour tous les modèles MDB BFF.

    Note :
        Cette classe est volontairement vide. Les colonnes communes
        (``created_at`` / ``updated_at``) sont apportées par mixin pour
        permettre une exclusion sélective (insert-only tables).
    """


class CreatedAtMixin:
    """Horodatage de création seul — pour les tables insert-only.

    Utilisé par ``AuditTrail`` et ``Signature`` : ces enregistrements ne
    doivent **jamais** être mis à jour après leur insertion (immuabilité
    légale et traçabilité).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Date/heure de création (UTC, défini par PostgreSQL).",
    )


class TimestampMixin(CreatedAtMixin):
    """Horodatage complet : ``created_at`` + ``updated_at``.

    Hérite de ``CreatedAtMixin`` et ajoute ``updated_at`` rafraîchi
    automatiquement à chaque UPDATE par PostgreSQL (``onupdate=func.now()``).
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Date/heure de dernière modification (UTC, défini par PostgreSQL).",
    )
