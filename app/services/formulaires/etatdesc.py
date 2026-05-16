"""Service formulaire ETATDESC — État descriptif de l'équipement."""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class EtatDescService(SimpleFormulaireService):
    CODE = "ETATDESC"
    CHAPITRE = Chapitre.A
    TITLE = "État descriptif de l'équipement"
    TITLE_EN = "Equipment descriptive record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_emission"})
    SECTIONS = [
        SectionSpec("Caractéristiques principales", [
            FieldSpec("date_emission", "Date d'émission", "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("categorie_ped", "Catégorie PED", "select",
                      options=[
                          ("", "— Sélectionner —"),
                          ("I", "I"),
                          ("II", "II"),
                          ("III", "III"),
                          ("IV", "IV"),
                      ],
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("pression_max_service_bar", "PS max (bar)", "float",
                      step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("temperature_min_c", "T min (°C)", "float",
                      step="0.5",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("temperature_max_c", "T max (°C)", "float",
                      step="0.5",
                      col_class="col-sm-6 col-md-2"),
            FieldSpec("volume_litre", "Volume (L)", "float",
                      step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-2"),
        ]),
        SectionSpec("Description", [
            FieldSpec("fluide_service", "Fluide de service", "text",
                      maxlength=200, col_class="col-sm-6 col-md-6"),
            FieldSpec("materiaux_principaux", "Matériaux principaux", "text",
                      maxlength=200, col_class="col-sm-6 col-md-6"),
            FieldSpec("description_generale", "Description générale", "textarea",
                      maxlength=3000, rows=4, col_class="col-12"),
            FieldSpec("specifications_techniques", "Spécifications techniques", "textarea",
                      maxlength=3000, rows=4, col_class="col-12"),
            FieldSpec("observations", "Observations", "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]
