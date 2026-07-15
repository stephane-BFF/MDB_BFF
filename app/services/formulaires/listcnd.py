"""Service formulaire LISTCND — Liste des contrôleurs CND certifiés.

Référence CDC v2 : §11 « Liste des contrôleurs CND ».
Tableau dynamique JS — chaque ligne décrit un contrôleur avec sa certification.
Liens vers le référentiel CND déférés à la Phase 4.
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import ColSpec, TableFormulaireService, TableSpec


class ListCndService(TableFormulaireService):
    CODE = "LISTCND"
    CHAPITRE = Chapitre.D
    TITLE = "Liste des contrôleurs CND certifiés"
    TITLE_EN = "Certified NDT operators list"
    REQUIRED_LIGNES = 1
    HEADER_SECTIONS = []
    TABLE_SPEC = TableSpec(
        title=_l("Contrôleurs CND"),
        cols=[
            ColSpec("nom", _l("Nom / Société"), "text",
                    required=True, maxlength=100, width="w-20",
                    help_text=_l("Phase 4 : sélection depuis le référentiel CND.")),
            ColSpec("methodes", _l("Méthodes habilitées"), "text",
                    required=True, maxlength=100, width="w-15",
                    help_text=_l("Ex : RT, UT, PT, MT, VT")),
            ColSpec("niveau", _l("Niveau"), "select",
                    options=[
                        ("", _l("—")),
                        ("1", _l("Niveau 1")),
                        ("2", _l("Niveau 2")),
                        ("3", _l("Niveau 3")),
                    ],
                    required=True, width="w-10"),
            ColSpec("organisme_cert", _l("Organisme certif."), "text",
                    required=True, maxlength=100, width="w-15",
                    help_text=_l("Ex : Cofrend, ASNT")),
            ColSpec("numero_cert", _l("N° certification"), "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("validite", _l("Date de validité"), "date",
                    required=True, width="w-10"),
            ColSpec("carte_cofrend", _l("Réf. carte COFREND"), "text",
                    maxlength=200, width="w-auto",
                    help_text=_l("Phase 3 : lien vers le fichier réseau.")),
        ],
    )
