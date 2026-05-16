"""Validateurs métier réutilisables — calculs et règles BFF."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, scoped_session


_NUMERO_RE = re.compile(r"^BN(\d{4})-(\d{3})$")


def calculate_test_pressure(design_pressure: float, coefficient: float = 1.43) -> float:
    """Calcule la pression d'épreuve PT selon la règle BFF.

    Args:
        design_pressure: Pression de calcul PS en bar.
        coefficient: Coefficient multiplicateur (1.43 pour eau, configurable).

    Returns:
        Pression d'épreuve PT arrondie à 1 décimale.
    """
    return round(design_pressure * coefficient, 1)


def is_valid_numero_affaire(numero: str) -> bool:
    """Vérifie le format BN{AAAA}-{NNN} (ex: BN2026-042)."""
    return bool(_NUMERO_RE.fullmatch(numero))


def parse_numero_affaire(numero: str) -> tuple[int, int] | None:
    """Décompose un numéro ``BN{AAAA}-{NNN}`` en ``(annee, sequence)``.

    Returns:
        Le tuple ``(annee, sequence)`` ou ``None`` si format invalide.
    """
    match = _NUMERO_RE.fullmatch(numero)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def next_numero_affaire(session: Session | scoped_session[Session], annee: int) -> str:
    """Calcule le prochain numéro d'affaire disponible pour une année donnée.

    Format de retour : ``BN{annee}-{NNN}`` avec ``NNN`` = max(séquence)+1 sur 3 digits.
    Démarre à ``001`` si aucune affaire pour cette année.

    Args:
        session: Session SQLAlchemy active.
        annee: Année cible (4 chiffres).

    Returns:
        Le numéro d'affaire suivant disponible.
    """
    from app.models.affaire import Affaire  # import local : évite cycle utils ↔ models

    prefix = f"BN{annee}-"
    rows = session.query(Affaire.numero_affaire).filter(
        Affaire.numero_affaire.like(f"{prefix}%")
    ).all()
    max_seq = 0
    for (num,) in rows:
        parsed = parse_numero_affaire(num or "")
        if parsed is not None:
            max_seq = max(max_seq, parsed[1])
    return f"{prefix}{max_seq + 1:03d}"


def is_allowed_extension(filename: str, allowed: frozenset[str]) -> bool:
    """Vérifie que l'extension du fichier est autorisée.

    Args:
        filename: Nom du fichier uploadé.
        allowed: Extensions autorisées (sans point).

    Returns:
        True si l'extension est dans la liste autorisée.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in allowed
