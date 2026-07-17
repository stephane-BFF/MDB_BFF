"""Service formulaire LISTSOUD — Liste des soudeurs qualifiés.

Référence CDC v2 : §8 « Liste des soudeurs ».

Formulaire **structuré** (template dédié) : on ajoute un soudeur depuis le
référentiel ``Soudeur`` (matricule / initiales / nom renseignés
automatiquement), puis pour ce soudeur une ou plusieurs *qualifications* (QS).
Chaque qualification décrit un procédé de soudage, les positions et les
groupes de matériaux qualifiés (cases à cocher), une référence de QS et une
date de validité.

Les listes de positions et de groupes de matériaux dépendent du **code de
construction** retenu pour l'affaire : ASME (positions QW-461, P-Numbers) ou
EN/ISO (positions ISO 6947, groupes ISO/TR 15608).

Structure stockée dans ``Formulaire.data`` ::

    {
        "code_construction": "ASME",            # ou "EN"
        "soudeurs": [
            {
                "matricule": "96", "initiales": "SG", "nom": "SZUROMI Gabor",
                "qualifications": [
                    {"procede": "141", "positions": ["6G"], "groupes": ["P8"],
                     "reference_qs": "QS-96-141", "date_validite": "2026-09-29"},
                    ...
                ],
            },
            ...
        ],
    }
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.enums import Chapitre, Statut
from app.extensions import db
from app.models.audit import AuditTrail
from app.models.referentiel import Soudeur
from app.services.formulaires.base import SimpleFormulaireService

if TYPE_CHECKING:
    from app.models.formulaire import Formulaire
    from app.models.user import User


# ── Référentiels normatifs ────────────────────────────────────────────────

# Procédés de soudage (ISO 4063).
PROCEDES: tuple[tuple[str, str], ...] = (
    ("141", "141 — TIG (soudage à l'arc sous gaz inerte avec électrode de tungstène)"),
    ("111", "111 — Électrode enrobée (MMA)"),
    ("135", "135 — MAG fil massif"),
    ("136", "136 — MAG fil fourré"),
    ("138", "138 — MAG fil fourré à poudre métallique"),
    ("131", "131 — MIG fil massif"),
    ("121", "121 — Soudage à l'arc sous flux (sous flux solide)"),
    ("15", "15 — Soudage plasma"),
)

# Positions de soudage — ASME BPVC IX (QW-461).
POSITIONS_ASME: tuple[str, ...] = (
    "1G", "2G", "3G", "4G", "5G", "6G", "6GR",
    "1F", "2F", "3F", "4F", "5F",
)
# Positions de soudage — EN ISO 6947.
POSITIONS_EN: tuple[str, ...] = (
    "PA", "PB", "PC", "PD", "PE", "PF", "PG", "H-L045", "J-L045",
)

# Groupes de matériaux — ASME BPVC IX (P-Numbers, QW/QB-422).
GROUPES_ASME: tuple[str, ...] = (
    "P1", "P3", "P4", "P5A", "P5B", "P6", "P7", "P8",
    "P9A", "P9B", "P10", "P11", "P15E", "P34", "P41", "P42", "P43", "P45",
)
# Groupes de matériaux — EN ISO/TR 15608.
GROUPES_EN: tuple[str, ...] = (
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
)

_CODES_CONSTRUCTION = ("ASME", "EN")


class ListSoudService(SimpleFormulaireService):
    """Liste des soudeurs qualifiés — formulaire structuré (template dédié)."""

    CODE = "LISTSOUD"
    CHAPITRE = Chapitre.C
    TITLE = "Liste des soudeurs qualifiés"
    TITLE_EN = "Qualified welders list"
    CUSTOM_TEMPLATE = True

    # ── Options de référence pour le template / JS ────────────────────────

    @classmethod
    def get_reference_options(cls) -> dict[str, Any]:
        """Référentiels alimentant l'UI : soudeurs, procédés, positions, groupes."""
        soudeurs = (
            db.session.query(Soudeur)
            .filter_by(actif=True)
            .order_by(Soudeur.nom)
            .all()
        )
        return {
            "codes_construction": list(_CODES_CONSTRUCTION),
            "procedes": [list(p) for p in PROCEDES],
            "positions": {"ASME": list(POSITIONS_ASME), "EN": list(POSITIONS_EN)},
            "groupes": {"ASME": list(GROUPES_ASME), "EN": list(GROUPES_EN)},
            "soudeurs": [
                {
                    "matricule": s.matricule or "",
                    "initiales": s.initiales or "",
                    "nom": s.nom,
                }
                for s in soudeurs
            ],
        }

    # ── Sanitisation du payload imbriqué ──────────────────────────────────

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """Nettoie la structure imbriquée soudeurs → qualifications.

        Filtre les valeurs d'énumération invalides selon le code de
        construction ; conserve les saisies partielles (la complétude est
        vérifiée à la validation, pas à l'enregistrement du brouillon).
        """
        code = raw.get("code_construction")
        code = code if code in _CODES_CONSTRUCTION else "ASME"

        valid_positions = set(POSITIONS_ASME if code == "ASME" else POSITIONS_EN)
        valid_groupes = set(GROUPES_ASME if code == "ASME" else GROUPES_EN)
        valid_procedes = {c for c, _ in PROCEDES}

        clean_soudeurs: list[dict[str, Any]] = []
        for s in raw.get("soudeurs", []):
            if not isinstance(s, dict):
                continue
            nom = str(s.get("nom") or "").strip()
            if not nom:
                continue

            quals: list[dict[str, Any]] = []
            for q in s.get("qualifications", []):
                if not isinstance(q, dict):
                    continue
                procede = str(q.get("procede") or "").strip()
                if procede not in valid_procedes:
                    procede = ""
                positions = [
                    p for p in (q.get("positions") or []) if p in valid_positions
                ]
                groupes = [g for g in (q.get("groupes") or []) if g in valid_groupes]
                reference_qs = str(q.get("reference_qs") or "").strip()[:100]
                date_validite = str(q.get("date_validite") or "").strip()[:10]
                # Ignore les qualifications entièrement vides.
                if not (procede or positions or groupes or reference_qs or date_validite):
                    continue
                quals.append(
                    {
                        "procede": procede,
                        "positions": positions,
                        "groupes": groupes,
                        "reference_qs": reference_qs,
                        "date_validite": date_validite,
                    }
                )

            clean_soudeurs.append(
                {
                    "matricule": str(s.get("matricule") or "").strip()[:20],
                    "initiales": str(s.get("initiales") or "").strip()[:10],
                    "nom": nom[:200],
                    "qualifications": quals,
                }
            )

        return {"code_construction": code, "soudeurs": clean_soudeurs}

    # ── Validation (BROUILLON → VALIDE) ───────────────────────────────────

    @classmethod
    def valider(cls, formulaire: Formulaire, user: User) -> None:
        """Valide : au moins un soudeur, chacun avec au moins une qualification
        complète (procédé + date de validité).

        Raises:
            ValueError: statut incorrect ou données incomplètes.
        """
        if formulaire.statut is not Statut.BROUILLON:
            raise ValueError(
                f"La validation requiert BROUILLON (actuel : {formulaire.statut.value})."
            )
        data = formulaire.data or {}
        soudeurs = data.get("soudeurs", [])
        if not soudeurs:
            raise ValueError("Ajoutez au moins un soudeur avant de valider.")

        for s in soudeurs:
            nom = s.get("nom") or "?"
            quals = s.get("qualifications", [])
            if not quals:
                raise ValueError(f"Le soudeur « {nom} » n'a aucune qualification.")
            for q in quals:
                if not q.get("procede"):
                    raise ValueError(f"Procédé manquant pour le soudeur « {nom} ».")
                if not q.get("date_validite"):
                    raise ValueError(
                        f"Date de validité manquante pour « {nom} » "
                        f"(procédé {q.get('procede')})."
                    )

        old_statut = formulaire.statut
        formulaire.statut = Statut.VALIDE
        AuditTrail.log(
            "formulaire.validated",
            user=user,
            entity_type="formulaire",
            entity_id=formulaire.id,
            old_value=old_statut,
            new_value=Statut.VALIDE,
        )
        db.session.commit()
