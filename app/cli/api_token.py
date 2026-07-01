"""Commande ``flask api-token`` — gestion des jetons d'API REST.

Émission et révocation des jetons porteurs utilisés par l'API ``/api/v1/``.
Le jeton en clair n'est affiché **qu'une seule fois** à l'émission : seul son
hash SHA-256 est stocké en base.

Exemples :
    flask api-token issue  Brice.Girard@bffrance.com
    flask api-token revoke Brice.Girard@bffrance.com
    flask api-token list
"""
from __future__ import annotations

import click
from flask.cli import with_appcontext
from sqlalchemy import func

from app.extensions import db
from app.models.audit import AuditTrail
from app.models.user import User


@click.group("api-token")
def api_token_group() -> None:
    """Gestion des jetons d'accès à l'API REST."""


@api_token_group.command("issue")
@click.argument("email")
@with_appcontext
def issue(email: str) -> None:
    """Émet (ou renouvelle) le jeton d'API d'un utilisateur."""
    user = _resolve(email)
    if user is None:
        raise click.ClickException(f"Utilisateur introuvable : {email}")

    token = user.issue_api_token()
    AuditTrail.log(
        "api.token_issued",
        user=user,
        entity_type="user",
        entity_id=user.id,
    )
    db.session.commit()
    click.echo(f"[OK] Jeton API emis pour {user.email} ({user.role.value}).")
    click.echo("     Conservez-le : il ne sera plus jamais affiche.")
    click.echo(f"     TOKEN: {token}")


@api_token_group.command("revoke")
@click.argument("email")
@with_appcontext
def revoke(email: str) -> None:
    """Révoque le jeton d'API d'un utilisateur."""
    user = _resolve(email)
    if user is None:
        raise click.ClickException(f"Utilisateur introuvable : {email}")

    user.revoke_api_token()
    AuditTrail.log(
        "api.token_revoked",
        user=user,
        entity_type="user",
        entity_id=user.id,
    )
    db.session.commit()
    click.echo(f"[OK] Jeton API revoque pour {user.email}.")


@api_token_group.command("list")
@with_appcontext
def list_tokens() -> None:
    """Liste les utilisateurs disposant d'un jeton d'API actif."""
    users = db.session.query(User).filter(User.api_token_hash.isnot(None)).all()
    if not users:
        click.echo("Aucun jeton API actif.")
        return
    for u in users:
        click.echo(f"  - {u.email} ({u.role.value})")


def _resolve(email: str) -> User | None:
    """Résout un utilisateur par e-mail (insensible à la casse)."""
    return (
        db.session.query(User)
        .filter(func.lower(User.email) == email.strip().lower())
        .first()
    )
