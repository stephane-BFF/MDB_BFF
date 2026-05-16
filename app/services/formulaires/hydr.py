"""Service métier du formulaire HYDR — Procès-verbal d'épreuve hydrostatique.

.. note::
    Ce module expose des fonctions de niveau module (API historique Phase 1)
    **et** la classe ``HydrService`` utilisée par le registre de routes.
    Les deux interfaces sont maintenues pour compatibilité.


Règle critique : PT = round(PS × 1.43, 1) — calculé côté JS (temps réel)
**et** revalidé ici côté serveur à chaque sauvegarde.

Workflow :
    (aucun) → BROUILLON  (premier save_brouillon)
    BROUILLON → VALIDE   (valider — VERIFICATEUR+)
    VALIDE    → SIGNE    (signer  — APPROBATEUR+)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.enums import Chapitre, Statut
from app.extensions import db
from app.models.audit import AuditTrail
from app.models.formulaire import Formulaire, FormulaireTemplate
from app.models.signature import Signature

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.user import User

_CODE = "HYDR"
_CHAPITRE = Chapitre.E

# Champs obligatoires pour autoriser la transition → VALIDE.
_REQUIRED_FOR_VALIDATION = frozenset({"ps", "pt", "fluide", "date_epreuve"})


def compute_pt(ps: float) -> float:
    """Calcule la pression d'épreuve PT = round(PS × 1.43, 1)."""
    return round(ps * 1.43, 1)


def get_or_none(affaire: Affaire) -> Formulaire | None:
    """Retourne le formulaire HYDR de l'affaire, ou None s'il n'existe pas."""
    return (
        db.session.query(Formulaire)
        .filter_by(affaire_id=affaire.id, code=_CODE)
        .first()
    )


def prefill_from_parametrage(affaire: Affaire) -> dict[str, Any]:
    """Extrait les données de pré-remplissage depuis le wizard Q5.

    Retourne un dict vide si le paramétrage n'est pas disponible.
    """
    if not (affaire.parametrage and affaire.parametrage.reponses):
        return {}
    reponses = affaire.parametrage.reponses
    ps_raw = reponses.get("q5_ps_bar")
    if ps_raw is None:
        return {}
    try:
        ps = float(ps_raw)
    except (TypeError, ValueError):
        return {}
    return {"ps": ps, "pt": compute_pt(ps)}


def save_brouillon(affaire: Affaire, payload: dict[str, Any], user: User) -> Formulaire:
    """Crée ou met à jour le formulaire HYDR en mode brouillon.

    Si le formulaire n'existe pas encore, il est créé (action ``formulaire.created``).
    Le champ PT est toujours recompté depuis PS côté serveur pour garantir
    la cohérence indépendamment de ce que le client envoie.

    Args:
        affaire: L'affaire propriétaire.
        payload: Champs reçus du client (JSON).
        user: Utilisateur effectuant la sauvegarde.

    Returns:
        Le formulaire HYDR (créé ou mis à jour).

    Raises:
        ValueError: Si le formulaire n'est plus éditable (VALIDE ou SIGNE).
    """
    formulaire = get_or_none(affaire)

    if formulaire is None:
        tmpl = _get_active_template()
        formulaire = Formulaire(
            affaire_id=affaire.id,
            code=_CODE,
            chapitre=_CHAPITRE,
            statut=Statut.BROUILLON,
            template_version=tmpl.version,
            data={},
        )
        db.session.add(formulaire)
        db.session.flush()
        AuditTrail.log(
            "formulaire.created",
            user=user,
            entity_type="formulaire",
            entity_id=formulaire.id,
            new_value=_CODE,
            contexte={"affaire_id": affaire.id, "template_version": tmpl.version},
        )
    elif not formulaire.statut.is_editable:
        raise ValueError(
            f"Formulaire HYDR non éditable (statut={formulaire.statut.value})."
        )

    # Normalise le payload et recompute PT depuis PS côté serveur.
    clean = _sanitize_payload(payload)
    formulaire.data = clean

    AuditTrail.log(
        "formulaire.saved",
        user=user,
        entity_type="formulaire",
        entity_id=formulaire.id,
        contexte={"statut": formulaire.statut.value},
    )
    db.session.commit()
    return formulaire


