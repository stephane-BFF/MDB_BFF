"""Service formulaire LISTSOUD — Liste des soudeurs qualifiés.

Référence CDC v2 : §8 « Liste des soudeurs ».
Tableau dynamique JS — chaque ligne décrit un soudeur avec ses qualifications.
Liens vers le référentiel Soudeurs déférés à la Phase 4.
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import ColSpec, TableFormulaireService, TableSpec


class ListSoudService(TableFormulaireService):
    CODE = "LISTSOUD"
    CHAPITRE = Chapitre.C
    TITLE = "Liste des soudeurs qualifiés"
    TITLE_EN = "Qualified welders list"
    REQUIRED_LIGNES = 1
    HEADER_SECTIONS = []
    TABLE_SPEC = TableSpec(
        title="Soudeurs",
        cols=[
            ColSpec("id_soudeur", "ID soudeur", "text",
                    required=True, maxlength=20, width="w-10",
                    help_text="Phase 4 : sélection depuis le référentiel Soudeurs."),
            ColSpec("initiales", "Initiales / Poinçon", "text",
                    required=True, maxlength=10, width="w-10"),
            ColSpec("nom", "Nom complet", "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("procedes", "Procédés qualifiés", "text",
                    required=True, maxlength=200, width="w-15",
                    help_text="Ex : TIG 141, MIG 131"),
            ColSpec("materiaux", "Matériaux qualifiés", "text",
                    required=True, maxlength=200, width="w-15",
                    help_text="Ex : Acier carbone P1, Inox P8"),
            ColSpec("positions", "Positions qualifiées", "text",
                    required=True, maxlength=100, width="w-10",
                    help_text="Ex : PA, PB, PC, PD, PF"),
            ColSpec("ref_qualification", "Référence qualification", "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("date_validite", "Date de validité", "date",
                    required=True, width="w-10"),
            ColSpec("date_dernier_emploi", "Dernier emploi affaire", "date",
                    width="w-10"),
        ],
    )
