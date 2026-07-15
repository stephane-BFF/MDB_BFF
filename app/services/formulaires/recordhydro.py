"""Service formulaire RECORDHYDRO — Enregistrement continu du test hydrostatique.

Référence CDC v2 : §23 « Enregistrement continu — test hydrostatique ».
Ce formulaire complète HYDR en enregistrant la courbe pression/temps.
Upload de la courbe numérique (Phase 3).
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class RecordHydroService(SimpleFormulaireService):
    CODE = "RECORDHYDRO"
    CHAPITRE = Chapitre.E
    TITLE = "Enregistrement continu — épreuve hydrostatique"
    TITLE_EN = "Hydrostatic test continuous record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_enregistrement", "echelle_pression", "echelle_temps", "pression_stabilisee"})
    SECTIONS = [
        SectionSpec(_l("Paramètres d'enregistrement"), [
            FieldSpec("date_enregistrement", _l("Date d'enregistrement"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("ref_hydr", _l("Référence PV HYDR associé"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Lien vers le formulaire HYDR correspondant.")),
            FieldSpec("appareil_enregistrement", _l("Appareil d'enregistrement"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Phase 4 : sélection depuis le référentiel métrologie.")),
            FieldSpec("echelle_pression", _l("Échelle pression (bar)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("echelle_temps", _l("Échelle temps (min)"), "float",
                      required=True, step="1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
        ]),
        SectionSpec(_l("Résultats"), [
            FieldSpec("pression_stabilisee", _l("Pression stabilisée (bar)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("chute_pression", _l("Chute de pression observée (bar)"), "float",
                      step="0.01", col_class="col-sm-6 col-md-3",
                      help_text=_l("Sur la durée totale du maintien.")),
            FieldSpec("ref_courbe", _l("Référence fichier courbe"), "text",
                      maxlength=200, col_class="col-sm-6 col-md-6",
                      help_text=_l("Phase 3 : upload du scan ou export numérique.")),
            FieldSpec("commentaires", _l("Commentaires"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
