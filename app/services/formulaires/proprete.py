"""Service formulaire PROPRETE — PV de contrôle de propreté.

Référence CDC v2 : §24 « PV de propreté ».
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class PropreteService(SimpleFormulaireService):
    CODE = "PROPRETE"
    CHAPITRE = Chapitre.F
    TITLE = "Procès-verbal de contrôle de propreté"
    TITLE_EN = "Cleanliness inspection report"
    REQUIRED_FOR_VALIDATION = frozenset({"date_controle", "methode", "resultat"})
    SECTIONS = [
        SectionSpec("Contrôle de propreté", [
            FieldSpec("date_controle", "Date du contrôle", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("methode", "Méthode de vérification", "select",
                      options=[
                          ("", "— Sélectionner —"),
                          ("visuelle", "Visuelle"),
                          ("chiffon_blanc", "Chiffon blanc"),
                          ("lampe_endoscope", "Lampe / endoscope"),
                          ("autre", "Autre"),
                      ],
                      required=True, col_class="col-sm-6 col-md-4"),
            FieldSpec("critere", "Critère d'acceptation", "text",
                      maxlength=200, col_class="col-12 col-md-6",
                      help_text="Ex : Absence de corps étrangers, pas de copeaux."),
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
            FieldSpec("observations", "Observations", "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
