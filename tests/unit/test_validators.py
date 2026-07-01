"""Tests unitaires — validateurs métier (`app.utils.validators`)."""
from __future__ import annotations

import pytest
from flask import Flask

from app.enums import Statut
from app.extensions import db
from app.models.affaire import Affaire
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
            ("BN2026-042", True),
            ("BN2026-001", True),
            ("BP2026-042", False),   # préfixe BP non géré par ce validateur
            ("BN26-042", False),
            ("BN2026-42", False),
            ("", False),
            ("nimportequoi", False),
        ],
    )
    def test_is_valid_numero_affaire(self, numero: str, valide: bool) -> None:
        assert validators.is_valid_numero_affaire(numero) is valide

    def test_parse_valide(self) -> None:
        assert validators.parse_numero_affaire("BN2026-042") == (2026, 42)

    def test_parse_invalide(self) -> None:
        assert validators.parse_numero_affaire("BN26-42") is None


class TestNextNumeroAffaire:
    def test_premier_numero_de_lannee(self, app: Flask) -> None:
        with app.app_context():
            assert validators.next_numero_affaire(db.session, 2027) == "BN2027-001"

    def test_incremente_le_max(self, app: Flask, user_redacteur) -> None:  # noqa: ANN001
        with app.app_context():
            for seq in (1, 2, 5):
                db.session.add(
                    Affaire(
                        numero_affaire=f"BN2028-{seq:03d}",
                        annee=2028,
                        statut=Statut.BROUILLON,
                        cree_par_id=user_redacteur.id,
                    )
                )
            db.session.commit()
            # max = 5 → suivant = 006 (ignore les autres années)
            assert validators.next_numero_affaire(db.session, 2028) == "BN2028-006"


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
