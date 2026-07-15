"""Service formulaire VISUFINAL — PV de contrôle visuel final.

Référence CDC v2 : §20 « PV visuel final ».
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService

_CONFORMITE = [
    ("", _l("— Sélectionner —")),
    ("conforme", _l("Conforme")),
    ("non_conforme", _l("Non conforme")),
]
_CONFORMITE_SO = [
    ("", _l("— Sélectionner —")),
    ("conforme", _l("Conforme")),
    ("non_conforme", _l("Non conforme")),
    ("sans_objet", _l("Sans objet")),
]


class VisuFinalService(SimpleFormulaireService):
    CODE = "VISUFINAL"
    CHAPITRE = Chapitre.F
    TITLE = "Procès-verbal de contrôle visuel final"
    TITLE_EN = "Final visual inspection report"
    REQUIRED_FOR_VALIDATION = frozenset({"date_controle_visuel", "etat_general", "etat_surface", "peinture"})
    SECTIONS = [
        SectionSpec(_l("Identification"), [
            FieldSpec("date_controle_visuel", _l("Date du contrôle"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("rev_plan", _l("Plan de référence (rév.)"), "text",
                      maxlength=50, col_class="col-sm-6 col-md-3"),
            FieldSpec("procedure", _l("Réf. procédure VT"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("controleur", _l("Contrôleur"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text=_l("Phase 4 : sélection depuis le référentiel QC.")),
        ]),
        SectionSpec(_l("Résultats"), [
            FieldSpec("etat_general", _l("État général"), "select",
                      options=_CONFORMITE, required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("etat_surface", _l("État de surface"), "select",
                      options=_CONFORMITE, required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("peinture", _l("Traitement de surface / peinture"), "select",
                      options=_CONFORMITE_SO, required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("marquage_plaque",
                      _l("Plaque signalétique conforme (PS, TS, N° série)"),
                      "checkbox", col_class="col-12 col-md-6"),
            FieldSpec("bouchons", _l("Bouchons de protection en place"), "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("contenu_plaque", _l("Contenu plaque contrôlé"), "text",
                      maxlength=200, col_class="col-12",
                      help_text=_l("N° de série, PS, TS, année constructeur…")),
            FieldSpec("observations", _l("Observations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
            FieldSpec("non_conformites", _l("Non-conformités relevées"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
