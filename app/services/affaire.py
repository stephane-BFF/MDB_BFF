"""Logique métier des affaires — wizard de création, transitions de statut.

Toute la logique non-CRUD vit ici (calculs métier, validations, audit). Les
routes Flask se contentent d'orchestrer formulaires ↔ service.

Wizard V1.2 (4 étapes — voir ``docs/STRATEGIE_AMELIORATIONS_V1.2_2026-07-16.md``) :
``Q1 Affaire → Q2 Item → Q3 Réglementation → Q4 Récapitulatif``.
``Affaire.statut_wizard`` stocke l'étape **max atteinte** : les étapes déjà
franchies restent librement navigables (stepper cliquable) et leur
ré-enregistrement ne fait jamais reculer la progression.
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

# Étape suivante pour la navigation wizard.
_NEXT_STEP: dict[StatutWizard, StatutWizard | None] = {
    StatutWizard.Q1: StatutWizard.Q2,
    StatutWizard.Q2: StatutWizard.Q3,
    StatutWizard.Q3: StatutWizard.Q4,
    StatutWizard.Q4: None,  # fin du wizard
}

# Préfixe des clés JSONB par étape. ⚠️ L'étape Réglementation (Q3) écrit sous
# le préfixe historique ``q4_`` : ces clés (``q4_desp``, ``q4_categorie_ped``,
# ``q4_module_ped``…) sont un contrat consommé par ATTDECR/ETATDESC/… — ne
# jamais les renommer (décision D2 de la stratégie V1.2).
_JSON_PREFIX: dict[StatutWizard, str] = {
    StatutWizard.Q3: "q4_",
}


def start_wizard(user: User, annee: int) -> Affaire:
    """Crée une affaire vide en ``WIZARD_BROUILLON`` étape Q1.

    Le n° d'affaire n'est pas encore connu à ce stade : il sera choisi (ou
    saisi manuellement) par l'utilisateur à l'étape Q1, dans le registre
    général de commande BE (voir ``resolve_q1_affaire``).

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


def resolve_q1_affaire(
    affaire: Affaire,
    *,
    annee: int,
    numero_affaire: str,
    client_nom: str,
    references_client: str | None,
    user: User,
) -> StatutWizard | None:
    """Applique l'étape Q1 (informations génériques de l'affaire) et avance.

    Args:
        affaire: L'affaire en cours de wizard.
        annee: Année de l'affaire.
        numero_affaire: N° d'affaire choisi ou saisi (BN|BP + 4 chiffres).
        client_nom: Nom du client (prérempli du registre, modifiable).
        references_client: N° de commande client.
        user: Utilisateur effectuant la sauvegarde (pour l'audit).

    Returns:
        L'étape max atteinte après sauvegarde (``Q2`` au premier passage).
    """
    affaire.annee = annee
    affaire.numero_affaire = numero_affaire
    affaire.client_nom = client_nom
    affaire.references_client = references_client

    next_step = _advance(affaire, StatutWizard.Q1)

    AuditTrail.log(
        "affaire.wizard_step",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=StatutWizard.Q1.value,
        new_value=(next_step or StatutWizard.Q1).value,
        contexte={"numero_affaire": numero_affaire},
    )
    db.session.commit()
    return next_step


def resolve_q2_item(
    affaire: Affaire,
    *,
    item: str,
    registre_item: RegistreBEItem | None,
    payload: dict[str, Any],
    user: User,
) -> StatutWizard | None:
    """Applique l'étape Q2 (item et identification de l'équipement) et avance.

    Calcule ``references_internes`` (``{numero_affaire}-{item}``) — la clé
    d'unicité par dossier (nom du dossier NAS, QR code).

    Args:
        affaire: L'affaire en cours de wizard (Q1 déjà renseignée).
        item: N° d'item (4 chiffres).
        registre_item: Ligne du registre BE correspondante, ou ``None`` en
            saisie manuelle (traçabilité d'audit uniquement).
        payload: Champs validés du formulaire (repère, types, nombre…).
        user: Utilisateur effectuant la sauvegarde (pour l'audit).

    Returns:
        L'étape max atteinte après sauvegarde (``Q3`` au premier passage).
    """
    affaire.item = item
    affaire.references_internes = f"{affaire.numero_affaire}-{item}"
    _apply_affaire_columns(affaire, payload)

    # Complète les informations génériques restées vides à Q1 avec celles du
    # registre (le n° de commande client est porté par la ligne d'item).
    if registre_item is not None:
        if not affaire.references_client and registre_item.references_client:
            affaire.references_client = registre_item.references_client
        if not affaire.client_nom and registre_item.client_nom:
            affaire.client_nom = registre_item.client_nom

    next_step = _advance(affaire, StatutWizard.Q2)

    AuditTrail.log(
        "affaire.wizard_step",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=StatutWizard.Q2.value,
        new_value=(next_step or StatutWizard.Q2).value,
        contexte={
            "numero_affaire": affaire.numero_affaire,
            "item": item,
            "registre": registre_item is not None,
        },
    )
    db.session.commit()
    return next_step


