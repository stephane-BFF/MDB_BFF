"""Service formulaire VISUFINAL — PV de contrôle visuel final.

Référence CDC v2 : §20 « PV visuel final ».
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService

_CONFORMITE = [
    ("", "— Sélectionner —"),
    ("conforme", "Conforme"),
    ("non_conforme", "Non conforme"),
]
_CONFORMITE_SO = [
    ("", "— Sélectionner —"),
    ("conforme", "Conforme"),
    ("non_conforme", "Non conforme"),
    ("sans_objet", "Sans objet"),
]


class VisuFinalService(SimpleFormulaireService):
    CODE = "VISUFINAL"
    CHAPITRE = Chapitre.F
    TITLE = "Procès-verbal de contrôle visuel final"
    TITLE_EN = "Final visual inspection report"
    REQUIRED_FOR_VALIDATION = frozenset({"date_controle_visuel", "etat_general", "etat_surface", "peinture"})
    SECTIONS = [
        SectionSpec("Identification", [
            FieldSpec("date_controle_visuel", "Date du contrôle", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("rev_plan", "Plan de référence (rév.)", "text",
                      maxlength=50, col_class="col-sm-6 col-md-3"),
            FieldSpec("procedure", "Réf. procédure VT", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("controleur", "Contrôleur", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text="Phase 4 : sélection depuis le référentiel QC."),
        ]),
        SectionSpec("Résultats", [
            FieldSpec("etat_general", "État général", "select",
                      options=_CONFORMITE, required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("etat_surface", "État de surface", "select",
                      options=_CONFORMITE, required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("peinture", "Traitement de surface / peinture", "select",
                      options=_CONFORMITE_SO, required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("marquage_plaque", "Plaque signalétique conforme (PS, TS, N° série)", "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("bouchons", "Bouchons de protection en place", "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("contenu_plaque", "Contenu plaque contrôlé", "text",
                      maxlength=200, col_class="col-12",
                      help_text="N° de série, PS, TS, année constructeur…"),
            FieldSpec("observations", "Observations", "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
            FieldSpec("non_conformites", "Non-conformités relevées", "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
