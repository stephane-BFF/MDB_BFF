"""Service formulaire BIM — Bordereau d'identification des matériaux de base.

Référence CDC v2 : §9 « Bordereau d'identification des matériaux ».
Tableau dynamique JS — chaque ligne décrit un composant avec son coupon
de matériau (numéro de coulée, norme, fournisseur, référence CCPU).
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import ColSpec, TableFormulaireService, TableSpec


class BimService(TableFormulaireService):
    CODE = "BIM"
    CHAPITRE = Chapitre.B
    TITLE = "Bordereau d'identification des matériaux de base"
    TITLE_EN = "Bill of material — base materials"
    REQUIRED_LIGNES = 1
    HEADER_SECTIONS = []
    TABLE_SPEC = TableSpec(
        title="Matériaux de base",
        cols=[
            ColSpec("repere_composant", "Repère composant", "text",
                    required=True, maxlength=50, width="w-15"),
            ColSpec("designation", "Désignation", "text",
                    required=True, maxlength=150, width="w-20"),
            ColSpec("norme_materiau", "Norme matériau", "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("num_coulee", "N° coulée", "text",
                    required=True, maxlength=50, width="w-10"),
            ColSpec("num_lot", "N° lot", "text",
                    maxlength=50, width="w-10"),
            ColSpec("fournisseur", "Fournisseur", "text",
                    maxlength=100, width="w-15"),
            ColSpec("ref_ccpu", "Réf. CCPU", "text",
                    maxlength=50, width="w-10",
                    help_text="Référence dans le cahier des contrôles et procédures d'usinage."),
            ColSpec("remarques", "Remarques", "text",
                    maxlength=200, width="w-auto"),
        ],
    )