def save_step(
    affaire: Affaire,
    step: StatutWizard,
    payload: dict[str, Any],
    user: User,
) -> StatutWizard | None:
    """Sauvegarde les données d'une étape et avance (sans jamais reculer).

    Le routage des champs (colonne typée vs JSONB) est fait selon l'étape :
        - Q1/Q2 sont traitées à part (``resolve_q1_affaire`` /
          ``resolve_q2_item``) — sélection registre + clé d'unicité.
        - Q3 (Réglementation) : clés JSON sur ``ParametrageAffaire.reponses``
          sous le préfixe historique ``q4_`` (contrat D2).
        - Q4 : pas de sauvegarde (récap) — la finalisation est gérée par
          ``finish_wizard()``.

    Args:
        affaire: L'affaire en cours de wizard.
        step: Étape courante (Q3 ou Q4).
        payload: Champs validés du formulaire.
        user: Utilisateur effectuant la sauvegarde (pour l'audit).

    Returns:
        L'étape max atteinte, ou ``None`` une fois le wizard prêt à finaliser.
    """
    if step is StatutWizard.Q3:
        _apply_parametrage(affaire, step, payload)
    # Q4 : pas de sauvegarde de champs ; juste avancement

    next_step = _advance(affaire, step)

    AuditTrail.log(
        "affaire.wizard_step",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=step.value,
        new_value=(next_step or step).value,
    )
    db.session.commit()
    return next_step


def finish_wizard(affaire: Affaire, user: User, commentaire: str | None = None) -> None:
    """Finalise le wizard : ``WIZARD_BROUILLON → BROUILLON``, statut_wizard à None.

    Précondition : ``affaire.statut_wizard == StatutWizard.Q4`` (récapitulatif
    atteint). Le dossier devient utilisable ; la fiche technique (ex-Q4→Q7)
    pourra être complétée ensuite.

    Args:
        affaire: L'affaire à finaliser.
        user: Utilisateur effectuant la finalisation.
        commentaire: Commentaire libre de Q4 (stocké dans le contexte d'audit).
    """
    if affaire.statut_wizard is not StatutWizard.Q4:
        raise ValueError(
            f"finish_wizard appelé hors Q4 (statut_wizard={affaire.statut_wizard})"
        )
    affaire.statut = Statut.BROUILLON
    affaire.statut_wizard = None

    # Architecture type du dossier (V1.2 Lot 6, D8) : la composition est
    # initialisée depuis le type d'équipement (NULL = dossier complet).
    if (
        affaire.composition_dossier is None
        and affaire.type_equipement is not None
        and affaire.type_equipement.formulaires_defaut is not None
    ):
        affaire.composition_dossier = list(affaire.type_equipement.formulaires_defaut)

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


# ── Regroupement par affaire (V1.2 Lot 3) ────────────────────────────────


def start_wizard_pour_affaire(user: User, numero_affaire: str) -> Affaire:
    """Démarre le wizard d'un nouvel item pour une affaire déjà connue.

    Les informations génériques (année, client, réf. commande) sont copiées
    du dossier le plus récent de l'affaire — à défaut, du registre BE — et
    le wizard démarre directement à l'étape Item (Q2). L'étape Affaire (Q1)
    reste consultable/modifiable via le stepper.

    Args:
        user: Utilisateur initiateur.
        numero_affaire: N° d'affaire BE (``BN``/``BP`` + 4 chiffres).

    Returns:
        Le nouveau dossier en ``WIZARD_BROUILLON``, étape Q2.
    """
    modele = (
        db.session.query(Affaire)
        .filter(Affaire.numero_affaire == numero_affaire, Affaire.item.isnot(None))
        .order_by(Affaire.created_at.desc())
        .first()
    )

    affaire = Affaire(
        numero_affaire=numero_affaire,
        cree_par_id=user.id,
        statut=Statut.WIZARD_BROUILLON,
        statut_wizard=StatutWizard.Q2,
    )
    if modele is not None:
        affaire.annee = modele.annee
        affaire.client_nom = modele.client_nom
        affaire.references_client = modele.references_client
    else:
        from app.services import registre_be as registre_be_svc  # noqa: PLC0415

        items = registre_be_svc.list_items_for_numero(numero_affaire)
        if items:
            affaire.annee = items[0].annee
            affaire.client_nom = items[0].client_nom
    if affaire.annee is None:
        import datetime as _dt  # noqa: PLC0415

        affaire.annee = _dt.datetime.now().year

    db.session.add(affaire)
    db.session.flush()

    AuditTrail.log(
        "affaire.wizard_started",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        contexte={"numero_affaire": numero_affaire, "nouvel_item": True},
    )
    db.session.commit()
    return affaire


