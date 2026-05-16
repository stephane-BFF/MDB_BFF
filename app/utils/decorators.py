"""Décorateurs de sécurité — utilisés sur toutes les routes d'écriture.

Le décorateur ``@role_required`` accepte des membres de l'enum
``app.enums.Role`` (pas de strings). Doit toujours être combiné avec
``@login_required`` :

    @bp.route("/affaires", methods=["POST"])
    @login_required
    @role_required(Role.REDACTEUR, Role.APPROBATEUR, Role.ADMIN)
    def creer_affaire():
        ...
"""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from flask import abort
from flask_login import current_user

from app.enums import Role

if TYPE_CHECKING:
    from app.models.user import User

_P = ParamSpec("_P")
_R = TypeVar("_R")


def role_required(*roles: Role) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Protège une route : l'utilisateur doit être authentifié et avoir l'un des rôles.

    Args:
        *roles: Membres de ``Role`` autorisés. Au moins un doit être fourni.

    Returns:
        Le décorateur de route. Lève ``HTTPException(401)`` si non authentifié,
        ``HTTPException(403)`` si rôle insuffisant.

    Usage:
        @bp.route("/affaires", methods=["POST"])
        @login_required
        @role_required(Role.REDACTEUR, Role.APPROBATEUR, Role.ADMIN)
        def creer_affaire():
            ...
    """
    if not roles:
        raise ValueError("role_required requiert au moins un rôle")

    allowed: frozenset[Role] = frozenset(roles)

    def decorator(view: Callable[_P, _R]) -> Callable[_P, _R]:
        @wraps(view)
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            user: User = current_user
            if not user.is_authenticated:
                abort(401)
            if user.role not in allowed:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