def valider(formulaire: Formulaire, user: User) -> None:
    """Transition BROUILLON → VALIDE.

    Args:
        formulaire: Formulaire HYDR en statut BROUILLON.
        user: Vérificateur ou Approbateur ou Admin.

    Raises:
        ValueError: Si le statut source est incorrect ou si des champs
            obligatoires sont manquants dans ``formulaire.data``.
    """
    if formulaire.statut is not Statut.BROUILLON:
        raise ValueError(
            f"La validation requiert le statut BROUILLON (actuel : {formulaire.statut.value})."
        )

    missing = _REQUIRED_FOR_VALIDATION - set(formulaire.data.keys())
    if missing:
        raise ValueError(
            f"Champs obligatoires manquants avant validation : {', '.join(sorted(missing))}."
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


def signer(formulaire: Formulaire, user: User) -> Signature:
    """Transition VALIDE → SIGNE + création de la Signature SHA-256.

    La signature est immuable : ``Signature`` hérite de ``CreatedAtMixin``
    et l'ORM interdit tout UPDATE/DELETE.

    Args:
        formulaire: Formulaire HYDR en statut VALIDE.
        user: Approbateur ou Admin.

    Returns:
        La ``Signature`` créée.

    Raises:
        ValueError: Si le statut source n'est pas VALIDE.
    """
    if formulaire.statut is not Statut.VALIDE:
        raise ValueError(
            f"La signature requiert le statut VALIDE (actuel : {formulaire.statut.value})."
        )

    hash_val = Signature.compute_hash(
        formulaire.code, formulaire.template_version, formulaire.data
    )
    sig = Signature(
        formulaire_id=formulaire.id,
        user_id=user.id,
        hash_sha256=hash_val,
    )
    db.session.add(sig)

    formulaire.statut = Statut.SIGNE
    AuditTrail.log(
        "formulaire.signed",
        user=user,
        entity_type="formulaire",
        entity_id=formulaire.id,
        old_value=Statut.VALIDE,
        new_value=Statut.SIGNE,
        contexte={"hash_sha256": hash_val[:16]},
    )
    db.session.commit()
    return sig


# ── Classe wrapper (registre de services) ────────────────────────────────


class HydrService:
    """Façade orientée-classe pour le registre — délègue aux fonctions du module."""

    CODE = _CODE
    CHAPITRE = _CHAPITRE
    TITLE = "Procès-verbal d'épreuve hydrostatique"
    TITLE_EN = "Hydrostatic test record"
    SECTIONS: list = []  # template dédié — SECTIONS non utilisées
    REQUIRED_FOR_VALIDATION = _REQUIRED_FOR_VALIDATION
    CUSTOM_TEMPLATE = True

    @classmethod
    def get_web_template(cls) -> str:
        return "formulaires/hydr.html"

    @classmethod
    def get_pdf_template(cls) -> str:
        return "pdf/hydr.html"

    @classmethod
    def get_or_none(cls, affaire: Affaire) -> Formulaire | None:
        return get_or_none(affaire)

    @classmethod
    def prefill_from_parametrage(cls, affaire: Affaire) -> dict[str, Any]:
        return prefill_from_parametrage(affaire)

    @classmethod
    def save_brouillon(cls, affaire: Affaire, payload: dict[str, Any], user: User) -> Formulaire:
        return save_brouillon(affaire, payload, user)

    @classmethod
    def valider(cls, formulaire: Formulaire, user: User) -> None:
        return valider(formulaire, user)

    @classmethod
    def signer(cls, formulaire: Formulaire, user: User) -> Signature:
        return signer(formulaire, user)


# ── Helpers internes ─────────────────────────────────────────────────────


def _get_active_template() -> FormulaireTemplate:
    tmpl = (
        db.session.query(FormulaireTemplate)
        .filter_by(code=_CODE, actif=True)
        .first()
    )
    if tmpl is None:
        raise RuntimeError(
            "Template HYDR actif introuvable — exécutez `flask seed` pour initialiser."
        )
    return tmpl


def _sanitize_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise et valide les champs HYDR reçus du client.

    - Convertit les types (str → float/int).
    - Recompute PT = PS × 1.43 côté serveur.
    - Ignore les clés inconnues pour éviter la pollution du JSONB.
    """
    allowed_keys = {
        "ps", "pt", "fluide", "temperature_c", "duree_minutes",
        "date_epreuve", "numero_manometre", "conforme", "observations",
    }
    clean: dict[str, Any] = {}

    for key, value in raw.items():
        if key not in allowed_keys:
            continue
        if value is None or value == "":
            continue
        clean[key] = value

    # Recompute PT depuis PS (source de vérité côté serveur).
    ps_raw = clean.get("ps")
    if ps_raw is not None:
        try:
            ps = float(ps_raw)
            clean["ps"] = ps
            clean["pt"] = compute_pt(ps)
        except (TypeError, ValueError):
            clean.pop("ps", None)
            clean.pop("pt", None)

    # Normalise les types numériques.
    for float_key in ("temperature_c",):
        if float_key in clean:
            try:
                clean[float_key] = float(clean[float_key])
            except (TypeError, ValueError):
                del clean[float_key]

    for int_key in ("duree_minutes",):
        if int_key in clean:
            try:
                clean[int_key] = int(clean[int_key])
            except (TypeError, ValueError):
                del clean[int_key]

    # Normalise conforme en bool.
    if "conforme" in clean:
        val = clean["conforme"]
        if isinstance(val, str):
            clean["conforme"] = val.lower() in ("true", "1", "oui", "on")
        else:
            clean["conforme"] = bool(val)

    return clean
