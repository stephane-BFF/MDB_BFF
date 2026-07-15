"""Validateurs métier réutilisables — calculs et règles BFF."""
from __future__ import annotations

import re

_NUMERO_RE = re.compile(r"^(BN|BP)\d{4}$")
_ITEM_RE = re.compile(r"^\d{4}$")


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
    """Vérifie le format BN|BP + 4 chiffres attribué par le BE (ex: BN0811)."""
    return bool(_NUMERO_RE.fullmatch(numero.upper()))


def is_valid_item(item: str) -> bool:
    """Vérifie le format du n° d'item (4 chiffres, ex: 8975)."""
    return bool(_ITEM_RE.fullmatch(item))


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
