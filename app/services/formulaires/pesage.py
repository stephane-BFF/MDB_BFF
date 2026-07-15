"""Service formulaire PESAGE — PV de pesage.

Référence CDC v2 : §27 « PV de pesage ».
Calcul automatique : ecart_pct = |poids_mesure - poids_plan| / poids_plan × 100
"""
from __future__ import annotations

from typing import Any

from flask_babel import lazy_gettext as _l

from app.enums import Chapitre
from app.services.formulaires.base import FieldSpec, SectionSpec, SimpleFormulaireService


class PesageService(SimpleFormulaireService):
    CODE = "PESAGE"
    CHAPITRE = Chapitre.F
    TITLE = "Procès-verbal de pesage"
    TITLE_EN = "Weighing record"
    REQUIRED_FOR_VALIDATION = frozenset({"date_pesage", "poids_mesure", "poids_plan", "tolerance"})
    SECTIONS = [
        SectionSpec(_l("Pesage"), [
            FieldSpec("date_pesage", _l("Date de pesage"), "date",
                      required=True, col_class="col-sm-6 col-md-3"),
            FieldSpec("conditions", _l("Conditions de pesage"), "text",
                      maxlength=200, col_class="col-sm-6 col-md-6",
                      help_text=_l("Ex : À vide, sans fluide ni protections.")),
            FieldSpec("bascule", _l("Bascule / pont bascule"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-4",
                      help_text=_l("Phase 4 : sélection depuis le référentiel métrologie.")),
            FieldSpec("operateur", _l("Opérateur"), "text",
                      maxlength=100, col_class="col-sm-6 col-md-3",
                      help_text=_l("Phase 4 : sélection depuis le référentiel QC.")),
        ]),
        SectionSpec(_l("Mesures"), [
            FieldSpec("poids_mesure", _l("Poids mesuré (kg)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("poids_plan", _l("Poids théorique selon plan (kg)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("tolerance", _l("Tolérance acceptée (%)"), "float",
                      required=True, step="0.1", min_val="0",
                      col_class="col-sm-6 col-md-3"),
            FieldSpec("ecart_pct", _l("Écart (%)"), "float",
                      server_computed=True,
                      help_text=_l("Calculé automatiquement."),
                      col_class="col-sm-6 col-md-3"),
        ]),
        SectionSpec(_l("Résultat"), [
            FieldSpec("conforme", _l("Poids conforme (écart ≤ tolérance)"), "checkbox",
                      col_class="col-12 col-md-6"),
            FieldSpec("remarques", _l("Remarques"), "textarea",
                      maxlength=2000, rows=3, col_class="col-12"),
        ]),
    ]

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """Calcule ecart_pct = |poids_mesure - poids_plan| / poids_plan × 100."""
        clean = super()._sanitize_payload(raw)
        pm = clean.get("poids_mesure")
        pp = clean.get("poids_plan")
        if isinstance(pm, (int, float)) and isinstance(pp, (int, float)) and pp != 0:
            clean["ecart_pct"] = round(abs(pm - pp) / pp * 100, 2)
        return clean
