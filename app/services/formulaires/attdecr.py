"""Service formulaire ATTDECR — Attestation de conformité directive PED."""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class AttDecrService(SimpleFormulaireService):
    CODE = "ATTDECR"
    CHAPITRE = Chapitre.A
    TITLE = "Attestation de conformité directive"
    TITLE_EN = "Directive conformity declaration"
    REQUIRED_FOR_VALIDATION = frozenset({"date_emission", "conformite_ped"})
    SECTIONS = [
        SectionSpec(_l("Identification"), [
            FieldSpec("date_emission", _l("Date d'émission"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("module_evaluation", _l("Module d'évaluation"), "select",
                      options=[
                          ("", _l("— Sélectionner —")),
                          ("A", _l("Module A")),
                          ("A1", _l("Module A1")),
                          ("A2", _l("Module A2")),
                          ("B", _l("Module B")),
                          ("C2", _l("Module C2")),
                          ("D", _l("Module D")),
                          ("D1", _l("Module D1")),
                          ("E", _l("Module E")),
                          ("G", _l("Module G")),
                          ("H", _l("Module H")),
                          ("H1", _l("Module H1")),
                      ],
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("organisme_notifie", _l("Organisme notifié"), "text",
                      maxlength=150, col_class="col-sm-6 col-md-4"),
            FieldSpec("numero_certificat", _l("N° certificat CE"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3"),
            FieldSpec("date_certificat", _l("Date du certificat"), "date",
                      col_class="col-sm-6 col-md-3"),
        ]),
        SectionSpec(_l("Attestation"), [
            FieldSpec("conformite_ped", _l("Équipement conforme à la directive PED 2014/68/UE"),
                      "checkbox", required=True, col_class="col-12"),
            FieldSpec("observations", _l("Observations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
