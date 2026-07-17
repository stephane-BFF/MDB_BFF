"""Service formulaire CONFCOM — Conformité commerciale."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService

if TYPE_CHECKING:
    from app.models.affaire import Affaire


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
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Auto-remplie depuis le registre BE (colonne "
                                   "« N° Commande ») — inclut l'indice de révision.")),
            FieldSpec("indice_revision", _l("Indice de révision"), "text",
                      maxlength=10, col_class="col-sm-6 col-md-2",
                      help_text=_l("À préciser uniquement si l'indice n'est pas "
                                   "déjà inclus dans la référence commande.")),
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

    @classmethod
    def prefill_from_parametrage(cls, affaire: Affaire) -> dict[str, Any]:
        """Pré-remplit la référence de commande client depuis le registre BE.

        La ``reference_commande`` (« VOS REFERENCES ») est issue du registre
        général de commande BE, matérialisée sur l'affaire à l'étape Q1/Q2 du
        wizard. L'indice de révision de la commande n'est pas encore capturé
        par le registre (à ajouter côté import BE — voir feuille de route).
        """
        prefill: dict[str, Any] = {}
        if affaire.references_client:
            prefill["reference_commande"] = affaire.references_client
        return prefill
