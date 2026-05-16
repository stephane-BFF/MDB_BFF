"""Service formulaire NDEMAP — Carte des contrôles non destructifs.

Référence CDC v2 : §12 « Carte des contrôles non destructifs (CND) ».
Tableau dynamique JS — une ligne par joint soudé contrôlé.
Logique conditionnelle RT/PT (champs conditionnels selon méthodes requises)
déférée à la Phase 4 — tous les champs sont présents en Phase 2.
"""
from __future__ import annotations

from app.enums import Chapitre
from app.services.formulaires.base import ColSpec, TableFormulaireService, TableSpec


class NdeMapService(TableFormulaireService):
    CODE = "NDEMAP"
    CHAPITRE = Chapitre.D
    TITLE = "Carte des contrôles non destructifs"
    TITLE_EN = "Non-destructive testing map"
    REQUIRED_LIGNES = 1
    HEADER_SECTIONS = []
    TABLE_SPEC = TableSpec(
        title="Joints soudés — résultats CND",
        cols=[
            ColSpec("num_joint", "N° joint", "text",
                    required=True, maxlength=20, width="w-8"),
            ColSpec("description", "Description du joint", "text",
                    required=True, maxlength=150, width="w-15"),
            ColSpec("procede", "Procédé soudage", "text",
                    maxlength=50, width="w-8"),
            ColSpec("soudeur", "ID soudeur", "text",
                    maxlength=20, width="w-8",
                    help_text="Phase 4 : sélection depuis ListSoud."),
            ColSpec("rt_requis", "RT requis", "checkbox", width="w-6"),
            ColSpec("rt_realise", "RT réalisé (%)", "float",
                    step="1", min_val="0", max_val="100", width="w-8"),
            ColSpec("rt_rapport", "N° rapport RT", "text",
                    maxlength=50, width="w-10"),
            ColSpec("rt_resultat", "Résultat RT", "select",
                    options=[
                        ("", "—"),
                        ("acceptable", "Acceptable"),
                        ("non_acceptable", "Non acceptable"),
                    ],
                    width="w-10"),
            ColSpec("pt_requis", "PT requis", "checkbox", width="w-6"),
            ColSpec("pt_realise", "PT réalisé", "checkbox", width="w-6"),
            ColSpec("pt_rapport", "N° rapport PT", "text",
                    maxlength=50, width="w-10"),
            ColSpec("pt_resultat", "Résultat PT", "select",
                    options=[
                        ("", "—"),
                        ("acceptable", "Acceptable"),
                        ("non_acceptable", "Non acceptable"),
                    ],
                    width="w-10"),
            ColSpec("remarques", "Remarques", "text",
                    maxlength=200, width="w-auto"),
        ],
    )
