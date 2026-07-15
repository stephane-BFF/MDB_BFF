"""Service formulaire BIMSoud — Bordereau d'identification des matériaux de soudage.

Référence CDC v2 : §10 « Bordereau d'identification des matériaux de soudage ».
Tableau dynamique JS — chaque ligne décrit un consommable de soudage
(électrode, fil, flux) avec son diamètre, numéro de lot et utilisation.
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import ColSpec, TableFormulaireService, TableSpec


class BimSoudService(TableFormulaireService):
    CODE = "BIMSOUD"
    CHAPITRE = Chapitre.B
    TITLE = "Bordereau d'identification des matériaux de soudage"
    TITLE_EN = "Bill of material — welding consumables"
    REQUIRED_LIGNES = 1
    HEADER_SECTIONS = []
    TABLE_SPEC = TableSpec(
        title=_l("Matériaux de soudage"),
        cols=[
            ColSpec("designation", _l("Désignation"), "text",
                    required=True, maxlength=150, width="w-20"),
            ColSpec("norme", _l("Norme"), "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("diametre", _l("Diamètre (mm)"), "float",
                    required=True, step="0.1", min_val="0", width="w-10"),
            ColSpec("num_lot", _l("N° lot"), "text",
                    required=True, maxlength=50, width="w-10"),
            ColSpec("fournisseur", _l("Fournisseur"), "text",
                    maxlength=100, width="w-15"),
            ColSpec("utilisation", _l("Utilisation"), "text",
                    maxlength=150, width="w-15",
                    help_text=_l("Ex : assemblage, rechargement, reprise…")),
            ColSpec("ref_ccpu", _l("Réf. CCPU"), "text",
                    maxlength=50, width="w-auto"),
        ],
    )
