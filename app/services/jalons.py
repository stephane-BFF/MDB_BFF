"""Service métier — gestion des jalons JP0-JP6.

Responsabilités :
    - Initialisation des 7 jalons à la création d'une affaire.
    - Vérification des prérequis documentaires avant franchissement.
    - Calcul automatique du statut (EN_RETARD, BLOQUE) via ``refresh_statuts``.
    - Franchissement d'un jalon (validation + enregistrement audit).
    - Création et signature des Hold Points.

Toutes les décisions métier sont ici ; les routes ne font qu'appeler ces
fonctions et renvoyer les erreurs au client.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from app.enums import JalonCode, Statut, StatutJalon
from app.extensions import db
from app.models.audit import AuditTrail
from app.models.jalon import PREREQUIS_PAR_JALON, HoldPoint, Jalon

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.user import User


# ── Initialisation ────────────────────────────────────────────────────────


def init_jalons_affaire(affaire: Affaire) -> list[Jalon]:
    """Crée les 7 jalons JP0-JP6 pour une nouvelle affaire.

    Doit être appelé une seule fois, lors de la finalisation du wizard
    (transition WIZARD_BROUILLON → BROUILLON).

    Args:
        affaire: Affaire nouvellement créée (doit être flushée en base).

    Returns:
        Liste des 7 Jalon créés (non encore commités).
    """
    jalons = []
    for code in JalonCode:
        j = Jalon(
            affaire_id=affaire.id,
            code=code,
            statut=StatutJalon.EN_ATTENTE,
        )
        db.session.add(j)
        jalons.append(j)
    return jalons


# ── Vérification des prérequis ────────────────────────────────────────────


def verifier_prerequis(jalon: Jalon) -> tuple[bool, list[str]]:
    """Vérifie si tous les prérequis documentaires du jalon sont satisfaits.

    Un prérequis est satisfait si le formulaire correspondant existe et est
    au statut VALIDE ou SIGNE.

    Args:
        jalon: Jalon à vérifier.

    Returns:
        ``(True, [])`` si tous les prérequis sont satisfaits,
        ``(False, [liste des codes manquants])`` sinon.
    """
    codes_requis = jalon.effective_prerequis
    if not codes_requis:
        return True, []

    # Index des formulaires de l'affaire validés/signés
    codes_ok: set[str] = {
        f.code
        for f in jalon.affaire.formulaires
        if f.statut in (Statut.VALIDE, Statut.SIGNE)
    }

    manquants = [c for c in codes_requis if c not in codes_ok]
    return len(manquants) == 0, manquants


# ── Franchissement ────────────────────────────────────────────────────────


def franchir_jalon(
    jalon: Jalon,
    user: User,
    commentaire: str | None = None,
) -> tuple[bool, str]:
    """Tente de franchir un jalon après vérification des prérequis.

    Ne peut pas franchir un jalon déjà franchi, ou dont un Hold Point n'est
    pas signé.

    Args:
        jalon: Jalon à franchir.
        user: Utilisateur qui effectue l'action.
        commentaire: Commentaire optionnel.

    Returns:
        ``(True, "")`` si le franchissement a réussi.
        ``(False, message_erreur)`` si le franchissement est impossible.
    """
    if jalon.est_franchi:
        return False, "Ce jalon est déjà franchi."

    # Hold Points non signés bloquent le franchissement
    hold_non_signes = [hp for hp in jalon.hold_points if not hp.signe]
    if hold_non_signes:
        orgs = ", ".join(hp.organisme for hp in hold_non_signes)
        return False, f"Hold Point(s) en attente de signature : {orgs}"

    ok, manquants = verifier_prerequis(jalon)
    if not ok:
        return False, f"Documents requis manquants ou non validés : {', '.join(manquants)}"

    jalon.statut = StatutJalon.FRANCHI
    jalon.date_reelle = date.today()
    if commentaire:
        jalon.commentaire = commentaire

    AuditTrail.log(
        "jalon.franchi",
        entity_type="jalon",
        entity_id=jalon.id,
        new_value=jalon.code.value,
        contexte={
            "affaire_id": jalon.affaire_id,
            "code": jalon.code.value,
            "user_id": user.id,
        },
    )
    return True, ""


# ── Rafraîchissement automatique des statuts ──────────────────────────────


def refresh_statuts(affaire: Affaire) -> None:
    """Met à jour les statuts EN_RETARD / BLOQUE pour les jalons d'une affaire.

    - BLOQUE : prérequis non satisfaits et statut != FRANCHI
    - EN_RETARD : date_prevue dépassée et statut != FRANCHI
    - Retour à EN_ATTENTE/EN_COURS si les conditions ne sont plus remplies

    Doit être appelé à chaque changement de statut d'un formulaire, ou en
    début de page jalon.

    Args:
        affaire: Affaire dont on rafraîchit les jalons.
    """
    today = date.today()
    for jalon in affaire.jalons:
        if jalon.statut is StatutJalon.FRANCHI:
            continue

        ok_prereq, _ = verifier_prerequis(jalon)
        en_retard = (
            jalon.date_prevue is not None and jalon.date_prevue < today
        )

        if not ok_prereq:
            jalon.statut = StatutJalon.BLOQUE
        elif en_retard:
            jalon.statut = StatutJalon.EN_RETARD
        elif jalon.statut in (StatutJalon.BLOQUE, StatutJalon.EN_RETARD):
            # Les conditions ne sont plus remplies : retour à EN_COURS
            jalon.statut = StatutJalon.EN_COURS


# ── Hold Points ───────────────────────────────────────────────────────────


def creer_hold_point(
    jalon: Jalon,
    organisme: str,
    nom_inspecteur: str | None,
    date_inspection: date | None,
    user: User,
) -> HoldPoint:
    """Crée un Hold Point sur un jalon.

    Args:
        jalon: Jalon auquel rattacher le Hold Point.
        organisme: Nom de l'organisme (ex: LRQA, Bureau Veritas).
        nom_inspecteur: Nom de l'inspecteur tiers (optionnel).
        date_inspection: Date prévue de l'inspection (optionnel).
        user: Utilisateur qui crée le Hold Point.

    Returns:
        HoldPoint créé (non encore commité).
    """
    hp = HoldPoint(
        jalon_id=jalon.id,
        organisme=organisme,
        nom_inspecteur=nom_inspecteur,
        date_inspection=date_inspection,
        signe=False,
    )
    db.session.add(hp)

    AuditTrail.log(
        "hold_point.cree",
        entity_type="hold_point",
        entity_id=None,
        new_value=organisme,
        contexte={
            "jalon_id": jalon.id,
            "affaire_id": jalon.affaire_id,
            "user_id": user.id,
        },
    )
    return hp


def signer_hold_point(hp: HoldPoint, user: User) -> None:
    """Signe un Hold Point et verrouille le jalon associé.

    Args:
        hp: Hold Point à signer.
        user: Utilisateur (approbateur) qui valide la signature.
    """
    hp.signe = True
    hp.date_inspection = hp.date_inspection or date.today()

    AuditTrail.log(
        "hold_point.signe",
        entity_type="hold_point",
        entity_id=hp.id,
        new_value=hp.organisme,
        contexte={
            "jalon_id": hp.jalon_id,
            "affaire_id": hp.jalon.affaire_id,
            "user_id": user.id,
        },
    )


# ── Alertes jalons en retard ──────────────────────────────────────────────


def get_jalons_en_retard() -> list[Jalon]:
    """Retourne tous les jalons EN_RETARD toutes affaires confondues.

    Utilisé par la tâche Celery d'alerte email quotidienne.
    """
    return (
        db.session.query(Jalon)
        .filter(Jalon.statut == StatutJalon.EN_RETARD)
        .all()
    )
