"""Validateurs métier réutilisables — calculs et règles BFF."""
import re


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
    """Vérifie le format BN{AAAA}-{NNN} (ex: BN2026-042).

    Args:
        numero: Numéro d'affaire à valider.

    Returns:
        True si le format est conforme.
    """
    return bool(re.fullmatch(r"BN\d{4}-\d{3}", numero))


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
