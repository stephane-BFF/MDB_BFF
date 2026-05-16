"""Service formulaire ATTDECR — Attestation de conformité directive PED."""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AttDecrService(SimpleFormulaireService):
    CODE = "ATTDECR"
    CHAPITRE = Chapitre.A
    TITLE = "Attestation de conformité directive"
    TITLE_EN = "Directive conformity declaration"
    REQUIRED_FOR_VALIDATION = frozenset({"date_emission", "conformite_ped"})
    SECTIONS = [
        SectionSpec("Identification", [
            FieldSpec("date_emission", "Date d'émission", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("module_evaluation", "Module d'évaluation", "select",
                      options=[
                          ("", "— Sélectionner —"),
                          ("A", "Module A"),
                          ("A1", "Module A1"),
                          ("A2", "Module A2"),
                          ("B", "Module B"),
                          ("C2", "Module C2"),
                          ("D", "Module D"),
                          ("D1", "Module D1"),
                          ("E", "Module E"),
                          ("G", "Module G"),
                          ("H", "Module H"),
                          ("H1", "Module H1"),
                      ],
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("organisme_notifie", "Organisme notifié", "text",
                      maxlength=150, col_class="col-sm-6 col-md-4"),
            FieldSpec("numero_certificat", "N° certificat CE", "text",
                      maxlength=100, col_class="col-sm-6 col-md-3"),
            FieldSpec("date_certificat", "Date du certificat", "date",
                      col_class="col-sm-6 col-md-3"),
        ]),
        SectionSpec("Attestation", [
            FieldSpec("conformite_ped", "Équipement conforme à la directive PED 2014/68/UE",
                      "checkbox", required=True, col_class="col-12"),
            FieldSpec("observations", "Observations", "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
