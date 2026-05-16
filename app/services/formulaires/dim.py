"""Service formulaire DIM — Procès-verbal dimensionnel.

Référence CDC v2 : §21 « PV dimensionnel ».
En-tête fixe (référence plan, instrument) + tableau dynamique avec
calcul automatique de l'écart et de la conformité par rapport aux tolérances.

Formules :
    ecart      = valeur_mesuree - valeur_nominale
    conformite = -tolerance_moins ≤ ecart ≤ tolerance_plus
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


class DimService(TableFormulaireService):
    CODE = "DIM"
    CHAPITRE = Chapitre.C
    TITLE = "Procès-verbal de contrôle dimensionnel"
    TITLE_EN = "Dimensional inspection record"
    REQUIRED_LIGNES = 1
    REQUIRED_HEADER = frozenset({"ref_plan", "date_dim"})
    HEADER_SECTIONS = [
        SectionSpec("Identification", [
            FieldSpec("ref_plan", "Référence du plan", "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("rev_plan", "Révision du plan", "text",
                      maxlength=20, col_class="col-sm-6 col-md-2"),
            FieldSpec("date_dim", "Date du contrôle", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("instrument", "Instrument de mesure", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text="Phase 4 : sélection depuis le référentiel métrologie."),
            FieldSpec("operateur", "Opérateur", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text="Phase 4 : sélection depuis le référentiel QC."),
        ]),
    ]
    TABLE_SPEC = TableSpec(
        title="Cotes à contrôler",
        cols=[
            ColSpec("num_cote", "N° / Repère", "text",
                    required=True, maxlength=20, width="w-8"),
            ColSpec("description", "Description", "text",
                    required=True, maxlength=150, width="w-20"),
            ColSpec("valeur_nominale", "Nominale (mm)", "float",
                    required=True, step="0.001", width="w-10"),
            ColSpec("tolerance_plus", "Tol. + (mm)", "float",
                    required=True, step="0.001", min_val="0", width="w-8"),
            ColSpec("tolerance_moins", "Tol. - (mm)", "float",
                    required=True, step="0.001", min_val="0", width="w-8"),
            ColSpec("valeur_mesuree", "Mesurée (mm)", "float",
                    required=True, step="0.001", width="w-10"),
            ColSpec("ecart", "Écart (mm)", "float",
                    server_computed=True, step="0.001", width="w-8"),
            ColSpec("conformite", "Conforme", "checkbox",
                    server_computed=True, width="w-8"),
            ColSpec("remarques", "Remarques", "text",
                    maxlength=200, width="w-auto"),
        ],
    )

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        data = super()._sanitize_payload(raw)

        for ligne in data.get("lignes", []):
            val_mes = ligne.get("valeur_mesuree")
            val_nom = ligne.get("valeur_nominale")
            tol_plus = ligne.get("tolerance_plus")
            tol_moins = ligne.get("tolerance_moins")

            if isinstance(val_mes, (int, float)) and isinstance(val_nom, (int, float)):
                ecart = round(val_mes - val_nom, 3)
                ligne["ecart"] = ecart
                if (isinstance(tol_plus, (int, float))
                        and isinstance(tol_moins, (int, float))):
                    ligne["conformite"] = bool(-tol_moins <= ecart <= tol_plus)

        return data
