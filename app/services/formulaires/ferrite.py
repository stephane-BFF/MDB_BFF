"""Service formulaire FERRITE — Contrôle de teneur en ferrite delta.

Référence CDC v2 : §17 « Contrôle de teneur en ferrite ».
En-tête fixe (ferritoscope, critères min/max) + tableau dynamique
avec calcul automatique de la conformité (critere_min ≤ mesure ≤ critere_max).

Déclencheur : matériau austénitique (304L, 316L, 2205, 2507…).
"""
from __future__ import annotations

from typing import Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import (
    ColSpec,
    FieldSpec,
    SectionSpec,
    TableFormulaireService,
    TableSpec,
)


class FeriteService(TableFormulaireService):
    CODE = "FERRITE"
    CHAPITRE = Chapitre.D
    TITLE = "Procès-verbal de contrôle de teneur en ferrite"
    TITLE_EN = "Delta ferrite content inspection record"
    REQUIRED_LIGNES = 1
    REQUIRED_HEADER = frozenset({"procedure", "critere_min", "critere_max", "date_ferrite"})
    HEADER_SECTIONS = [
        SectionSpec(_l("Paramètres du contrôle"), [
            FieldSpec("procedure", _l("Référence procédure"), "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("ferritoscope", _l("Ferritoscope utilisé"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Phase 4 : sélection depuis le référentiel métrologie.")),
            FieldSpec("critere_min", _l("Teneur min. en ferrite (FN)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("critere_max", _l("Teneur max. en ferrite (FN)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("operateur", _l("Opérateur"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text=_l("Phase 4 : sélection depuis le référentiel QC.")),
            FieldSpec("date_ferrite", _l("Date du contrôle"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
        ]),
    ]
    TABLE_SPEC = TableSpec(
        title=_l("Mesures de teneur en ferrite"),
        cols=[
            ColSpec("num_joint", _l("Référence joint"), "text",
                    required=True, maxlength=50, width="w-12"),
            ColSpec("localisation", _l("Localisation"), "text",
                    required=True, maxlength=150, width="w-25"),
            ColSpec("zone", _l("Zone"), "select",
                    options=[
                        ("", _l("—")),
                        ("metal_base", _l("Métal de base")),
                        ("zat", _l("ZAT")),
                        ("bain_soudure", _l("Bain de soudure")),
                    ],
                    required=True, width="w-12"),
            ColSpec("mesure", _l("Valeur mesurée (FN)"), "float",
                    required=True, step="0.1", min_val="0", width="w-10"),
            ColSpec("conformite", _l("Conforme"), "checkbox",
                    server_computed=True, width="w-8"),
        ],
    )

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        data = super()._sanitize_payload(raw)
        header = data.get("header", {})
        critere_min = header.get("critere_min")
        critere_max = header.get("critere_max")

        for ligne in data.get("lignes", []):
            mesure = ligne.get("mesure")
            if (isinstance(mesure, (int, float))
                    and isinstance(critere_min, (int, float))
                    and isinstance(critere_max, (int, float))):
                ligne["conformite"] = bool(critere_min <= mesure <= critere_max)

        return data
