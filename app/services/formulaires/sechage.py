"""Service formulaire SECHAGE — PV de séchage après épreuve hydraulique.

Référence CDC v2 : §26 « PV de séchage ».
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class SechageService(SimpleFormulaireService):
    CODE = "SECHAGE"
    CHAPITRE = Chapitre.F
    TITLE = "Procès-verbal de séchage"
    TITLE_EN = "Drying record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_sechage", "methode", "resultat", "point_rosee_mesure"})
    SECTIONS = [
        SectionSpec(_l("Paramètres de séchage"), [
            FieldSpec("date_sechage", _l("Date de séchage"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("methode", _l("Méthode de séchage"), "select",
                      options=[
                          ("", _l("— Sélectionner —")),
                          ("air_sec", _l("Air comprimé sec")),
                          ("ventilation", _l("Ventilation forcée")),
                          ("etuve", _l("Étuve")),
                      ],
                      required=True, col_class="col-sm-6 col-md-4"),
            FieldSpec("critere_sechage", _l("Critère de point de rosée"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Ex : Point de rosée ≤ −30 °C.")),
            FieldSpec("appareil_mesure", _l("Appareil de mesure"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Phase 4 : sélection depuis le référentiel métrologie.")),
            FieldSpec("operateur", _l("Opérateur"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text=_l("Phase 4 : sélection depuis le référentiel QC.")),
        ]),
        SectionSpec(_l("Mesures et résultat"), [
            FieldSpec("point_rosee_mesure", _l("Point de rosée mesuré (°C)"), "float",
                      required=True, step="0.1", col_class="col-sm-6 col-md-3"),
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
