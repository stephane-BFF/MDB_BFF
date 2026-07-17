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

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Horodatage UTC courant, calculé côté Python.

    Utilisé comme ``default``/``onupdate`` des colonnes d'horodatage afin que
    la valeur soit **toujours fournie par SQLAlchemy dans l'INSERT/UPDATE**,
    indépendamment du dialecte. Point critique : le schéma SQLite de dev a été
    matérialisé par une migration avec ``DEFAULT (now())`` (fonction PostgreSQL
    inconnue de SQLite) ; sans ce défaut Python, toute insertion de jalon,
    hold point ou référentiel échouerait avec ``unknown function: now()``.
    """
    return datetime.now(UTC)


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
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
        doc="Date/heure de création (UTC). Défaut Python + repli SQL portable.",
    )


class TimestampMixin(CreatedAtMixin):
    """Horodatage complet : ``created_at`` + ``updated_at``.

    Hérite de ``CreatedAtMixin`` et ajoute ``updated_at`` rafraîchi
    automatiquement à chaque UPDATE. Le défaut et le ``onupdate`` sont
    calculés côté Python (``_utcnow``) pour rester portables SQLite/PostgreSQL.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
        doc="Date/heure de dernière modification (UTC). Défaut/onupdate Python.",
    )
