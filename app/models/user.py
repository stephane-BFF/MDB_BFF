"""Modèle utilisateur — authentification locale + autorisation par rôle.

Compatible Flask-Login via héritage de ``UserMixin``. Le hash de mot de passe
est calculé avec Werkzeug (algorithme ``scrypt`` par défaut). L'authentification
LDAP/AD optionnelle (Phase 5) ne stocke pas de mot de passe en base : le hash
reste ``None`` pour ces comptes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import Boolean, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.enums import Role
from app.extensions import db, login_manager
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.affaire import Affaire


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
