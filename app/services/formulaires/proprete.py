"""Service formulaire PROPRETE — PV de contrôle de propreté.

Référence CDC v2 : §24 « PV de propreté ».
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class PropreteService(SimpleFormulaireService):
    CODE = "PROPRETE"
    CHAPITRE = Chapitre.F
    TITLE = "Procès-verbal de contrôle de propreté"
    TITLE_EN = "Cleanliness inspection report"
    REQUIRED_FOR_VALIDATION = frozenset({"date_controle", "methode", "resultat"})
    SECTIONS = [
        SectionSpec(_l("Contrôle de propreté"), [
            FieldSpec("date_controle", _l("Date du contrôle"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("methode", _l("Méthode de vérification"), "select",
                      options=[
                          ("", _l("— Sélectionner —")),
                          ("visuelle", _l("Visuelle")),
                          ("chiffon_blanc", _l("Chiffon blanc")),
                          ("lampe_endoscope", _l("Lampe / endoscope")),
                          ("autre", _l("Autre")),
                      ],
                      required=True, col_class="col-sm-6 col-md-4"),
            FieldSpec("critere", _l("Critère d'acceptation"), "text",
                      maxlength=200, col_class="col-12 col-md-6",
                      help_text=_l("Ex : Absence de corps étrangers, pas de copeaux.")),
            FieldSpec("controleur", _l("Contrôleur"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text=_l("Phase 4 : sélection depuis le référentiel QC.")),
        ]),
        SectionSpec(_l("Résultat"), [
            FieldSpec("resultat", _l("Résultat"), "select",
                      options=[
                          ("", _l("— Sélectionner —")),
                          ("conforme", _l("Conforme")),
                          ("non_conforme", _l("Non conforme")),
                      ],
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("observations", _l("Observations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
