"""Service formulaire LISTSOUD — Liste des soudeurs qualifiés.

Référence CDC v2 : §8 « Liste des soudeurs ».
Tableau dynamique JS — chaque ligne décrit un soudeur avec ses qualifications.
Liens vers le référentiel Soudeurs déférés à la Phase 4.
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

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
        title=_l("Soudeurs"),
        cols=[
            ColSpec("id_soudeur", _l("ID soudeur"), "text",
                    required=True, maxlength=20, width="w-10",
                    help_text=_l("Phase 4 : sélection depuis le référentiel Soudeurs.")),
            ColSpec("initiales", _l("Initiales / Poinçon"), "text",
                    required=True, maxlength=10, width="w-10"),
            ColSpec("nom", _l("Nom complet"), "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("procedes", _l("Procédés qualifiés"), "text",
                    required=True, maxlength=200, width="w-15",
                    help_text=_l("Ex : TIG 141, MIG 131")),
            ColSpec("materiaux", _l("Matériaux qualifiés"), "text",
                    required=True, maxlength=200, width="w-15",
                    help_text=_l("Ex : Acier carbone P1, Inox P8")),
            ColSpec("positions", _l("Positions qualifiées"), "text",
                    required=True, maxlength=100, width="w-10",
                    help_text=_l("Ex : PA, PB, PC, PD, PF")),
            ColSpec("ref_qualification", _l("Référence qualification"), "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("date_validite", _l("Date de validité"), "date",
                    required=True, width="w-10"),
            ColSpec("date_dernier_emploi", _l("Dernier emploi affaire"), "date",
                    width="w-10"),
        ],
    )
