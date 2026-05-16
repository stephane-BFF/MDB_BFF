"""Service formulaire ATTREP — Attestation du représentant habilité."""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AttRepService(SimpleFormulaireService):
    CODE = "ATTREP"
    CHAPITRE = Chapitre.A
    TITLE = "Attestation du représentant habilité"
    TITLE_EN = "Authorized representative declaration"
    REQUIRED_FOR_VALIDATION = frozenset({"date_emission", "nom_representant"})
    SECTIONS = [
        SectionSpec("Représentant", [
            FieldSpec("date_emission", "Date d'émission", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("nom_representant", "Nom du représentant", "text",
                      required=True, maxlength=150, col_class="col-sm-6 col-md-4"),
            FieldSpec("qualite_representant", "Qualité / Fonction", "text",
                      maxlength=100, col_class="col-sm-6 col-md-4"),
            FieldSpec("organisme", "Organisme / Société", "text",
                      maxlength=150, col_class="col-sm-6 col-md-4"),
        ]),
        SectionSpec("Attestation", [
            FieldSpec("habilitation_confirmee",
                      "Habilitation du représentant confirmée", "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("observations", "Observations", "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
