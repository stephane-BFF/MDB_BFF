"""Tests unitaires — service HYDR (calcul PT, sanitisation du payload)."""
from __future__ import annotations

import pytest

from app.services.formulaires.hydr import _sanitize_payload, compute_pt


class TestComputePt:
    def test_basic(self) -> None:
        # 10 × 1.43 = 14.3 — cas nominal
        assert compute_pt(10.0) == 14.3

    def test_rounding(self) -> None:
        # 7 × 1.43 = 10.01 → arrondi 1 décimale = 10.0
        assert compute_pt(7.0) == 10.0

    def test_fraction(self) -> None:
        # 5.5 × 1.43 = 7.865 → arrondi à 7.9
        assert compute_pt(5.5) == pytest.approx(7.9)

    def test_large_pressure(self) -> None:
        assert compute_pt(100.0) == 143.0

    def test_ped_example(self) -> None:
        # Exemple typique PED 2014/68/UE : PS=16 bar → PT=22.88 → arrondi 22.9
        assert compute_pt(16.0) == pytest.approx(22.9)

    def test_formula_invariant(self) -> None:
        # PT doit toujours être ≥ PS (facteur 1.43 > 1)
        for ps in (0.5, 1.0, 10.0, 50.0, 250.0):
            assert compute_pt(ps) > ps


class TestSanitizePayload:
    def test_pt_recomputed_ignoring_client_value(self) -> None:
        clean = _sanitize_payload({"ps": "10", "pt": "999"})
        assert clean["ps"] == 10.0
        assert clean["pt"] == pytest.approx(14.3)

    def test_unknown_keys_stripped(self) -> None:
        clean = _sanitize_payload({"ps": "10", "evil": "injection", "admin": True})
        assert "evil" not in clean
        assert "admin" not in clean

    def test_empty_strings_stripped(self) -> None:
        clean = _sanitize_payload({"ps": "10", "observations": "", "fluide": ""})
        assert "observations" not in clean
        assert "fluide" not in clean

    def test_none_stripped(self) -> None:
        clean = _sanitize_payload({"ps": "10", "fluide": None})
        assert "fluide" not in clean

    def test_conforme_string_true(self) -> None:
        assert _sanitize_payload({"conforme": "true"})["conforme"] is True

    def test_conforme_string_false(self) -> None:
        assert _sanitize_payload({"conforme": "false"})["conforme"] is False

    def test_conforme_bool_false(self) -> None:
        assert _sanitize_payload({"conforme": False})["conforme"] is False

    def test_conforme_bool_true(self) -> None:
        assert _sanitize_payload({"conforme": True})["conforme"] is True

    def test_duree_minutes_cast_to_int(self) -> None:
        assert _sanitize_payload({"duree_minutes": "45"})["duree_minutes"] == 45

    def test_temperature_cast_to_float(self) -> None:
        assert _sanitize_payload({"temperature_c": "20.5"})["temperature_c"] == pytest.approx(20.5)

    def test_invalid_ps_excluded(self) -> None:
        clean = _sanitize_payload({"ps": "not_a_number"})
        assert "ps" not in clean
        assert "pt" not in clean

    def test_no_ps_means_no_pt(self) -> None:
        clean = _sanitize_payload({"fluide": "eau", "date_epreuve": "2026-05-13"})
        assert "pt" not in clean

    def test_valid_fluide_kept(self) -> None:
        clean = _sanitize_payload({"fluide": "eau"})
        assert clean["fluide"] == "eau"

    def test_allowed_keys_exhaustive(self) -> None:
        payload = {
            "ps": 10.0, "fluide": "eau", "date_epreuve": "2026-05-13",
            "duree_minutes": "30", "temperature_c": "20",
            "numero_manometre": "MAN-001", "conforme": "true",
            "observations": "RAS",
        }
        clean = _sanitize_payload(payload)
        assert "ps" in clean
        assert "pt" in clean  # recomputed
        assert "fluide" in clean
        assert "date_epreuve" in clean
        assert "duree_minutes" in clean
        assert "temperature_c" in clean
        assert "numero_manometre" in clean
        assert "conforme" in clean
        assert "observations" in clean
