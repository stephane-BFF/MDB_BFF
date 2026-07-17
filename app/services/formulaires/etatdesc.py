"""Service formulaire ETATDESC — État descriptif de l'équipement."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService

if TYPE_CHECKING:
    from app.models.affaire import Affaire


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

    # Catégories PED reconnues par le select de ce formulaire (I–IV).
    _CATEGORIES_SELECT = frozenset({"I", "II", "III", "IV"})
    _FLUIDE_ETAT_LABELS = {"gaz": "Gaz", "liquide": "Liquide"}
    _FLUIDE_GROUPE_LABELS = {"1": "Groupe 1 (dangereux)", "2": "Groupe 2 (non dangereux)"}

    @classmethod
    def prefill_from_parametrage(cls, affaire: Affaire) -> dict[str, Any]:
        """Pré-remplit les caractéristiques techniques depuis le wizard Q4/Q5.

        Reprend la catégorie PED, les conditions de service (PS, températures,
        volume) et le fluide saisis à la création de l'affaire, pour éviter
        toute ressaisie.
        """
        prefill: dict[str, Any] = {}
        reponses = (affaire.parametrage.reponses if affaire.parametrage else None) or {}

        categorie = reponses.get("q4_categorie_ped")
        if categorie in cls._CATEGORIES_SELECT:
            prefill["categorie_ped"] = categorie

        _map = {
            "pression_max_service_bar": "q5_ps_bar",
            "temperature_min_c": "q5_temperature_min_c",
            "temperature_max_c": "q5_temperature_max_c",
            "volume_litre": "q5_volume_l",
        }
        for champ, cle in _map.items():
            valeur = reponses.get(cle)
            if valeur is not None:
                prefill[champ] = valeur

        # Fluide de service : nom + état + dangerosité en une phrase lisible.
        fluide_parts = []
        if reponses.get("q4_fluide_nom"):
            fluide_parts.append(str(reponses["q4_fluide_nom"]))
        etat = cls._FLUIDE_ETAT_LABELS.get(reponses.get("q4_fluide_etat", ""))
        if etat:
            fluide_parts.append(etat)
        groupe = cls._FLUIDE_GROUPE_LABELS.get(str(reponses.get("q4_fluide_groupe", "")))
        if groupe:
            fluide_parts.append(groupe)
        if fluide_parts:
            prefill["fluide_service"] = " — ".join(fluide_parts)

        return prefill
