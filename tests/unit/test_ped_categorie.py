"""Tests unitaires — calcul de catégorie PED récipients (annexe II, tableaux 1-4).

Chaque frontière est testée de part et d'autre (la ligne de démarcation
appartient à la catégorie inférieure).
"""
from __future__ import annotations

import pytest

from app.services.ped_categorie import (
    ART_43,
    HORS_CHAMP,
    compute_categorie_recipient,
)


def _cat(etat: str, groupe: str, ps: float, v: float) -> str:
    return compute_categorie_recipient(etat, groupe, ps, v).categorie


class TestHorsChampEtValidation:
    def test_ps_sous_0_5_bar_hors_champ(self) -> None:
        assert _cat("gaz", "1", 0.5, 100) == HORS_CHAMP

    @pytest.mark.parametrize(
        ("etat", "groupe", "ps", "v"),
        [
            ("plasma", "1", 10, 10),
            ("gaz", "3", 10, 10),
            ("gaz", "1", 0, 10),
            ("gaz", "1", 10, 0),
        ],
    )
    def test_parametres_invalides(
        self, etat: str, groupe: str, ps: float, v: float
    ) -> None:
        with pytest.raises(ValueError):
            compute_categorie_recipient(etat, groupe, ps, v)


class TestTableau1GazGroupe1:
    @pytest.mark.parametrize(
        ("ps", "v", "attendu"),
        [
            (25, 1.0, ART_43),      # V ≤ 1 : art. 4.3 jusqu'à PS 200
            (200, 1.0, ART_43),
            (201, 1.0, "III"),      # V ≤ 1 : III entre PS 200 et 1000
            (1000, 0.5, "III"),
            (1001, 0.5, "IV"),      # V ≤ 1 : IV au-delà de PS 1000
            (12.5, 2, ART_43),      # PS·V = 25 → art. 4.3 (frontière incluse)
            (13, 2, "I"),           # PS·V = 26 → I
            (25, 2, "I"),           # PS·V = 50 → I (frontière incluse)
            (25.5, 2, "II"),        # PS·V = 51 → II
            (100, 2, "II"),         # PS·V = 200 → II
            (100.5, 2, "III"),      # PS·V = 201 → III
            (500, 2, "III"),        # PS·V = 1000 → III
            (100, 10.1, "IV"),      # PS·V = 1010 → IV
            (100, 10000, "IV"),     # exemple guide : 100 bar × 10 000 L → IV
        ],
    )
    def test_frontieres(self, ps: float, v: float, attendu: str) -> None:
        assert _cat("gaz", "1", ps, v) == attendu


class TestTableau2GazGroupe2:
    @pytest.mark.parametrize(
        ("ps", "v", "attendu"),
        [
            (1000, 1.0, ART_43),    # V ≤ 1 : art. 4.3 jusqu'à PS 1000
            (1001, 0.5, "III"),
            (3001, 0.5, "IV"),
            (4, 1000, ART_43),      # PS ≤ 4 : art. 4.3 quel que soit V
            (25, 2, ART_43),        # PS·V = 50 → art. 4.3
            (26, 2, "I"),           # PS·V = 52 → I
            (100, 2, "I"),          # PS·V = 200 → I
            (101, 2, "II"),         # PS·V = 202 → II
            (100, 10, "II"),        # PS·V = 1000 → II
            (101, 10, "III"),       # PS·V = 1010 → III
            (100, 30, "III"),       # PS·V = 3000 → III
            (101, 30, "IV"),        # PS·V = 3030 → IV
        ],
    )
    def test_frontieres(self, ps: float, v: float, attendu: str) -> None:
        assert _cat("gaz", "2", ps, v) == attendu


class TestTableau3LiquideGroupe1:
    @pytest.mark.parametrize(
        ("ps", "v", "attendu"),
        [
            (10, 20, ART_43),       # PS·V = 200 → art. 4.3
            (8, 30, "I"),           # PS ≤ 10 et PS·V > 200 → I
            (10, 21, "I"),
            (11, 20, "II"),         # 10 < PS ≤ 500 et PS·V > 200 → II
            (500, 10, "II"),
            (501, 0.1, "II"),       # PS > 500 mais PS·V ≤ 200 → II
            (501, 1, "III"),        # PS > 500 et PS·V > 200 → III
            (400, 0.4, ART_43),     # PS ≤ 500 et PS·V ≤ 200 → art. 4.3
        ],
    )
    def test_frontieres(self, ps: float, v: float, attendu: str) -> None:
        assert _cat("liquide", "1", ps, v) == attendu


class TestTableau4LiquideGroupe2:
    @pytest.mark.parametrize(
        ("ps", "v", "attendu"),
        [
            (10, 100000, ART_43),   # PS ≤ 10 : art. 4.3 quel que soit V
            (11, 100, ART_43),      # PS·V ≤ 10 000 et PS ≤ 1000 → art. 4.3
            (1000, 10, ART_43),
            (1001, 5, "I"),         # PS > 1000 à PS·V ≤ 10 000 → I
            (11, 1000, "I"),        # PS·V = 11 000, PS ≤ 500 → I
            (500, 21, "I"),
            (501, 21, "II"),        # PS > 500 et PS·V > 10 000 → II
        ],
    )
    def test_frontieres(self, ps: float, v: float, attendu: str) -> None:
        assert _cat("liquide", "2", ps, v) == attendu


class TestExplication:
    def test_explication_contient_tableau_et_valeurs(self) -> None:
        resultat = compute_categorie_recipient("gaz", "1", 100, 10)
        assert resultat.tableau == 1
        assert "Tableau 1" in resultat.explication
        assert "100" in resultat.explication
        assert resultat.categorie == "III"
