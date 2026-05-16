"""Service formulaire AZOTE — PV de mise sous azote.

Référence CDC v2 : §25 « PV de mise sous azote ».
Déclencheur : requis par le client ou le code de construction.
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AzoteService(SimpleFormulaireService):
    CODE = "AZOTE"
    CHAPITRE = Chapitre.E
    TITLE = "Procès-verbal de mise sous azote"
    TITLE_EN = "Nitrogen pressurization record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_azote", "pression_azote", "pression_verifiee", "resultat"})
    SECTIONS = [
        SectionSpec("Mise sous azote", [
            FieldSpec("date_azote", "Date de l'opération", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("pression_azote", "Pression d'azote (bar g)", "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("manometre", "Manomètre", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text="Phase 4 : sélection depuis le référentiel métrologie."),
            FieldSpec("pression_verifiee", "Pression vérifiée en fin d'opération (bar g)", "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
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
                          ("conforme", "Conforme"),
                          ("non_conforme", "Non conforme"),
                      ],
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("remarques", "Remarques", "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
