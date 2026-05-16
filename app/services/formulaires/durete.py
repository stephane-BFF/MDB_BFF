"""Service formulaire DURETE — PV de contrôle de dureté.

Référence CDC v2 : §16 « Procès-verbal de dureté ».
En-tête fixe (duromètre, échelle, critère max) + tableau dynamique
avec calcul automatique de la conformité (mesure ≤ critère_max).

Déclencheur : requis si le code de construction ou le client le spécifie.
"""
from __future__ import annotations

from typing import Any

from app.enums import Chapitre
from app.services.formulaires.base import (
    ColSpec,
    FieldSpec,
    SectionSpec,
    TableFormulaireService,
    TableSpec,
)


class DureteService(TableFormulaireService):
    CODE = "DURETE"
    CHAPITRE = Chapitre.D
    TITLE = "Procès-verbal de contrôle de dureté"
    TITLE_EN = "Hardness test record"
    REQUIRED_LIGNES = 1
    REQUIRED_HEADER = frozenset({"procedure", "echelle", "critere_max", "date_durete"})
    HEADER_SECTIONS = [
        SectionSpec("Paramètres du contrôle", [
            FieldSpec("procedure", "Référence procédure", "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("durometre", "Duromètre utilisé", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text="Phase 4 : sélection depuis le référentiel métrologie."),
            FieldSpec("echelle", "Échelle de dureté", "select",
                      options=[
                          ("", "— Sélectionner —"),
                          ("HB", "HB — Brinell"),
                          ("HV", "HV — Vickers"),
                          ("HR", "HR — Rockwell"),
                      ],
                      required=True, col_class="col-sm-6 col-md-2"),
            FieldSpec("critere_max", "Dureté maximale acceptée", "float",
                      required=True, step="1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("operateur", "Opérateur", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text="Phase 4 : sélection depuis le référentiel QC."),
            FieldSpec("date_durete", "Date du contrôle", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
        ]),
    ]
    TABLE_SPEC = TableSpec(
        title="Mesures de dureté",
        cols=[
            ColSpec("num_joint", "Référence joint", "text",
                    required=True, maxlength=50, width="w-12"),
            ColSpec("localisation", "Localisation", "text",
                    required=True, maxlength=150, width="w-25"),
            ColSpec("zone", "Zone", "select",
                    options=[
                        ("", "—"),
                        ("metal_base", "Métal de base"),
                        ("zat", "ZAT"),
                        ("bain_soudure", "Bain de soudure"),
                    ],
                    required=True, width="w-12"),
            ColSpec("mesure", "Valeur mesurée", "float",
                    required=True, step="0.1", min_val="0", width="w-10"),
            ColSpec("conformite", "Conforme", "checkbox",
                    server_computed=True, width="w-8"),
        ],
    )

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        data = super()._sanitize_payload(raw)
        header = data.get("header", {})
        critere_max = header.get("critere_max")

        for ligne in data.get("lignes", []):
            mesure = ligne.get("mesure")
            if isinstance(mesure, (int, float)) and isinstance(critere_max, (int, float)):
                ligne["conformite"] = bool(mesure <= critere_max)

        return data
