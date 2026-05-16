"""Services formulaires TTH1 et TTH2 — PV de traitement thermique.

Référence CDC v2 : §13 « Procès-verbal de traitement thermique ».
Deux codes distincts (avant/après soudage ou deux traitements successifs)
mais structure de champs identique — partagée via ``_TTHBase``.
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService

_REQUIRED = frozenset({
    "date_tth", "procedure_tth", "type_tth",
    "temperature_cible", "duree_palier", "resultat",
})

_SECTIONS = [
    SectionSpec("Paramètres du traitement", [
        FieldSpec("date_tth", "Date du traitement", "date",
                  required=True, col_class="col-sm-6 col-md-3"),
        FieldSpec("procedure_tth", "Référence procédure TTH", "text",
                  required=True, maxlength=100, col_class="col-sm-6 col-md-4"),
        FieldSpec("type_tth", "Type de traitement", "select",
                  options=[
                      ("", "— Sélectionner —"),
                      ("prechauffage", "Préchauffage"),
                      ("pwht", "PWHT"),
                      ("detente", "Détente"),
                      ("autre", "Autre"),
                  ],
                  required=True, col_class="col-sm-6 col-md-3"),
        FieldSpec("temperature_cible", "Température cible (°C)", "float",
                  required=True, step="1", min_val="0",
                  col_class="col-sm-6 col-md-3"),
        FieldSpec("tolerance_temp", "Tolérance température (°C)", "float",
                  step="1", min_val="0", col_class="col-sm-6 col-md-3"),
        FieldSpec("duree_palier", "Durée de maintien (min)", "float",
                  required=True, step="1", min_val="0",
                  col_class="col-sm-6 col-md-3"),
        FieldSpec("vitesse_montee", "Vitesse de montée (°C/h)", "float",
                  step="1", col_class="col-sm-6 col-md-3"),
        FieldSpec("vitesse_descente", "Vitesse de descente (°C/h)", "float",
                  step="1", col_class="col-sm-6 col-md-3"),
        FieldSpec("thermocouples", "Thermocouples utilisés", "text",
                  maxlength=200, col_class="col-12 col-md-6"),
        FieldSpec("operateur", "Opérateur", "text",
                  maxlength=100, col_class="col-sm-6 col-md-3",
                  help_text="Phase 4 : sélection depuis le référentiel QC."),
        FieldSpec("ref_graphique", "Référence graphique d'enregistrement", "text",
                  maxlength=100, col_class="col-sm-6 col-md-4",
                  help_text="Phase 3 : lien vers le fichier importé."),
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


class TTH1Service(SimpleFormulaireService):
    CODE = "TTH1"
    CHAPITRE = Chapitre.C
    TITLE = "Procès-verbal de traitement thermique — opération 1"
    TITLE_EN = "Heat treatment record — operation 1"
    REQUIRED_FOR_VALIDATION = _REQUIRED
    SECTIONS = _SECTIONS


class TTH2Service(SimpleFormulaireService):
    CODE = "TTH2"
    CHAPITRE = Chapitre.C
    TITLE = "Procès-verbal de traitement thermique — opération 2"
    TITLE_EN = "Heat treatment record — operation 2"
    REQUIRED_FOR_VALIDATION = _REQUIRED
    SECTIONS = _SECTIONS
