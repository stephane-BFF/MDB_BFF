"""Tests unitaires — validateurs métier (`app.utils.validators`)."""
from __future__ import annotations

import pytest

from app.utils import validators


class TestCalculateTestPressure:
    @pytest.mark.parametrize(
        ("ps", "expected"),
        [(10.0, 14.3), (16.0, 22.9), (0.0, 0.0), (7.0, 10.0)],
    )
    def test_regle_bff_1_43(self, ps: float, expected: float) -> None:
        assert validators.calculate_test_pressure(ps) == expected

    def test_coefficient_personnalise(self) -> None:
        assert validators.calculate_test_pressure(10.0, coefficient=1.5) == 15.0


class TestNumeroAffaire:
    @pytest.mark.parametrize(
        ("numero", "valide"),
        [
            ("BN0811", True),
            ("BP1234", True),
            ("bn0811", True),        # normalisé en majuscules
            ("BN2026-042", False),   # ancien format auto-généré, plus valide
            ("BN081", False),        # 3 chiffres
            ("BN08111", False),      # 5 chiffres
            ("BX0811", False),       # préfixe inconnu
            ("", False),
            ("nimportequoi", False),
        ],
    )
    def test_is_valid_numero_affaire(self, numero: str, valide: bool) -> None:
        assert validators.is_valid_numero_affaire(numero) is valide


class TestIsValidItem:
    @pytest.mark.parametrize(
        ("item", "valide"),
        [
            ("8975", True),
            ("0001", True),
            ("123", False),
            ("12345", False),
            ("", False),
            ("abcd", False),
        ],
    )
    def test_is_valid_item(self, item: str, valide: bool) -> None:
        assert validators.is_valid_item(item) is valide


class TestExtensions:
    @pytest.mark.parametrize(
        ("filename", "ok"),
        [
            ("photo.jpg", True),
            ("PLAN.PDF", True),
            ("archive.zip", False),
            ("sans_extension", False),
            ("doc.tiff", True),
        ],
    )
    def test_is_allowed_extension(self, filename: str, ok: bool) -> None:
        allowed = frozenset({"pdf", "jpg", "jpeg", "png", "tiff"})
        assert validators.is_allowed_extension(filename, allowed) is ok
