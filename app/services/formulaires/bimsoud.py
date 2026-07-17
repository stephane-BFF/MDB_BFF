"""Service formulaire BIMSoud — Bordereau d'identification des matériaux de soudage.

Référence CDC v2 : §10 « Bordereau d'identification des matériaux de soudage ».
Tableau dynamique JS — chaque ligne décrit un consommable de soudage
(électrode, fil, flux) avec son diamètre, numéro de lot et utilisation.

V1.2 Lot 4 (demande n°9, arbitrage D4) : le **n° de lot est en première
colonne** — saisir un lot déjà rencontré remplit toute la ligne d'un coup,
depuis l'historique des BIMSOUD saisies (toutes affaires confondues, la
saisie la plus récente gagne). La colonne « Désignation » reste adossée au
référentiel ``MetalApport`` (norme + fournisseur auto).
"""
from __future__ import annotations

from typing import Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.extensions import db
from app.models.referentiel import MetalApport
from app.services.formulaires.base import ColSpec, TableFormulaireService, TableSpec

# Clés partagées entre les colonnes ``datalist`` et ``get_reference_options``.
_DATALIST_METAUX = "metaux_apport"
_DATALIST_LOTS = "lots_soudage"

# Colonnes remplies automatiquement à la sélection d'un n° de lot connu.
_LOT_AUTOFILL_COLS = ("designation", "norme", "diametre", "fournisseur", "ref_ccpu")


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
            ColSpec("num_lot", _l("N° lot"), "text",
                    required=True, maxlength=50, width="w-10",
                    datalist=_DATALIST_LOTS,
                    help_text=_l("Saisir un lot déjà connu remplit toute la "
                                 "ligne automatiquement.")),
            ColSpec("designation", _l("Désignation"), "text",
                    required=True, maxlength=150, width="w-20",
                    datalist=_DATALIST_METAUX,
                    help_text=_l("Choisir dans la liste : norme et fournisseur "
                                 "seront renseignés automatiquement.")),
            ColSpec("norme", _l("Norme"), "text",
                    required=True, maxlength=100, width="w-15"),
            ColSpec("diametre", _l("Diamètre (mm)"), "float",
                    required=True, step="0.1", min_val="0", width="w-10"),
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
        """Alimente les listes « N° lot » (historique) et « Désignation ».

        - ``lots_soudage`` : lots déjà saisis dans des BIMSOUD (toutes
          affaires) ; sélectionner un lot remplit désignation, norme,
          diamètre, fournisseur et réf. CCPU de la ligne.
        - ``metaux_apport`` : référentiel ``MetalApport`` ; sélectionner une
          désignation renseigne norme (classification AWS) et fournisseur.
        """
        metaux = (
            db.session.query(MetalApport)
            .filter_by(actif=True)
            .order_by(MetalApport.designation)
            .all()
        )
        autofill_metaux = {
            m.designation: {"norme": m.classification, "fournisseur": m.fournisseur or ""}
            for m in metaux
        }
        lots = cls._lots_connus()
        return {
            _DATALIST_LOTS: {
                "options": sorted(lots),
                "autofill": lots,
            },
            _DATALIST_METAUX: {
                "options": [m.designation for m in metaux],
                "autofill": autofill_metaux,
            },
        }

    @classmethod
    def _lots_connus(cls) -> dict[str, dict[str, Any]]:
        """Historique ``{n° lot: colonnes à remplir}`` des BIMSOUD saisies.

        Parcourt les formulaires BIMSOUD de toutes les affaires, du plus
        ancien au plus récent (la saisie la plus récente d'un même lot
        gagne). Arbitrage D4 : historique d'abord ; un référentiel de lots
        administrable pourra s'y ajouter plus tard si le besoin se confirme.
        """
        from app.models.formulaire import Formulaire  # noqa: PLC0415

        lots: dict[str, dict[str, Any]] = {}
        formulaires = (
            db.session.query(Formulaire)
            .filter_by(code=cls.CODE)
            .order_by(Formulaire.updated_at)
            .all()
        )
        for formulaire in formulaires:
            for ligne in (formulaire.data or {}).get("lignes", []):
                lot = str(ligne.get("num_lot") or "").strip()
                if not lot:
                    continue
                lots[lot] = {
                    col: ligne.get(col) if ligne.get(col) is not None else ""
                    for col in _LOT_AUTOFILL_COLS
                }
        return lots
