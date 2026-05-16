"""Service formulaire AIRSAV — PV de test air-savon.

Référence CDC v2 : §19 « Test air-savon ».
Déclencheur : dudgeonnage présent ou requis par client/code.
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AirSavService(SimpleFormulaireService):
    CODE = "AIRSAV"
    CHAPITRE = Chapitre.E
    TITLE = "Procès-verbal de test air-savon"
    TITLE_EN = "Soap bubble leak test report"
    REQUIRED_FOR_VALIDATION = frozenset({"date_airsav", "pression_test", "duree", "resultat"})
    SECTIONS = [
        SectionSpec("Test air-savon", [
            FieldSpec("date_airsav", "Date du test", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("pression_test", "Pression de test (bar)", "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("duree", "Durée de maintien (min)", "float",
                      required=True, step="1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("manometre", "Manomètre utilisé", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text="Phase 4 : sélection depuis le référentiel métrologie."),
            FieldSpec("operateur", "Opérateur", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text="Phase 4 : sélection depuis le référentiel QC."),
            FieldSpec("controleur", "Contrôleur", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text="Phase 4 : sélection depuis le référentiel QC."),
        ]),
        SectionSpec("Résultat", [
            FieldSpec("resultat", "Résultat", "select",
                      options=[
                          ("", "— Sélectionner —"),
                          ("pas_de_fuite", "Pas de fuite"),
                          ("fuite_detectee", "Fuite détectée"),
                      ],
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("fuites_detectees", "Description des fuites", "textarea",
                      maxlength=1000, rows=2, col_class="col-12",
                      help_text="Si applicable."),
            FieldSpec("actions", "Actions correctives", "textarea",
                      maxlength=1000, rows=2, col_class="col-12",
                      help_text="Si applicable."),
        ]),
    ]
