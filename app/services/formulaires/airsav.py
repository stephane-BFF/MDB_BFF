"""Service formulaire AIRSAV — PV de test air-savon.

Référence CDC v2 : §19 « Test air-savon ».
Déclencheur : dudgeonnage présent ou requis par client/code.
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AirSavService(SimpleFormulaireService):
    CODE = "AIRSAV"
    CHAPITRE = Chapitre.E
    TITLE = "Procès-verbal de test air-savon"
    TITLE_EN = "Soap bubble leak test report"
    REQUIRED_FOR_VALIDATION = frozenset({"date_airsav", "pression_test", "duree", "resultat"})
    SECTIONS = [
        SectionSpec(_l("Test air-savon"), [
            FieldSpec("date_airsav", _l("Date du test"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("pression_test", _l("Pression de test (bar)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("duree", _l("Durée de maintien (min)"), "float",
                      required=True, step="1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("manometre", _l("Manomètre utilisé"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Phase 4 : sélection depuis le référentiel métrologie.")),
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
                          ("pas_de_fuite", _l("Pas de fuite")),
                          ("fuite_detectee", _l("Fuite détectée")),
                      ],
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("fuites_detectees", _l("Description des fuites"), "textarea",
                      maxlength=1000, rows=2, col_class="col-12",
                      help_text=_l("Si applicable.")),
            FieldSpec("actions", _l("Actions correctives"), "textarea",
                      maxlength=1000, rows=2, col_class="col-12",
                      help_text=_l("Si applicable.")),
        ]),
    ]
