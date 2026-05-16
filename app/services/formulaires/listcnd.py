"""Service formulaire LISTCND — Liste des contrôleurs CND certifiés.

Référence CDC v2 : §11 « Liste des contrôleurs CND ».
Tableau dynamique JS — chaque ligne décrit un contrôleur avec sa certification.
Liens vers le référentiel CND déférés à la Phase 4.
"""
from __future__ import annotations

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
        title="Contrôleurs CND",
        cols=[
            ColSpec("nom", "Nom / Société", "text",
                    required=True, maxlength=100, width="w-20",
                    help_text="Phase 4 : sélection depuis le référentiel CND."),
            ColSpec("methodes", "Méthodes habilitées", "text",
                    required=True, maxlength=100, width="w-15",
                    help_text="Ex : RT, UT, PT, MT, VT"),
            ColSpec("niveau", "Niveau", "select",
                    options=[
                        ("", "—"),
                        ("1", "Niveau 1"),
                        ("2", "Niveau 2"),
                        ("3", "Niveau 3"),
                    ],
                    required=True, width="w-10"),
            ColSpec("organisme_cert", "Organisme certif.", "text",
                    required=True, maxlength=100, width="w-15",
                    help_text="Ex : Cofrend, ASNT"),
            ColSpec("numero_cert", "N° certification", "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("validite", "Date de validité", "date",
                    required=True, width="w-10"),
            ColSpec("carte_cofrend", "Réf. carte COFREND", "text",
                    maxlength=200, width="w-auto",
                    help_text="Phase 3 : lien vers le fichier réseau."),
        ],
    )
