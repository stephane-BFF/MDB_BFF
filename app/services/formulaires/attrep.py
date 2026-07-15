"""Service formulaire ATTREP — Attestation du représentant habilité."""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AttRepService(SimpleFormulaireService):
    CODE = "ATTREP"
    CHAPITRE = Chapitre.A
    TITLE = "Attestation du représentant habilité"
    TITLE_EN = "Authorized representative declaration"
    REQUIRED_FOR_VALIDATION = frozenset({"date_emission", "nom_representant"})
    SECTIONS = [
        SectionSpec(_l("Représentant"), [
            FieldSpec("date_emission", _l("Date d'émission"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("nom_representant", _l("Nom du représentant"), "text",
                      required=True, maxlength=150, col_class="col-sm-6 col-md-4"),
            FieldSpec("qualite_representant", _l("Qualité / Fonction"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("organisme", _l("Organisme / Société"), "text",
                      maxlength=150, col_class="col-sm-6 col-md-4"),
        ]),
        SectionSpec(_l("Attestation"), [
            FieldSpec("habilitation_confirmee",
                      _l("Habilitation du représentant confirmée"), "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("observations", _l("Observations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
