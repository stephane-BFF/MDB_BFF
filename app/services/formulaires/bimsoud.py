"""Service formulaire BIMSoud — Bordereau d'identification des matériaux de soudage.

Référence CDC v2 : §10 « Bordereau d'identification des matériaux de soudage ».
Tableau dynamique JS — chaque ligne décrit un consommable de soudage
(électrode, fil, flux) avec son diamètre, numéro de lot et utilisation.

La colonne « Désignation » est adossée au référentiel ``MetalApport`` : la
sélection d'une désignation renseigne automatiquement la norme (classification
AWS) et le fournisseur.
"""
from __future__ import annotations

from typing import Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.extensions import db
from app.models.referentiel import MetalApport
from app.services.formulaires.base import ColSpec, TableFormulaireService, TableSpec

# Clé partagée entre la colonne ``datalist`` et ``get_reference_options``.
_DATALIST_METAUX = "metaux_apport"


class BimSoudService(TableFormulaireService):
    CODE = "BIMSOUD"
    CHAPITRE = Chapitre.B
    TITLE = "Bordereau d'identification des matériaux de soudage"
    TITLE_EN = "Bill of material — welding consumables"
    REQUIRED_LIGNES = 1
    HEADER_SECTIONS = []
    TABLE_SPEC = TableSpec(
        title=_l("Matériaux de soudage"),
        cols=[
            ColSpec("designation", _l("Désignation"), "text",
                    required=True, maxlength=150, width="w-20",
                    datalist=_DATALIST_METAUX,
                    help_text=_l("Choisir dans la liste : norme et fournisseur "
                                 "seront renseignés automatiquement.")),
            ColSpec("norme", _l("Norme"), "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("diametre", _l("Diamètre (mm)"), "float",
                    required=True, step="0.1", min_val="0", width="w-10"),
            ColSpec("num_lot", _l("N° lot"), "text",
                    required=True, maxlength=50, width="w-10"),
            ColSpec("fournisseur", _l("Fournisseur"), "text",
                    maxlength=100, width="w-15"),
            ColSpec("utilisation", _l("Utilisation"), "text",
                    maxlength=150, width="w-15",
                    help_text=_l("Ex : assemblage, rechargement, reprise…")),
            ColSpec("ref_ccpu", _l("Réf. CCPU"), "text",
                    maxlength=50, width="w-auto"),
        ],
    )

    @classmethod
    def get_reference_options(cls) -> dict[str, Any]:
        """Alimente la liste déroulante « Désignation » depuis ``MetalApport``.

        Sélectionner une désignation renseigne automatiquement les colonnes
        ``norme`` (classification AWS) et ``fournisseur``.
        """
        metaux = (
            db.session.query(MetalApport)
            .filter_by(actif=True)
            .order_by(MetalApport.designation)
            .all()
        )
        autofill = {
            m.designation: {"norme": m.classification, "fournisseur": m.fournisseur or ""}
            for m in metaux
        }
        return {
            _DATALIST_METAUX: {
                "options": [m.designation for m in metaux],
                "autofill": autofill,
            }
        }
