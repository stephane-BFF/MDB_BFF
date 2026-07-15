"""Service formulaire PEDMOD — Déclaration UE de conformité (modules A/D1/H/H1).

Référence CDC v2 : §27 « PED Module ».

Quatre modules PED applicables aux équipements BFF, quatre langues de sortie
(FR/EN/DE/IT). Le formulaire web utilise le gabarit générique ``_simple.html`` ;
le PDF utilise ``pdf/ped.html`` qui embarque les textes légaux multilingues
comme dict Jinja2.

Préremplissage : PS depuis Q5 du wizard, millésime PED 2014/68/UE et lieu
« Thonon-les-Bains » comme valeurs par défaut.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService

if TYPE_CHECKING:
    from app.models.affaire import Affaire


class PedModService(SimpleFormulaireService):
    """Déclaration UE de conformité — 4 modules × 4 langues."""

    CODE = "PEDMOD"
    CHAPITRE = Chapitre.G
    TITLE = "Déclaration UE de conformité (modules PED)"
    TITLE_EN = "EU Declaration of Conformity (PED modules)"
    REQUIRED_FOR_VALIDATION = frozenset(
        {"module_ped", "langue", "categorie_ped", "date_signature"}
    )

    SECTIONS = [
        SectionSpec(
            _l("Module et langue"),
            [
                FieldSpec(
                    "module_ped",
                    _l("Module PED"),
                    "select",
                    required=True,
                    col_class="col-sm-12 col-md-6",
                    options=[
                        ("", _l("— Sélectionner —")),
                        ("A", _l("Module A — Contrôle interne de la fabrication")),
                        ("D1", _l("Module D1 — Assurance de la qualité de la production")),
                        ("H", _l("Module H — Assurance complète de la qualité")),
                        ("H1", _l("Module H1 — Assurance complète + examen de conception")),
                    ],
                ),
                FieldSpec(
                    "langue",
                    _l("Langue du document"),
                    "select",
                    required=True,
                    col_class="col-sm-6 col-md-3",
                    options=[
                        ("", _l("— Sélectionner —")),
                        ("FR", _l("Français")),
                        ("EN", _l("English")),
                        ("DE", _l("Deutsch")),
                        ("IT", _l("Italiano")),
                    ],
                ),
                FieldSpec(
                    "categorie_ped",
                    _l("Catégorie PED"),
                    "select",
                    required=True,
                    col_class="col-sm-6 col-md-2",
                    options=[
                        ("", _l("— Sélectionner —")),
                        ("I", _l("I")),
                        ("II", _l("II")),
                        ("III", _l("III")),
                        ("IV", _l("IV")),
                    ],
                ),
                FieldSpec(
                    "groupe_fluide",
                    _l("Groupe de fluide"),
                    "select",
                    col_class="col-sm-6 col-md-1",
                    options=[
                        ("", _l("—")),
                        ("1", _l("1")),
                        ("2", _l("2")),
                    ],
                ),
            ],
        ),
        SectionSpec(
            _l("Organisme notifié (modules D1 / H / H1)"),
            [
                FieldSpec(
                    "on_nom",
                    _l("Nom de l'organisme notifié"),
                    "text",
                    maxlength=200,
                    col_class="col-sm-12 col-md-5",
                    help_text=_l("Laisser vide pour le module A."),
                ),
                FieldSpec(
                    "on_numero",
                    _l("N° d'identification ON"),
                    "text",
                    maxlength=10,
                    col_class="col-sm-6 col-md-2",
                    help_text=_l("Ex : 0082"),
                ),
                FieldSpec(
                    "on_certificat",
                    _l("Référence certificat ON"),
                    "text",
                    maxlength=100,
                    col_class="col-sm-12 col-md-5",
                    help_text=_l(
                        "Requis pour modules H et H1 (certificat d'examen de la conception)."
                    ),
                ),
            ],
        ),
        SectionSpec(
            _l("Caractéristiques de l'équipement"),
            [
                FieldSpec(
                    "ps",
                    _l("PS — Pression de service (bar)"),
                    "float",
                    step="0.1",
                    min_val="0",
                    col_class="col-sm-6 col-md-2",
                ),
                FieldSpec(
                    "ts_max",
                    _l("TS max (°C)"),
                    "float",
                    step="1",
                    col_class="col-sm-6 col-md-2",
                ),
                FieldSpec(
                    "ts_min",
                    _l("TS min (°C)"),
                    "float",
                    step="1",
                    col_class="col-sm-6 col-md-2",
                ),
                FieldSpec(
                    "volume",
                    _l("Volume (litres)"),
                    "float",
                    step="0.01",
                    min_val="0",
                    col_class="col-sm-6 col-md-2",
                ),
                FieldSpec(
                    "dn",
                    _l("DN"),
                    "text",
                    maxlength=20,
                    col_class="col-sm-6 col-md-2",
                ),
                FieldSpec(
                    "surface",
                    _l("Surface d'échange (m²)"),
                    "float",
                    step="0.01",
                    min_val="0",
                    col_class="col-sm-6 col-md-2",
                ),
            ],
        ),
        SectionSpec(
            _l("Signature"),
            [
                FieldSpec(
                    "millesime",
                    _l("Millésime directive"),
                    "text",
                    maxlength=20,
                    col_class="col-sm-6 col-md-3",
                ),
                FieldSpec(
                    "lieu_signature",
                    _l("Lieu de signature"),
                    "text",
                    maxlength=100,
                    col_class="col-sm-6 col-md-3",
                ),
                FieldSpec(
                    "date_signature",
                    _l("Date de signature"),
                    "date",
                    required=True,
                    col_class="col-sm-6 col-md-3",
                ),
                FieldSpec(
                    "signataire_nom",
                    _l("Nom du signataire"),
                    "text",
                    maxlength=100,
                    col_class="col-sm-6 col-md-4",
                ),
                FieldSpec(
                    "signataire_titre",
                    _l("Titre du signataire"),
                    "text",
                    maxlength=100,
                    col_class="col-sm-6 col-md-4",
                ),
            ],
        ),
    ]

    @classmethod
    def get_pdf_template(cls) -> str:
        """Template PDF dédié avec textes légaux multilingues."""
        return "pdf/ped.html"

    @classmethod
    def prefill_from_parametrage(cls, affaire: Affaire) -> dict[str, Any]:
        """Pré-remplit PS depuis Q5, millésime et lieu BFF par défaut."""
        prefill: dict[str, Any] = {
            "millesime": "2014/68/UE",
            "lieu_signature": "Thonon-les-Bains",
        }
        if affaire.parametrage and affaire.parametrage.reponses:
            ps_raw = affaire.parametrage.reponses.get("q5_ps_bar")
            if ps_raw is not None:
                try:
                    prefill["ps"] = float(ps_raw)
                except (TypeError, ValueError):
                    pass
        return prefill
