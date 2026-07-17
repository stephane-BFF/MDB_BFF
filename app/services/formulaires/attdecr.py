"""Service formulaire ATTDECR — Attestation de conformité directive PED.

Le module d'évaluation est **imposé** par la catégorie PED saisie en Q4 du
wizard (données d'entrée) : il est pré-rempli et ré-appliqué côté serveur à
chaque enregistrement. L'organisme notifié se choisit dans le référentiel
NANDO (``OrganismeNotifie``) — sa sélection renseigne le numéro d'ON. Le n° de
certificat CE n'est visible que si le module requiert un organisme notifié
(tous les modules sauf le module A, auto-certification).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.extensions import db
from app.forms.wizard import MODULES_PED
from app.models.referentiel import OrganismeNotifie
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.formulaire import Formulaire
    from app.models.user import User

# Clé du datalist des organismes notifiés.
_DATALIST_ON = "organismes_notifies"

# Le module A (auto-certification, catégorie I) ne requiert pas d'organisme
# notifié : le n° de certificat CE et l'ON sont alors sans objet.
_MODULES_SANS_ON = ("", "A")

# Condition d'affichage des champs liés à l'organisme notifié.
_VISIBLE_SI_ON_REQUIS = {"field": "module_evaluation", "not_in": list(_MODULES_SANS_ON)}


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
                      options=[("", _l("— Sélectionner —"))]
                      + [(code, label) for code, label in MODULES_PED.items()],
                      col_class="col-sm-6 col-md-5",
                      help_text=_l("Imposé par la catégorie PED (Q4) — "
                                   "réappliqué automatiquement à l'enregistrement.")),
        ]),
        SectionSpec(_l("Organisme notifié (modules autres que A)"), [
            FieldSpec("organisme_notifie", _l("Organisme notifié"), "text",
                      maxlength=255, col_class="col-sm-8 col-md-6",
                      datalist=_DATALIST_ON,
                      visible_when=_VISIBLE_SI_ON_REQUIS,
                      help_text=_l("Choisir dans la liste NANDO : le n° d'ON "
                                   "est renseigné automatiquement.")),
            FieldSpec("numero_on", _l("N° d'organisme notifié"), "text",
                      maxlength=10, col_class="col-sm-4 col-md-2",
                      visible_when=_VISIBLE_SI_ON_REQUIS,
                      help_text=_l("N° NANDO à 4 chiffres (ex: 0062).")),
            FieldSpec("numero_certificat", _l("N° certificat CE"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      visible_when=_VISIBLE_SI_ON_REQUIS),
            FieldSpec("date_certificat", _l("Date du certificat"), "date",
                      col_class="col-sm-6 col-md-3",
                      visible_when=_VISIBLE_SI_ON_REQUIS),
        ]),
        SectionSpec(_l("Attestation"), [
            FieldSpec("conformite_ped", _l("Équipement conforme à la directive PED 2014/68/UE"),
                      "checkbox", required=True, col_class="col-12"),
            FieldSpec("observations", _l("Observations"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]

    @classmethod
    def _module_from_q4(cls, affaire: Affaire) -> str | None:
        """Module d'évaluation issu de la catégorie PED (Q4), ou None."""
        if affaire.parametrage and affaire.parametrage.reponses:
            module = affaire.parametrage.reponses.get("q4_module_ped")
            if module in MODULES_PED:
                return str(module)
        return None

    @classmethod
    def prefill_from_parametrage(cls, affaire: Affaire) -> dict[str, Any]:
        """Pré-remplit le module d'évaluation imposé depuis Q4."""
        prefill: dict[str, Any] = {}
        module = cls._module_from_q4(affaire)
        if module:
            prefill["module_evaluation"] = module
        return prefill

    @classmethod
    def save_brouillon(
        cls, affaire: Affaire, payload: dict[str, Any], user: User
    ) -> Formulaire:
        """Impose le module d'évaluation depuis Q4 avant l'enregistrement."""
        module = cls._module_from_q4(affaire)
        if module:
            payload = {**payload, "module_evaluation": module}
        return super().save_brouillon(affaire, payload, user)

    @classmethod
    def get_reference_options(cls) -> dict[str, Any]:
        """Alimente la liste déroulante « Organisme notifié » depuis NANDO.

        Sélectionner un ON renseigne automatiquement son numéro (``numero_on``).
        """
        organismes = (
            db.session.query(OrganismeNotifie)
            .filter_by(actif=True)
            .order_by(OrganismeNotifie.numero)
            .all()
        )
        return {
            _DATALIST_ON: {
                "options": [f"{o.numero} — {o.nom}" for o in organismes],
                "autofill": {
                    f"{o.numero} — {o.nom}": {"numero_on": o.numero}
                    for o in organismes
                },
            }
        }
