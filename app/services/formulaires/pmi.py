"""Service formulaire PMI — Positive Material Identification.

Référence CDC v2 : §§21–22 « Rapport de contrôle PMI ».
En-tête fixe (date, procédure, appareil) + tableau dynamique JS
(une ligne par composant analysé avec son grade attendu et résultat).
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import (
    ColSpec,
    FieldSpec,
    SectionSpec,
    TableFormulaireService,
    TableSpec,
)


class PmiService(TableFormulaireService):
    CODE = "PMI"
    CHAPITRE = Chapitre.B
    TITLE = "Rapport de contrôle par identification positive des matériaux (PMI)"
    TITLE_EN = "Positive material identification (PMI) inspection report"
    REQUIRED_LIGNES = 1
    REQUIRED_HEADER = frozenset({"date_pmi", "procedure"})
    HEADER_SECTIONS = [
        SectionSpec("En-tête", [
            FieldSpec("date_pmi", "Date du contrôle PMI", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("procedure", "Référence procédure PMI", "text",
                      required=True, maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("appareil_pmi", "Appareil PMI utilisé", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3"),
            FieldSpec("operateur", "Opérateur", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text="Phase 4 : sélection depuis le référentiel QC."),
        ]),
    ]
    TABLE_SPEC = TableSpec(
        title="Résultats PMI par composant",
        cols=[
            ColSpec("composant", "Composant / repère", "text",
                    required=True, maxlength=100, width="w-20"),
            ColSpec("grade_attendu", "Grade attendu", "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("resultats", "Résultats mesurés", "text",
                    maxlength=200, width="w-20"),
            ColSpec("conformite", "Conformité", "select",
                    options=[
                        ("", "—"),
                        ("conforme", "Conforme"),
                        ("non_conforme", "Non conforme"),
                    ],
                    width="w-15"),
            ColSpec("remarques", "Remarques", "text",
                    maxlength=200, width="w-auto"),
        ],
    )
