"""Service formulaire CONFCOM — Conformité commerciale."""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class ConfComService(SimpleFormulaireService):
    CODE = "CONFCOM"
    CHAPITRE = Chapitre.A
    TITLE = "Conformité commerciale"
    TITLE_EN = "Commercial conformity"
    REQUIRED_FOR_VALIDATION = frozenset({"date_emission"})
    SECTIONS = [
        SectionSpec(_l("Référence commande"), [
            FieldSpec("date_emission", _l("Date d'émission"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("reference_commande", _l("Référence commande client"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("indice_revision", _l("Indice de révision"), "text",
                      maxlength=10, col_class="col-sm-6 col-md-2"),
        ]),
        SectionSpec(_l("Conformité"), [
            FieldSpec("conforme_specification",
                      _l("Conforme aux spécifications techniques"), "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("conforme_delais", _l("Conforme aux délais contractuels"), "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("conforme_documents", _l("Documents fournis conformes"), "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("ecarts", _l("Écarts / dérogations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
            FieldSpec("observations", _l("Observations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
