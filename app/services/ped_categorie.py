"""Calcul de la catégorie de risque PED pour les récipients (annexe II).

Transcription des tableaux 1 à 4 de l'annexe II de la directive 2014/68/UE
(récipients — les échangeurs tubulaires BFF sont des récipients sous
pression). Les frontières des diagrammes ont été croisées sur trois sources
concordantes (support de cours DESP J.-L. Joulin, note de conformité PED
Blacoh, seuils de suivi en service DREAL Centre-Val de Loire) :

    Tableau 1 — gaz, groupe 1 : PS·V = 25 / 50 / 200 / 1000 ;
        pour V ≤ 1 L : art. 4.3 jusqu'à PS 200, III jusqu'à PS 1000, IV au-delà.
    Tableau 2 — gaz, groupe 2 : PS·V = 50 / 200 / 1000 / 3000 ; art. 4.3
        aussi pour PS ≤ 4 ; pour V ≤ 1 L : art. 4.3 jusqu'à PS 1000,
        III jusqu'à PS 3000, IV au-delà.
    Tableau 3 — liquide, groupe 1 : art. 4.3 si PS ≤ 500 et PS·V ≤ 200 ;
        I si PS ≤ 10 ; II jusqu'à PS 500 (ou PS > 500 à PS·V ≤ 200) ;
        III si PS > 500 et PS·V > 200.
    Tableau 4 — liquide, groupe 2 : art. 4.3 si PS ≤ 10, ou PS ≤ 1000 et
        PS·V ≤ 10 000 ; I au-delà jusqu'à PS 500 (ou PS > 1000 à
        PS·V ≤ 10 000) ; II si PS > 500 et PS·V > 10 000.

Convention de la directive : la ligne de démarcation appartient à la
catégorie inférieure (les seuils sont donc des « ≤ »).

Limites assumées (affichées à l'utilisateur, décision D5 — le calcul ne
remplace jamais la déclaration sans action explicite) :
    - règles particulières non couvertes : gaz instables (→ III/IV),
      extincteurs portables et bouteilles respiratoires (→ III minimum),
      générateurs de vapeur (tableau 5) ;
    - PS ≤ 0,5 bar : hors champ de la directive (art. 1er).
"""
from __future__ import annotations

from dataclasses import dataclass

#: Valeur renvoyée pour un équipement sous les seuils (art. 4 §3 — règles
#: de l'art, sans marquage CE ni module). Alignée sur ``CATEGORIE_ART_43``
#: de ``app.forms.wizard``.
ART_43 = "Art.4.3"

#: Valeur renvoyée quand l'équipement est hors champ DESP (PS ≤ 0,5 bar).
HORS_CHAMP = "hors_champ"


@dataclass(frozen=True)
class CategorieCalculee:
    """Résultat du calcul de catégorie pour un récipient.

    Attributes:
        categorie: ``"I"``–``"IV"``, ``ART_43`` ou ``HORS_CHAMP``.
        tableau: N° du tableau annexe II appliqué (1 à 4), ou ``None``
            si hors champ.
        explication: Phrase lisible justifiant le classement (affichée
            telle quelle dans l'UI).
    """

    categorie: str
    tableau: int | None
    explication: str


def compute_categorie_recipient(
    fluide_etat: str,
    fluide_groupe: str,
    ps_bar: float,
    volume_l: float,
) -> CategorieCalculee:
    """Calcule la catégorie de risque PED d'un récipient (tableaux 1-4).

    Args:
        fluide_etat: ``"gaz"`` ou ``"liquide"``.
        fluide_groupe: ``"1"`` (dangereux) ou ``"2"``.
        ps_bar: Pression maximale admissible PS, en bar.
        volume_l: Volume V, en litres (> 0).

    Returns:
        Le résultat du calcul (catégorie, tableau appliqué, explication).

    Raises:
        ValueError: Si un paramètre est hors domaine (état/groupe inconnus,
            PS ou V non positifs).
    """
    if fluide_etat not in ("gaz", "liquide"):
        raise ValueError(f"État de fluide inconnu : {fluide_etat!r}")
    if fluide_groupe not in ("1", "2"):
        raise ValueError(f"Groupe de fluide inconnu : {fluide_groupe!r}")
    if ps_bar <= 0 or volume_l <= 0:
        raise ValueError("PS et V doivent être strictement positifs.")

    if ps_bar <= 0.5:
        return CategorieCalculee(
            HORS_CHAMP,
            None,
            "PS ≤ 0,5 bar : hors champ de la directive 2014/68/UE (art. 1er).",
        )

    psv = ps_bar * volume_l
    if fluide_etat == "gaz":
        if fluide_groupe == "1":
            return _tableau_1(ps_bar, volume_l, psv)
        return _tableau_2(ps_bar, volume_l, psv)
    if fluide_groupe == "1":
        return _tableau_3(ps_bar, psv)
    return _tableau_4(ps_bar, psv)


def _resultat(categorie: str, tableau: int, ps: float, v: float, psv: float) -> CategorieCalculee:
    libelle = (
        "sous les seuils (art. 4 §3, règles de l'art)"
        if categorie == ART_43
        else f"catégorie {categorie}"
    )
    return CategorieCalculee(
        categorie,
        tableau,
        f"Tableau {tableau} (récipient) : PS = {ps:g} bar, V = {v:g} L, "
        f"PS·V = {psv:g} bar·L → {libelle}.",
    )


def _tableau_1(ps: float, v: float, psv: float) -> CategorieCalculee:
    """Récipients, gaz, fluide du groupe 1."""
    if v <= 1:
        if ps <= 200:
            cat = ART_43
        elif ps <= 1000:
            cat = "III"
        else:
            cat = "IV"
    elif psv <= 25:
        cat = ART_43
    elif psv <= 50:
        cat = "I"
    elif psv <= 200:
        cat = "II"
    elif psv <= 1000:
        cat = "III"
    else:
        cat = "IV"
    return _resultat(cat, 1, ps, v, psv)


def _tableau_2(ps: float, v: float, psv: float) -> CategorieCalculee:
    """Récipients, gaz, fluide du groupe 2."""
    if v <= 1:
        if ps <= 1000:
            cat = ART_43
        elif ps <= 3000:
            cat = "III"
        else:
            cat = "IV"
    elif ps <= 4 or psv <= 50:
        cat = ART_43
    elif psv <= 200:
        cat = "I"
    elif psv <= 1000:
        cat = "II"
    elif psv <= 3000:
        cat = "III"
    else:
        cat = "IV"
    return _resultat(cat, 2, ps, v, psv)


def _tableau_3(ps: float, psv: float) -> CategorieCalculee:
    """Récipients, liquide, fluide du groupe 1."""
    if psv <= 200:
        cat = ART_43 if ps <= 500 else "II"
    elif ps <= 10:
        cat = "I"
    elif ps <= 500:
        cat = "II"
    else:
        cat = "III"
    v = psv / ps
    return _resultat(cat, 3, ps, v, psv)


def _tableau_4(ps: float, psv: float) -> CategorieCalculee:
    """Récipients, liquide, fluide du groupe 2."""
    if ps <= 10:
        cat = ART_43
    elif psv <= 10_000:
        cat = ART_43 if ps <= 1000 else "I"
    elif ps <= 500:
        cat = "I"
    else:
        cat = "II"
    v = psv / ps
    return _resultat(cat, 4, ps, v, psv)
