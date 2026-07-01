"""Modèle utilisateur — authentification locale + autorisation par rôle.

Compatible Flask-Login via héritage de ``UserMixin``. Le hash de mot de passe
est calculé avec Werkzeug (algorithme ``scrypt`` par défaut). L'authentification
LDAP/AD optionnelle (Phase 5) ne stocke pas de mot de passe en base : le hash
reste ``None`` pour ces comptes.

Sécurité Phase 5 :
    - **2FA TOTP** (``totp_secret`` / ``totp_enabled``) : double authentification
      obligatoire pour les rôles Approbateur et Admin (voir ``requires_2fa``).
      Compatible Google Authenticator / FreeOTP (RFC 6238, 6 chiffres, 30 s).
    - **Codes de secours** (``backup_codes``) : hash SHA-256 de codes à usage
      unique, consommés à l'usage (perte du téléphone d'authentification).
    - **Jeton d'API** (``api_token_hash``) : SHA-256 d'un jeton porteur donnant
      l'accès en lecture à l'API REST ``/api/v1/`` sans session navigateur.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.enums import Role
from app.extensions import db, login_manager
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.affaire import Affaire


# Rôles à privilège pour lesquels la 2FA est obligatoire (signature engageante).
_ROLES_2FA_OBLIGATOIRE: frozenset[Role] = frozenset({Role.APPROBATEUR, Role.ADMIN})


class User(UserMixin, db.Model, TimestampMixin):  # type: ignore[name-defined,misc]
    """Utilisateur BFF — authentification locale + autorisation par rôle.

    Attributes:
        id: Identifiant interne auto-incrémenté.
        email: Adresse e-mail unique, utilisée comme identifiant de connexion.
        nom: Nom de famille.
        prenom: Prénom.
        role: Rôle (voir ``app.enums.Role``).
        actif: Compte activé/désactivé (préféré à la suppression pour préserver
            l'historique d'audit). Exposé à Flask-Login via ``is_active``.
        password_hash: Hash Werkzeug. ``None`` autorisé pour les comptes LDAP/AD.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(254),  # longueur max RFC 5321
        unique=True,
        nullable=False,
        index=True,
    )
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    prenom: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[Role] = mapped_column(
        SQLEnum(Role, name="role", native_enum=False, length=20),
        nullable=False,
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── 2FA TOTP (Phase 5) ───────────────────────────────────────────────
    totp_secret: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Secret TOTP base32 ; ``None`` tant que la 2FA n'est pas enrôlée.",
    )
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="True une fois le premier code TOTP validé lors de l'enrôlement.",
    )
    backup_codes: Mapped[list[str] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        doc="Hash SHA-256 des codes de secours à usage unique (jamais en clair).",
    )

    # ── Jeton API REST (Phase 4) ─────────────────────────────────────────
    api_token_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="SHA-256 hexa du jeton d'API porteur ; ``None`` si aucun jeton émis.",
    )

    # ── Relations ────────────────────────────────────────────────────────
    affaires_creees: Mapped[list[Affaire]] = relationship(
        back_populates="cree_par",
        foreign_keys="Affaire.cree_par_id",
    )

    def set_password(self, password: str) -> None:
        """Hache et stocke le mot de passe (Werkzeug ``scrypt``)."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Vérifie un mot de passe en clair contre le hash stocké.

        Retourne ``False`` si aucun hash n'est défini (compte LDAP-only).
        """
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    # ── 2FA TOTP ─────────────────────────────────────────────────────────
    @property
    def requires_2fa(self) -> bool:
        """True si le rôle impose la double authentification (Approbateur/Admin)."""
        return self.role in _ROLES_2FA_OBLIGATOIRE

    def start_totp_enrollment(self) -> str:
        """Génère un nouveau secret TOTP (non encore activé) et le retourne.

        Le secret est stocké mais ``totp_enabled`` reste ``False`` jusqu'à la
        validation du premier code par ``confirm_totp``. Régénérer écrase un
        éventuel secret précédent (ré-enrôlement).

        Returns:
            Le secret base32 (à afficher en QR code / clé manuelle).
        """
        import pyotp  # noqa: PLC0415 — dépendance optionnelle, import différé

        self.totp_secret = pyotp.random_base32()
        self.totp_enabled = False
        return self.totp_secret

    def totp_provisioning_uri(self, issuer: str = "MDB BFF") -> str:
        """Retourne l'URI ``otpauth://`` pour l'app d'authentification.

        Raises:
            ValueError: Si aucun secret n'a été généré (``start_totp_enrollment``).
        """
        if not self.totp_secret:
            raise ValueError("Aucun secret TOTP : appeler start_totp_enrollment d'abord.")
        import pyotp  # noqa: PLC0415

        return pyotp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email, issuer_name=issuer
        )

    def verify_totp(self, code: str) -> bool:
        """Vérifie un code TOTP à 6 chiffres (fenêtre ±30 s pour la dérive d'horloge).

        Retourne ``False`` si aucun secret n'est défini ou si le code est vide.
        """
        if not self.totp_secret or not code:
            return False
        import pyotp  # noqa: PLC0415

        return bool(pyotp.TOTP(self.totp_secret).verify(code.strip(), valid_window=1))

    def confirm_totp(self, code: str) -> bool:
        """Active définitivement la 2FA si le code fourni est valide.

        Returns:
            True si activée, False si le code est invalide (2FA reste inactive).
        """
        if self.verify_totp(code):
            self.totp_enabled = True
            return True
        return False

    def disable_totp(self) -> None:
        """Désactive la 2FA et purge secret + codes de secours (réservé Admin)."""
        self.totp_secret = None
        self.totp_enabled = False
        self.backup_codes = None

    def generate_backup_codes(self, count: int = 8) -> list[str]:
        """Génère ``count`` codes de secours à usage unique et stocke leurs hash.

        Returns:
            Les codes **en clair** (affichés une seule fois à l'utilisateur).
        """
        codes = [f"{secrets.randbelow(10**8):08d}" for _ in range(count)]
        self.backup_codes = [self._hash_token(c) for c in codes]
        return codes

    def consume_backup_code(self, code: str) -> bool:
        """Vérifie et consomme un code de secours (usage unique).

        Returns:
            True si le code était valide (et vient d'être retiré), False sinon.
        """
        if not self.backup_codes or not code:
            return False
        hashed = self._hash_token(code.strip())
        if hashed in self.backup_codes:
            # Réassigner une nouvelle liste pour que SQLAlchemy détecte le changement JSONB.
            self.backup_codes = [c for c in self.backup_codes if c != hashed]
            return True
        return False

    # ── Jeton d'API REST ─────────────────────────────────────────────────
    def issue_api_token(self) -> str:
        """Génère un nouveau jeton d'API porteur, stocke son hash et le retourne.

        Le jeton en clair n'est **jamais** persisté : seul son SHA-256 l'est.
        Émettre un nouveau jeton révoque le précédent.

        Returns:
            Le jeton en clair (à transmettre une seule fois au client).
        """
        token = secrets.token_urlsafe(32)
        self.api_token_hash = self._hash_token(token)
        return token

    def revoke_api_token(self) -> None:
        """Révoque le jeton d'API courant."""
        self.api_token_hash = None

    def check_api_token(self, token: str) -> bool:
        """Compare (temps constant) un jeton présenté au hash stocké."""
        if not self.api_token_hash or not token:
            return False
        return secrets.compare_digest(self.api_token_hash, self._hash_token(token))

    @staticmethod
    def _hash_token(token: str) -> str:
        """SHA-256 hexa d'un jeton/code à forte entropie (non salé, donc requêtable)."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def by_api_token(cls, token: str) -> User | None:
        """Résout un utilisateur actif à partir d'un jeton d'API en clair.

        Le jeton est haché puis comparé à l'index ``api_token_hash``. Retourne
        ``None`` si aucun compte actif ne correspond.

        Args:
            token: Jeton porteur présenté par le client (``Authorization: Bearer``).

        Returns:
            L'utilisateur propriétaire du jeton, ou ``None``.
        """
        if not token:
            return None
        user = (
            db.session.query(cls)
            .filter_by(api_token_hash=cls._hash_token(token))
            .first()
        )
        if user is None or not user.actif:
            return None
        return user

    @property
    def full_name(self) -> str:
        """Nom complet pour l'UI (« Prénom Nom »)."""
        return f"{self.prenom} {self.nom}"

    @property
    def is_active(self) -> bool:
        """Override Flask-Login : reflète la colonne ``actif``."""
        return self.actif

    def has_role(self, *roles: Role) -> bool:
        """Retourne True si l'utilisateur a l'un des rôles passés en argument."""
        return self.role in roles

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role.value}>"


@login_manager.user_loader  # type: ignore[untyped-decorator]
def _load_user(user_id: str) -> User | None:
    """Callback Flask-Login : charge un utilisateur depuis sa clé primaire."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, uid)