def propager_infos_generiques(
    numero_affaire: str,
    *,
    client_nom: str,
    references_client: str | None,
    user: User,
) -> tuple[int, int]:
    """Applique les infos génériques à tous les dossiers modifiables de l'affaire.

    Propagation **sur confirmation** (arbitrage du 2026-07-16) : cette
    fonction n'est appelée qu'après que l'utilisateur a coché la case de
    confirmation. Les dossiers non modifiables (signés, clôturés…) sont
    ignorés et comptés à part. Chaque dossier modifié est audité.

    Returns:
        ``(nb_modifiés, nb_ignorés_non_modifiables)``.
    """
    dossiers = (
        db.session.query(Affaire)
        .filter(Affaire.numero_affaire == numero_affaire)
        .all()
    )
    modifies = 0
    ignores = 0
    for dossier in dossiers:
        if not dossier.is_editable:
            ignores += 1
            continue
        if (
            dossier.client_nom == client_nom
            and dossier.references_client == references_client
        ):
            continue
        ancien = {
            "client_nom": dossier.client_nom,
            "references_client": dossier.references_client,
        }
        dossier.client_nom = client_nom
        dossier.references_client = references_client
        AuditTrail.log(
            "affaire.infos_generiques_propagees",
            user=user,
            entity_type="affaire",
            entity_id=dossier.id,
            old_value=str(ancien),
            new_value=str({"client_nom": client_nom, "references_client": references_client}),
            contexte={"numero_affaire": numero_affaire},
        )
        modifies += 1
    db.session.commit()
    return modifies, ignores


# ── Composition du dossier / sommaire (V1.2 Lot 6) ───────────────────────


def formulaire_inclus(affaire: Affaire, code: str) -> bool:
    """True si le formulaire ``code`` fait partie du dossier (sommaire).

    ``composition_dossier`` à ``NULL`` = tout inclus (rétrocompatible, D8).
    """
    if affaire.composition_dossier is None:
        return True
    return code in affaire.composition_dossier


def set_composition_dossier(
    affaire: Affaire, codes: list[str], user: User
) -> None:
    """Enregistre la composition du dossier (codes inclus au sommaire).

    Exclure un formulaire le masque du sommaire, de la page dossier et du
    PDF assemblé, mais **ne supprime aucune donnée** (D8). La modification
    est auditée.
    """
    ancienne = affaire.composition_dossier
    affaire.composition_dossier = sorted(set(codes))
    AuditTrail.log(
        "affaire.composition_modifiee",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
        old_value=str(ancienne),
        new_value=str(affaire.composition_dossier),
    )
    db.session.commit()


# ── Fiche technique de l'item (V1.2 Lot 2) ───────────────────────────────

# Routage des champs de la fiche technique vers les préfixes JSONB
# historiques (contrat D2 — consommés par ATTDECR/ETATDESC/HYDR/PED).
_FICHE_PREFIXES: dict[str, str] = {
    # Réglementation + fluide → q4_
    "desp": "q4_",
    "stamp_u": "q4_",
    "categorie_ped": "q4_",
    "module_ped": "q4_",
    "fluide_etat": "q4_",
    "fluide_groupe": "q4_",
    "fluide_nom": "q4_",
    # Conditions de service → q5_
    "ps_bar": "q5_",
    "temperature_min_c": "q5_",
    "temperature_max_c": "q5_",
    "volume_l": "q5_",
    # Procédés de fabrication → q6_
    "procedes_soudage": "q6_",
    "tubes_soudes": "q6_",
    "tth_required": "q6_",
    # Contrôles et essais → q7_
    "cnd_methodes": "q7_",
    "test_pressions": "q7_",
    "inspection_client": "q7_",
}

