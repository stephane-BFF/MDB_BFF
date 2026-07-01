"""Service d'authentification LDAP / Active Directory BFF.

Authentification cible retenue pour la V1 : les comptes utilisateurs sont
vérifiés contre l'annuaire Active Directory BFF (``ldap3``). L'authentification
locale (Werkzeug) reste un **repli** quand ``WINDOWS_AUTH_ENABLED`` est faux
(développement, tests) ou pour les comptes de service sans entrée AD.

Architecture (défensive) :
    ``authenticate(email, password)`` est le point d'entrée unique appelé par
    la route de login. Il choisit la stratégie selon la configuration :

        WINDOWS_AUTH_ENABLED = true   → bind LDAP, puis résolution locale du
                                        compte applicatif (rôle, activation).
        WINDOWS_AUTH_ENABLED = false  → vérification du hash Werkzeug local.

    Le bind LDAP réel est isolé dans ``_ldap_bind`` pour être **mocké** en test
    (aucun serveur AD n'est requis pour la couverture). ``ldap3`` est importé de
    façon différée afin que l'application démarre même si le paquet est absent.

Sécurité :
    - Un compte doit **exister en base** (table ``users``) même en mode LDAP :
      l'AD prouve l'identité, la base porte le rôle et l'état d'activation. On
      ne crée jamais d'utilisateur applicatif à la volée depuis l'AD (le rôle
      métier est une décision humaine, pas un attribut d'annuaire).
    - Un mot de passe vide est rejeté avant tout bind (les serveurs AD
      acceptent parfois un bind anonyme sur mot de passe vide → faux positif).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import structlog
from flask import current_app

from app.models.user import User

log = structlog.get_logger(__name__)


class AuthMethod(Enum):
    """Méthode ayant validé (ou tenté de valider) l'authentification."""

    LOCAL = auto()
    LDAP = auto()


@dataclass(frozen=True)
class AuthResult:
    """Résultat d'une tentative d'authentification.

    Attributes:
        success: True si l'identité et le mot de passe sont valides.
        user: Le compte applicatif résolu (``None`` si introuvable/échec).
        method: Méthode employée (LOCAL ou LDAP).
        reason: Code court d'échec pour l'audit (``bad_password``,
            ``user_not_found``, ``ldap_unreachable``…). Vide si succès.
    """

    success: bool
    user: User | None
    method: AuthMethod
    reason: str = ""


def authenticate(email: str, password: str) -> AuthResult:
    """Authentifie un utilisateur (LDAP si activé, sinon local).

    Args:
        email: Adresse e-mail saisie (identifiant de connexion).
        password: Mot de passe en clair.

    Returns:
        Un ``AuthResult`` décrivant le succès/échec et la méthode utilisée.
    """
    email = (email or "").strip().lower()
    if not password:
        return AuthResult(False, None, AuthMethod.LOCAL, reason="empty_password")

    user = _find_user(email)

    if current_app.config.get("WINDOWS_AUTH_ENABLED"):
        return _authenticate_ldap(user, email, password)
    return _authenticate_local(user, password)


# ── Stratégie locale (Werkzeug) ───────────────────────────────────────────


def _authenticate_local(user: User | None, password: str) -> AuthResult:
    """Vérifie le mot de passe contre le hash Werkzeug stocké en base."""
    if user is None:
        return AuthResult(False, None, AuthMethod.LOCAL, reason="user_not_found")
    if not user.check_password(password):
        return AuthResult(False, user, AuthMethod.LOCAL, reason="bad_password")
    return AuthResult(True, user, AuthMethod.LOCAL)


# ── Stratégie LDAP / Active Directory ─────────────────────────────────────


def _authenticate_ldap(user: User | None, email: str, password: str) -> AuthResult:
    """Vérifie l'identité par bind AD, puis résout le compte applicatif.

    Le compte doit exister en base pour porter le rôle métier ; un bind réussi
    sur un e-mail inconnu de l'application est un échec (``user_not_found``).
    """
    if user is None:
        # On tente quand même le bind pour ne pas divulguer l'existence du compte,
        # mais un bind réussi sans compte applicatif reste un échec.
        _ldap_bind(email, password)
        return AuthResult(False, None, AuthMethod.LDAP, reason="user_not_found")

    try:
        bound = _ldap_bind(email, password)
    except LdapUnreachableError:
        log.warning("ldap.unreachable", email=email)
        return AuthResult(False, user, AuthMethod.LDAP, reason="ldap_unreachable")

    if not bound:
        return AuthResult(False, user, AuthMethod.LDAP, reason="bad_password")
    return AuthResult(True, user, AuthMethod.LDAP)


class LdapUnreachableError(RuntimeError):
    """Le serveur LDAP est injoignable (réseau, DNS, timeout)."""


def _ldap_bind(email: str, password: str) -> bool:
    """Effectue le bind LDAP réel contre l'AD BFF.

    Isolé pour être **mocké** en test. Construit le ``user_dn`` à partir de
    ``LDAP_USER_DN_TEMPLATE`` (ex: ``"{username}@bff.local"`` en UPN, ou
    ``"CN={username},OU=Users,DC=bff,DC=local"``) puis tente le bind.

    Args:
        email: E-mail / identifiant de connexion.
        password: Mot de passe en clair.

    Returns:
        True si le bind réussit (identité prouvée), False sinon.

    Raises:
        LdapUnreachableError: Si le serveur est injoignable.
    """
    try:
        import ldap3  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover — ldap3 est une dépendance déclarée
        raise LdapUnreachableError("ldap3 non installé") from exc

    server_uri = current_app.config.get("LDAP_SERVER", "")
    if not server_uri:
        raise LdapUnreachableError("LDAP_SERVER non configuré")

    template = current_app.config.get("LDAP_USER_DN_TEMPLATE", "{username}")
    username = email.split("@", 1)[0]
    user_dn = template.format(username=username, email=email)

    try:
        server = ldap3.Server(server_uri, get_info=ldap3.NONE, connect_timeout=5)
        conn = ldap3.Connection(server, user=user_dn, password=password)
        bound = bool(conn.bind())
        conn.unbind()
        return bound
    except Exception as exc:  # noqa: BLE001 — ldap3 lève des types variés
        raise LdapUnreachableError(str(exc)) from exc


# ── Helpers ────────────────────────────────────────────────────────────────


def _find_user(email: str) -> User | None:
    """Résout le compte applicatif par e-mail (insensible à la casse)."""
    from sqlalchemy import func  # noqa: PLC0415

    from app.extensions import db  # noqa: PLC0415

    return (
        db.session.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )
