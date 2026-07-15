"""Service formulaire BIM — Bordereau d'identification des matériaux de base.

Référence CDC v2 : §9 « Bordereau d'identification des matériaux ».
Tableau dynamique JS — chaque ligne décrit un composant avec son coupon
de matériau (numéro de coulée, norme, fournisseur, référence CCPU).
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

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
        title=_l("Matériaux de base"),
        cols=[
            ColSpec("repere_composant", _l("Repère composant"), "text",
                    required=True, maxlength=50, width="w-15"),
            ColSpec("designation", _l("Désignation"), "text",
                    required=True, maxlength=150, width="w-20"),
            ColSpec("norme_materiau", _l("Norme matériau"), "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("num_coulee", _l("N° coulée"), "text",
                    required=True, maxlength=50, width="w-10"),
            ColSpec("num_lot", _l("N° lot"), "text",
                    maxlength=50, width="w-10"),
            ColSpec("fournisseur", _l("Fournisseur"), "text",
                    maxlength=100, width="w-15"),
            ColSpec("ref_ccpu", _l("Réf. CCPU"), "text",
                    maxlength=50, width="w-10",
                    help_text=_l(
                        "Référence dans le cahier des contrôles et procédures d'usinage."
                    )),
            ColSpec("remarques", _l("Remarques"), "text",
                    maxlength=200, width="w-auto"),
        ],
    )
