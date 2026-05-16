"""Services formulaires UT0 — Mesures d'épaisseur initiale par ultrasons.

Référence CDC v2 : §15 « Mesures d'épaisseur initiale (Point 0) ».
Quatre zones d'un échangeur de chaleur, structure identique :
en-tête fixe (appareil, épaisseur mini) + tableau dynamique avec
calcul automatique de la moyenne et de la conformité.

    mesure_moy = round((mesure_1 + mesure_2) / 2, 3)
    conformite = mesure_moy ≥ ep_mini_acceptable

Codes : UT0FAIS (faisceau), UT0SHELL (calandre), UT0RET (retour), UT0UBEND (U-coudes).
"""
from __future__ import annotations

from typing import Any

from app.enums import Chapitre
from app.services.formulaires.base import (
    ColSpec,
    FieldSpec,
    SectionSpec,
    TableFormulaireService,
    TableSpec,
)

_REQUIRED_HDR = frozenset({"ep_mini_acceptable", "date_mesure"})

_HEADER_SECTIONS = [
    SectionSpec("Paramètres du contrôle", [
        FieldSpec("date_mesure", "Date de mesure", "date",
                  required=True, col_class="col-sm-6 col-md-3"),
        FieldSpec("appareil_mesure", "Appareil de mesure UT", "text",
                  maxlength=100, col_class="col-sm-6 col-md-4",
                  help_text="Phase 4 : sélection depuis le référentiel métrologie."),
        FieldSpec("sonde", "Type de sonde", "text",
                  maxlength=100, col_class="col-sm-6 col-md-3"),
        FieldSpec("couplant", "Couplant utilisé", "text",
                  maxlength=100, col_class="col-sm-6 col-md-3"),
        FieldSpec("ep_mini_acceptable", "Ép. mini acceptable (mm)", "float",
                  required=True, step="0.001", min_val="0",
                  col_class="col-sm-6 col-md-3"),
        FieldSpec("operateur", "Opérateur", "text",
                  maxlength=100, col_class="col-sm-6 col-md-3",
                  help_text="Phase 4 : sélection depuis le référentiel QC."),
    ]),
]

_TABLE_SPEC = TableSpec(
    title="Mesures par tube",
    cols=[
        ColSpec("num_tube", "N° tube", "text",
                required=True, maxlength=20, width="w-10"),
        ColSpec("mesure_1", "Mesure 1 (mm)", "float",
                required=True, step="0.001", min_val="0", width="w-12"),
        ColSpec("mesure_2", "Mesure 2 (mm)", "float",
                required=True, step="0.001", min_val="0", width="w-12"),
        ColSpec("mesure_moy", "Moyenne (mm)", "float",
                server_computed=True, step="0.001", width="w-10"),
        ColSpec("conformite", "Conforme", "checkbox",
                server_computed=True, width="w-8"),
    ],
)


class _UT0Base(TableFormulaireService):
    """Classe de base partagée par les quatre variantes UT0."""

    REQUIRED_HEADER = _REQUIRED_HDR
    HEADER_SECTIONS = _HEADER_SECTIONS
    TABLE_SPEC = _TABLE_SPEC
    REQUIRED_LIGNES = 1

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        data = super()._sanitize_payload(raw)
        header = data.get("header", {})
        ep_mini = header.get("ep_mini_acceptable")

        for ligne in data.get("lignes", []):
            m1 = ligne.get("mesure_1")
            m2 = ligne.get("mesure_2")
            if isinstance(m1, (int, float)) and isinstance(m2, (int, float)):
                moy = round((m1 + m2) / 2, 3)
                ligne["mesure_moy"] = moy
                if isinstance(ep_mini, (int, float)):
                    ligne["conformite"] = bool(moy >= ep_mini)

        return data


class UT0FaisService(_UT0Base):
    CODE = "UT0FAIS"
    CHAPITRE = Chapitre.D
    TITLE = "Mesures d'épaisseur initiale — Zone faisceau"
    TITLE_EN = "Initial thickness measurements — Tube bundle zone"


class UT0ShellService(_UT0Base):
    CODE = "UT0SHELL"
    CHAPITRE = Chapitre.D
    TITLE = "Mesures d'épaisseur initiale — Zone calandre"
    TITLE_EN = "Initial thickness measurements — Shell zone"


class UT0RetService(_UT0Base):
    CODE = "UT0RET"
    CHAPITRE = Chapitre.D
    TITLE = "Mesures d'épaisseur initiale — Zone retour"
    TITLE_EN = "Initial thickness measurements — Return zone"


class UT0UbendService(_UT0Base):
    CODE = "UT0UBEND"
    CHAPITRE = Chapitre.D
    TITLE = "Mesures d'épaisseur initiale — Zone U-coudes"
    TITLE_EN = "Initial thickness measurements — U-bend zone"
