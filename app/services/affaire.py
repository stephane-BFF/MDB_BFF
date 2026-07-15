"""Logique métier des affaires — wizard de création, transitions de statut.

Toute la logique non-CRUD vit ici (calculs métier, validations, audit). Les
routes Flask se contentent d'orchestrer formulaires ↔ service.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.enums import Statut, StatutWizard
from app.extensions import db
from app.models.affaire import Affaire, ParametrageAffaire
from app.models.audit import AuditTrail

if TYPE_CHECKING:
    from app.models.registre_be import RegistreBEItem
    from app.models.user import User

# Étape suivante / précédente pour la navigation wizard.
_NEXT_STEP: dict[StatutWizard, StatutWizard | None] = {
    StatutWizard.Q1: StatutWizard.Q2,
    StatutWizard.Q2: StatutWizard.Q3,
    StatutWizard.Q3: StatutWizard.Q4,
    StatutWizard.Q4: StatutWizard.Q5,
    StatutWizard.Q5: StatutWizard.Q6,
    StatutWizard.Q6: StatutWizard.Q7,
    StatutWizard.Q7: StatutWizard.Q8,
    StatutWizard.Q8: None,  # fin du wizard
}
_PREV_STEP: dict[StatutWizard, StatutWizard | None] = {v: k for k, v in _NEXT_STEP.items() if v}


def start_wizard(user: User, annee: int) -> Affaire:
    """Crée une affaire vide en ``WIZARD_BROUILLON`` étape Q1.

    Le n° d'affaire n'est pas encore connu à ce stade : il sera choisi (ou
    saisi manuellement) par l'utilisateur à l'étape Q1, dans le registre
    général de commande BE (voir ``resolve_q1_selection``).

    Args:
        user: Utilisateur initiateur (sera ``cree_par``).
        annee: Année par défaut proposée en Q1 (modifiable).

    Returns:
        L'affaire nouvellement créée et persistée (avec ``id`` connu).
    """
    affaire = Affaire(
        annee=annee,
        cree_par_id=user.id,
        statut=Statut.WIZARD_BROUILLON,
        statut_wizard=StatutWizard.Q1,
    )
    db.session.add(affaire)
    db.session.flush()  # pour obtenir affaire.id

    AuditTrail.log(
        "affaire.wizard_started",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        contexte={"annee": annee},
    )
    db.session.commit()
    return affaire


def resolve_q1_selection(
    affaire: Affaire,
    *,
    annee: int,
    numero_affaire: str,
    item: str,
    registre_item: RegistreBEItem | None,
    user: User,
) -> StatutWizard | None:
    """Applique la sélection Q1 (n° affaire + item) et avance le wizard.

    Si ``registre_item`` est fourni (affaire connue du registre BE), les
    champs d'identité Q2/Q3 (client, repère, type d'échangeur, nombre) sont
    pré-remplis dès maintenant — l'utilisateur les retrouvera prêts (mais
    modifiables) en arrivant sur ces étapes. En saisie manuelle
    (``registre_item is None``), ces champs restent vides comme avant.

    Args:
        affaire: L'affaire en cours de wizard (étape Q1).
        annee: Année de l'affaire.
        numero_affaire: N° d'affaire choisi ou saisi (BN|BP + 4 chiffres).
        item: N° d'item (4 chiffres).
        registre_item: Ligne du registre BE correspondante, ou ``None`` en
            saisie manuelle.
        user: Utilisateur effectuant la sauvegarde (pour l'audit).

    Returns:
        L'étape suivante (``StatutWizard.Q2``).
    """
    affaire.annee = annee
    affaire.numero_affaire = numero_affaire
    affaire.item = item
    affaire.references_internes = f"{numero_affaire}-{item}"

    if registre_item is not None:
        affaire.client_nom = registre_item.client_nom
        affaire.references_client = registre_item.references_client
        affaire.repere = registre_item.repere_client
        affaire.type_echangeur = registre_item.type_appareil
        if registre_item.nombre is not None:
            affaire.nombre = registre_item.nombre

    next_step = _NEXT_STEP[StatutWizard.Q1]
    affaire.statut_wizard = next_step

    AuditTrail.log(
        "affaire.wizard_step",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=StatutWizard.Q1.value,
        new_value=next_step.value if next_step else StatutWizard.Q1.value,
        contexte={"numero_affaire": numero_affaire, "item": item},
    )
    db.session.commit()
    return next_step


def save_step(
    affaire: Affaire,
    step: StatutWizard,
    payload: dict[str, Any],
    user: User,
) -> StatutWizard | None:
    """Sauvegarde les données d'une étape et avance à la suivante.

    Le routage des champs (colonne typée vs JSONB) est fait selon l'étape :
        - Q2-Q3 : colonnes typées sur ``Affaire``. (Q1 est traitée à part par
          ``resolve_q1_selection`` — sélection du n° d'affaire/item.)
        - Q4-Q7 : clés JSON sur ``ParametrageAffaire.reponses`` préfixées ``qN_``.
        - Q8 : pas de sauvegarde (récap) — la finalisation est gérée par
          ``finish_wizard()``.

    Args:
        affaire: L'affaire en cours de wizard.
        step: Étape courante (Q2 à Q8 — pas Q1, voir ``resolve_q1_selection``).
        payload: Champs validés du formulaire.
        user: Utilisateur effectuant la sauvegarde (pour l'audit).

    Returns:
        L'étape suivante (``StatutWizard``) ou ``None`` si Q8 (= prêt à
        finaliser via ``finish_wizard``).
    """
    if step in (StatutWizard.Q2, StatutWizard.Q3):
        _apply_affaire_columns(affaire, payload)
    elif step in (StatutWizard.Q4, StatutWizard.Q5, StatutWizard.Q6, StatutWizard.Q7):
        _apply_parametrage(affaire, step, payload)
    # Q8 : pas de sauvegarde de champs ; juste avancement

    next_step = _NEXT_STEP[step]
    affaire.statut_wizard = next_step if next_step else step  # reste sur Q8 jusqu'à finish

    AuditTrail.log(
        "affaire.wizard_step",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=step.value,
        new_value=next_step.value if next_step else step.value,
    )
    db.session.commit()
    return next_step


def go_back(affaire: Affaire) -> StatutWizard | None:
    """Revient à l'étape précédente du wizard.

    Returns:
        L'étape sur laquelle on revient, ou ``None`` si on est déjà à Q1.
    """
    current = affaire.statut_wizard
    if current is None:
        return None
    prev = _PREV_STEP.get(current)
    if prev is not None:
        affaire.statut_wizard = prev
        db.session.commit()
    return prev


def finish_wizard(affaire: Affaire, user: User, commentaire: str | None = None) -> None:
    """Finalise le wizard : ``WIZARD_BROUILLON → BROUILLON``, statut_wizard à None.

    Précondition : ``affaire.statut_wizard == StatutWizard.Q8``.

    Args:
        affaire: L'affaire à finaliser.
        user: Utilisateur effectuant la finalisation.
        commentaire: Commentaire libre de Q8 (stocké dans le contexte d'audit).
    """
    if affaire.statut_wizard is not StatutWizard.Q8:
        raise ValueError(
            f"finish_wizard appelé hors Q8 (statut_wizard={affaire.statut_wizard})"
        )
    affaire.statut = Statut.BROUILLON
    affaire.statut_wizard = None

    AuditTrail.log(
        "affaire.wizard_finished",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=Statut.WIZARD_BROUILLON,
        new_value=Statut.BROUILLON,
        contexte={"commentaire": commentaire} if commentaire else None,
    )

    from app.services.jalons import init_jalons_affaire  # noqa: PLC0415
    init_jalons_affaire(affaire)

    db.session.commit()


# ── Helpers internes ─────────────────────────────────────────────────────


def _apply_affaire_columns(affaire: Affaire, payload: dict[str, Any]) -> None:
    """Applique les champs Q2-Q3 sur les colonnes typées de ``Affaire``."""
    column_fields = {
        "client_nom",
        "references_client",
        "repere",
        "type_echangeur",
        "nombre",
        "annee_construction",
    }
    for field, value in payload.items():
        if field in column_fields:
            setattr(affaire, field, value)


def _apply_parametrage(
    affaire: Affaire, step: StatutWizard, payload: dict[str, Any]
) -> None:
    """Stocke les champs Q4-Q7 dans ``ParametrageAffaire.reponses`` préfixés ``qN_``."""
    if affaire.parametrage is None:
        affaire.parametrage = ParametrageAffaire(affaire_id=affaire.id, reponses={})

    reponses = dict(affaire.parametrage.reponses or {})
    prefix = f"{step.value.lower()}_"
    for field, value in payload.items():
        # Sérialise les valeurs non-JSON (datetime, etc.) en string si besoin
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        reponses[f"{prefix}{field}"] = value
    # Réassignation pour que SQLAlchemy détecte la mutation (JSONB n'est pas
    # tracé en mutation sur SQLite/PG sans MutableDict).
    affaire.parametrage.reponses = reponses
