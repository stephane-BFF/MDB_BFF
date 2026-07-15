"""Service formulaire ETATDESC — État descriptif de l'équipement."""
from __future__ import annotations

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class EtatDescService(SimpleFormulaireService):
    CODE = "ETATDESC"
    CHAPITRE = Chapitre.A
    TITLE = "État descriptif de l'équipement"
    TITLE_EN = "Equipment descriptive record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_emission"})
    SECTIONS = [
        SectionSpec(_l("Caractéristiques principales"), [
            FieldSpec("date_emission", _l("Date d'émission"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("categorie_ped", _l("Catégorie PED"), "select",
                      options=[
                          ("", _l("— Sélectionner —")),
                          ("I", _l("I")),
                          ("II", _l("II")),
                          ("III", _l("III")),
                          ("IV", _l("IV")),
                      ],
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("pression_max_service_bar", _l("PS max (bar)"), "float",
                      step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("temperature_min_c", _l("T min (°C)"), "float",
                      step="0.5",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("temperature_max_c", _l("T max (°C)"), "float",
                      step="0.5",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("volume_litre", _l("Volume (L)"), "float",
                      step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
        ]),
        SectionSpec(_l("Description"), [
            FieldSpec("fluide_service", _l("Fluide de service"), "text",
                      maxlength=200, col_class="col-sm-6 col-md-6"),
            FieldSpec("materiaux_principaux", _l("Matériaux principaux"), "text",
                      maxlength=200, col_class="col-sm-6 col-md-6"),
            FieldSpec("description_generale", _l("Description générale"), "textarea",
                      maxlength=3000, rows=4, col_class="col-12"),
            FieldSpec("specifications_techniques", _l("Spécifications techniques"), "textarea",
                      maxlength=3000, rows=4, col_class="col-12"),
            FieldSpec("observations", _l("Observations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
