"""Décorateurs de sécurité — utilisés sur toutes les routes d'écriture."""
from functools import wraps
from typing import Callable
from flask import abort
from flask_login import current_user


def role_required(*roles: str) -> Callable:
    """Protège une route : l'utilisateur doit être authentifié et avoir l'un des rôles.

    Args:
        *roles: Noms de rôles autorisés (ex: 'admin', 'approbateur').

    Usage:
        @bp.route("/affaires", methods=["POST"])
        @login_required
        @role_required("redacteur", "approbateur", "admin")
        def creer_affaire():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args: object, **kwargs: object) -> object:
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
