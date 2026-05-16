"""Service formulaire ROLLING — PV de dudgeonnage (expansion de tubes).

Référence CDC v2 : §14 « Procès-verbal de dudgeonnage ».
En-tête fixe (paramètres de la procédure) + tableau dynamique avec
calcul automatique du taux d'expansion réel et de la conformité.

Formule :
    taux_reel (%) = (ep_avant - ep_apres) / ep_avant × 100
    conformite   = taux_min ≤ taux_reel ≤ taux_max
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


class RollingService(TableFormulaireService):
    CODE = "ROLLING"
    CHAPITRE = Chapitre.C
    TITLE = "Procès-verbal de dudgeonnage"
    TITLE_EN = "Tube rolling / expansion record"
    REQUIRED_LIGNES = 1
    REQUIRED_HEADER = frozenset({"procedure_roll", "taux_min", "taux_max"})
    HEADER_SECTIONS = [
        SectionSpec("Paramètres de dudgeonnage", [
            FieldSpec("procedure_roll", "Référence procédure", "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("outil", "Outil de dudgeonnage", "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("dim_tube", "Dimensions tube (Ø × ép.)", "text",
                      required=True, maxlength=50, col_class="col-sm-6 col-md-3",
                      help_text="Ex : 25.4 × 2.11 mm"),
            FieldSpec("materiau_tube", "Matériau tube", "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-3"),
            FieldSpec("materiau_collecteur", "Matériau collecteur", "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-3"),
            FieldSpec("taux_cible", "Taux d'expansion cible (%)", "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("taux_min", "Taux minimum accepté (%)", "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("taux_max", "Taux maximum accepté (%)", "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
        ]),
    ]
    TABLE_SPEC = TableSpec(
        title="Résultats par tube",
        cols=[
            ColSpec("num_tube", "N° tube", "text",
                    required=True, maxlength=20, width="w-10"),
            ColSpec("ep_avant", "Ép. avant (mm)", "float",
                    required=True, step="0.01", min_val="0", width="w-12"),
            ColSpec("ep_apres", "Ép. après (mm)", "float",
                    required=True, step="0.01", min_val="0", width="w-12"),
            ColSpec("taux_reel", "Taux réel (%)", "float",
                    server_computed=True, step="0.1", width="w-10"),
            ColSpec("conformite", "Conforme", "checkbox",
                    server_computed=True, width="w-8"),
            ColSpec("remarques", "Remarques", "text",
                    maxlength=200, width="w-auto"),
        ],
    )

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        data = super()._sanitize_payload(raw)
        header = data.get("header", {})
        taux_min = header.get("taux_min")
        taux_max = header.get("taux_max")

        for ligne in data.get("lignes", []):
            ep_avant = ligne.get("ep_avant")
            ep_apres = ligne.get("ep_apres")
            if (isinstance(ep_avant, (int, float))
                    and isinstance(ep_apres, (int, float))
                    and ep_avant > 0):
                taux_reel = round((ep_avant - ep_apres) / ep_avant * 100, 1)
                ligne["taux_reel"] = taux_reel
                if (isinstance(taux_min, (int, float))
                        and isinstance(taux_max, (int, float))):
                    ligne["conformite"] = bool(taux_min <= taux_reel <= taux_max)

        return data
