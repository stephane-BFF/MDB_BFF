"""Service formulaire SECHAGE — PV de séchage après épreuve hydraulique.

Référence CDC v2 : §26 « PV de séchage ».
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class SechageService(SimpleFormulaireService):
    CODE = "SECHAGE"
    CHAPITRE = Chapitre.F
    TITLE = "Procès-verbal de séchage"
    TITLE_EN = "Drying record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_sechage", "methode", "resultat", "point_rosee_mesure"})
    SECTIONS = [
        SectionSpec("Paramètres de séchage", [
            FieldSpec("date_sechage", "Date de séchage", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("methode", "Méthode de séchage", "select",
                      options=[
                          ("", "— Sélectionner —"),
                          ("air_sec", "Air comprimé sec"),
                          ("ventilation", "Ventilation forcée"),
                          ("etuve", "Étuve"),
                      ],
                      required=True, col_class="col-sm-6 col-md-4"),
            FieldSpec("critere_sechage", "Critère de point de rosée", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text="Ex : Point de rosée ≤ −30 °C."),
            FieldSpec("appareil_mesure", "Appareil de mesure", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text="Phase 4 : sélection depuis le référentiel métrologie."),
            FieldSpec("operateur", "Opérateur", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text="Phase 4 : sélection depuis le référentiel QC."),
        ]),
        SectionSpec("Mesures et résultat", [
            FieldSpec("point_rosee_mesure", "Point de rosée mesuré (°C)", "float",
                      required=True, step="0.1", col_class="col-sm-6 col-md-3"),
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
