"""Service formulaire AZOTE — PV de mise sous azote.

Référence CDC v2 : §25 « PV de mise sous azote ».
Déclencheur : requis par le client ou le code de construction.
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AzoteService(SimpleFormulaireService):
    CODE = "AZOTE"
    CHAPITRE = Chapitre.E
    TITLE = "Procès-verbal de mise sous azote"
    TITLE_EN = "Nitrogen pressurization record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_azote", "pression_azote", "pression_verifiee", "resultat"})
    SECTIONS = [
        SectionSpec(_l("Mise sous azote"), [
            FieldSpec("date_azote", _l("Date de l'opération"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("pression_azote", _l("Pression d'azote (bar g)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("manometre", _l("Manomètre"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Phase 4 : sélection depuis le référentiel métrologie.")),
            FieldSpec("pression_verifiee",
                      _l("Pression vérifiée en fin d'opération (bar g)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("operateur", _l("Opérateur"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text=_l("Phase 4 : sélection depuis le référentiel QC.")),
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
            FieldSpec("remarques", _l("Remarques"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