#: Version de matrice signalant une saisie via la fiche technique.
_TEMPLATE_VERSION_FICHE = 2


def get_fiche_technique(affaire: Affaire) -> dict[str, Any]:
    """Valeurs actuelles de la fiche technique, indexées par nom de champ.

    Lit les clés JSONB ``q4_*``–``q7_*``. Repli de compatibilité (D3) :
    l'ancienne clé ``q7_test_pression`` (choix unique, str) est convertie en
    liste si la nouvelle ``q7_test_pressions`` est absente.
    """
    reponses = ((affaire.parametrage.reponses if affaire.parametrage else {}) or {})
    data: dict[str, Any] = {}
    for field, prefix in _FICHE_PREFIXES.items():
        key = f"{prefix}{field}"
        if key in reponses:
            data[field] = reponses[key]
    if "test_pressions" not in data and reponses.get("q7_test_pression"):
        data["test_pressions"] = [reponses["q7_test_pression"]]
    return data


def save_fiche_technique(
    affaire: Affaire, payload: dict[str, Any], user: User
) -> None:
    """Enregistre la fiche technique dans ``ParametrageAffaire.reponses``.

    Chaque champ est stocké sous son préfixe historique (``_FICHE_PREFIXES``,
    contrat D2). ``template_version`` passe à 2 pour tracer la saisie via la
    fiche technique. La modification est auditée.

    Args:
        affaire: Le dossier concerné (créé, hors wizard).
        payload: Champs validés du formulaire ``FicheTechniqueForm``.
        user: Utilisateur effectuant la sauvegarde.
    """
    if affaire.parametrage is None:
        affaire.parametrage = ParametrageAffaire(affaire_id=affaire.id, reponses={})

    reponses = dict(affaire.parametrage.reponses or {})
    for field, value in payload.items():
        prefix = _FICHE_PREFIXES.get(field)
        if prefix is None:
            continue
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        reponses[f"{prefix}{field}"] = value
    affaire.parametrage.reponses = reponses
    affaire.parametrage.template_version = _TEMPLATE_VERSION_FICHE

    AuditTrail.log(
        "affaire.fiche_technique_saved",
        user=user,
        entity_type="affaire",
        entity_id=affaire.id,
    )
    db.session.commit()


# ── Helpers internes ─────────────────────────────────────────────────────


def _advance(affaire: Affaire, step: StatutWizard) -> StatutWizard | None:
    """Avance ``statut_wizard`` (étape max) sans jamais le faire reculer.

    Ré-enregistrer une étape déjà franchie via le stepper cliquable renvoie
    vers l'étape suivante mais conserve la progression max.

    Returns:
        L'étape suivant ``step`` (cible de redirection), ou ``None`` si
        ``step`` est la dernière.
    """
    next_step = _NEXT_STEP[step]
    if next_step is not None:
        current = affaire.statut_wizard
        if current is None or next_step.numero > current.numero:
            affaire.statut_wizard = next_step
    return next_step


def _apply_affaire_columns(affaire: Affaire, payload: dict[str, Any]) -> None:
    """Applique les champs d'identité Q2 sur les colonnes typées de ``Affaire``."""
    column_fields = {
        "repere",
        "type_echangeur",
        "type_equipement_id",
        "nombre",
        "annee_construction",
    }
    for field, value in payload.items():
        if field in column_fields:
            setattr(affaire, field, value)


def _apply_parametrage(
    affaire: Affaire, step: StatutWizard, payload: dict[str, Any]
) -> None:
    """Stocke les champs d'une étape dans ``ParametrageAffaire.reponses``.

    Le préfixe des clés vient de ``_JSON_PREFIX`` (Q3 → ``q4_``, contrat D2).
    """
    if affaire.parametrage is None:
        affaire.parametrage = ParametrageAffaire(affaire_id=affaire.id, reponses={})

    reponses = dict(affaire.parametrage.reponses or {})
    prefix = _JSON_PREFIX.get(step, f"{step.value.lower()}_")
    for field, value in payload.items():
        # Sérialise les valeurs non-JSON (datetime, etc.) en string si besoin
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        reponses[f"{prefix}{field}"] = value
    # Réassignation pour que SQLAlchemy détecte la mutation (JSONB n'est pas
    # tracé en mutation sur SQLite/PG sans MutableDict).
    affaire.parametrage.reponses = reponses
