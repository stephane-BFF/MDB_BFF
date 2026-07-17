"""Routes du module Affaires — liste paginée + wizard de création Q1-Q4."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import TYPE_CHECKING

from flask import abort, flash, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload
from werkzeug.wrappers.response import Response

from app.blueprints.affaires import bp
from app.enums import Role, Statut, StatutWizard
from app.extensions import db
from app.forms.affaire import AffaireFilterForm
from app.forms.wizard import (
    CATEGORIE_ART_43,
    MODULES_PAR_CATEGORIE,
    MODULES_PED,
    MODULES_SUPERIEURS_PAR_CATEGORIE,
    NUMERO_AFFAIRE_MANUEL,
    WizardQ1Form,
    WizardQ2Form,
    WizardQ3Form,
    WizardQ4Form,
)
from app.models.affaire import Affaire
from app.models.referentiel import TypeEquipement
from app.models.user import User
from app.services import affaire as affaire_svc
from app.services import registre_be as registre_be_svc
from app.utils.decorators import role_required

if TYPE_CHECKING:
    from app.models.registre_be import RegistreBEItem

# Nombre d'affaires par page — peut devenir paramétrable plus tard.
_PER_PAGE = 20

# Mapping étape → classe de formulaire (wizard V1.2 : 4 étapes).
_WIZARD_FORMS: dict[StatutWizard, type] = {
    StatutWizard.Q1: WizardQ1Form,
    StatutWizard.Q2: WizardQ2Form,
    StatutWizard.Q3: WizardQ3Form,
    StatutWizard.Q4: WizardQ4Form,
}

# Mapping catégorie du registre BE → valeur du champ ``categorie_ped``.
# « 3.3 » est l'ancienne référence (art. 3 §3, PED 97/23) de l'actuel art. 4.3.
_REGISTRE_CATEGORIES: dict[str, str] = {
    "I": "I",
    "II": "II",
    "III": "III",
    "IV": "IV",
    "4.3": CATEGORIE_ART_43,
    "3.3": CATEGORIE_ART_43,
}

_WIZARD_ROLES = (Role.REDACTEUR, Role.VERIFICATEUR, Role.APPROBATEUR, Role.ADMIN)


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def index() -> str:
    """Liste paginée des affaires avec filtres par statut, année et recherche.

    Filtres passés en query-string :
        - ``statut`` : valeur d'enum (ex: ``"brouillon"``).
        - ``annee`` : entier 4 chiffres.
        - ``q`` : recherche partielle sur ``numero_affaire``, ``client_nom``,
          ``repere`` et ``type_echangeur`` (case-insensitive).
        - ``page`` : numéro de page (défaut 1).

    Tri par défaut : ``created_at DESC`` (plus récentes en premier).
    """
    form = AffaireFilterForm(request.args, meta={"csrf": False})

    stmt = select(Affaire).options(joinedload(Affaire.cree_par))

    statut_val = (form.statut.data or "").strip()
    if statut_val:
        try:
            stmt = stmt.where(Affaire.statut == Statut(statut_val))
        except ValueError:
            pass  # valeur invalide : ignore le filtre

    annee_val = (form.annee.data or "").strip()
    if annee_val.isdigit() and len(annee_val) == 4:
        stmt = stmt.where(Affaire.annee == int(annee_val))

    q_val = (form.q.data or "").strip()
    if q_val:
        like = f"%{q_val}%"
        stmt = stmt.where(
            or_(
                Affaire.numero_affaire.ilike(like),
                Affaire.client_nom.ilike(like),
                Affaire.repere.ilike(like),
                Affaire.type_echangeur.ilike(like),
            )
        )

    stmt = stmt.order_by(Affaire.created_at.desc())

    pagination = db.paginate(stmt, per_page=_PER_PAGE, error_out=False)

    return render_template(
        "affaires/index.html",
        form=form,
        pagination=pagination,
        affaires=pagination.items,
    )


# ────────────────────────────────────────────────────────────────────────
# Page détail d'une affaire — accordéon A-G des 27 formulaires
# ────────────────────────────────────────────────────────────────────────


@bp.route("/<int:affaire_id>")
@login_required  # type: ignore[untyped-decorator]
def show(affaire_id: int) -> str:
    """Affiche la page d'une affaire avec accordéon A-G des formulaires.

    Pour chaque chapitre, liste les ``FormulaireTemplate`` actifs et leur état
    d'instanciation pour cette affaire (créé ? signé ?).

    Les affaires en wizard sont redirigées vers l'étape courante du wizard.
    """
    from app.enums import Chapitre
    from app.models.formulaire import Formulaire, FormulaireTemplate
    from app.services.formulaires import registered_codes

    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        abort(404)

    if affaire.statut is Statut.WIZARD_BROUILLON:
        return redirect(  # type: ignore[return-value]
            url_for(
                "affaires.wizard_step",
                affaire_id=affaire.id,
                step=(affaire.statut_wizard or StatutWizard.Q1).value,
            )
        )

    # Charge tous les templates actifs groupés par chapitre.
    templates_by_chap: dict[Chapitre, list[FormulaireTemplate]] = {c: [] for c in Chapitre}
    for tmpl in db.session.query(FormulaireTemplate).filter_by(actif=True).all():
        templates_by_chap[tmpl.chapitre].append(tmpl)

    # Charge les formulaires existants pour cette affaire, indexés par code.
    formulaires_by_code: dict[str, Formulaire] = {
        f.code: f
        for f in db.session.query(Formulaire).filter_by(affaire_id=affaire.id).all()
    }

    return render_template(
        "affaires/show.html",
        affaire=affaire,
        chapitres=list(Chapitre),
        templates_by_chap=templates_by_chap,
        formulaires_by_code=formulaires_by_code,
        implemented_codes=registered_codes(),
    )


# ────────────────────────────────────────────────────────────────────────
# Historique audit_trail d'une affaire
# ────────────────────────────────────────────────────────────────────────


@bp.route("/<int:affaire_id>/historique")
@login_required  # type: ignore[untyped-decorator]
def historique(affaire_id: int) -> str:
    """Affiche le journal d'audit paginé d'une affaire.

    Inclut toutes les entrées relatives à l'affaire elle-même, à ses
    formulaires et à ses jalons, triées de la plus récente à la plus ancienne.
    """
    from app.models.audit import AuditTrail  # noqa: PLC0415
    from app.models.formulaire import Formulaire  # noqa: PLC0415
    from app.models.jalon import Jalon  # noqa: PLC0415

    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        abort(404)

    form_ids = [
        r for (r,) in db.session.query(Formulaire.id).filter_by(affaire_id=affaire_id).all()
    ]
    jalon_ids = [
        r for (r,) in db.session.query(Jalon.id).filter_by(affaire_id=affaire_id).all()
    ]

    conditions = [
        (AuditTrail.entity_type == "affaire") & (AuditTrail.entity_id == affaire_id),
    ]
    if form_ids:
        conditions.append(
            (AuditTrail.entity_type == "formulaire") & (AuditTrail.entity_id.in_(form_ids))
        )
    if jalon_ids:
        conditions.append(
            (AuditTrail.entity_type == "jalon") & (AuditTrail.entity_id.in_(jalon_ids))
        )

    stmt = (
        select(AuditTrail)
        .options(joinedload(AuditTrail.user))
        .where(or_(*conditions))
        .order_by(AuditTrail.created_at.desc())
    )
    pagination = db.paginate(stmt, per_page=50, error_out=False)

    return render_template(
        "affaires/historique.html",
        affaire=affaire,
        pagination=pagination,
        entries=pagination.items,
    )


# ────────────────────────────────────────────────────────────────────────
# Export CSV de la liste des affaires
# ────────────────────────────────────────────────────────────────────────


@bp.route("/export-csv")
@login_required  # type: ignore[untyped-decorator]
def export_csv() -> Response:
    """Exporte la liste filtrée des affaires en CSV UTF-8 BOM (compatible Excel).

    Accepte les mêmes paramètres de filtre que la route ``index``
    (``statut``, ``annee``, ``q``).
    """
    form = AffaireFilterForm(request.args, meta={"csrf": False})

    stmt = select(Affaire).options(joinedload(Affaire.cree_par))

    statut_val = (form.statut.data or "").strip()
    if statut_val:
        try:
            from app.enums import Statut as _Statut  # noqa: PLC0415
            stmt = stmt.where(Affaire.statut == _Statut(statut_val))
        except ValueError:
            pass

    annee_val = (form.annee.data or "").strip()
    if annee_val.isdigit() and len(annee_val) == 4:
        stmt = stmt.where(Affaire.annee == int(annee_val))

    q_val = (form.q.data or "").strip()
    if q_val:
        like = f"%{q_val}%"
        stmt = stmt.where(
            or_(
                Affaire.numero_affaire.ilike(like),
                Affaire.client_nom.ilike(like),
                Affaire.repere.ilike(like),
                Affaire.type_echangeur.ilike(like),
            )
        )

    stmt = stmt.order_by(Affaire.created_at.desc())
    affaires = db.session.execute(stmt).scalars().all()

    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(
        ["Numéro", "Client", "Repère", "Type échangeur", "Statut", "Année", "Créé par", "Créé le"]
    )
    for a in affaires:
        writer.writerow([
            a.numero_affaire,
            a.client_nom or "",
            a.repere or "",
            a.type_echangeur or "",
            a.statut.label,
            a.annee,
            a.cree_par.full_name if a.cree_par else "",
            a.created_at.strftime("%d/%m/%Y") if a.created_at else "",
        ])

    content = out.getvalue().encode("utf-8-sig")
    response = make_response(content)
    response.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
    response.headers["Content-Disposition"] = "attachment; filename=\"affaires.csv\""
    return response


# ────────────────────────────────────────────────────────────────────────
# Wizard de création d'affaire (Q1 → Q4 — V1.2)
# ────────────────────────────────────────────────────────────────────────


@bp.route("/wizard/start", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_WIZARD_ROLES)
def wizard_start() -> Response:
    """Crée une nouvelle affaire en WIZARD_BROUILLON et redirige vers Q1.

    Le n° d'affaire n'est pas encore connu : il sera choisi en Q1 dans le
    registre BE (ou saisi manuellement).
    """
    annee = datetime.now().year
    affaire = affaire_svc.start_wizard(user=_current_user(), annee=annee)
    flash("Affaire créée. Étape 1/4 — Affaire.", "success")
    return redirect(
        url_for("affaires.wizard_step", affaire_id=affaire.id, step="Q1")
    )


@bp.route("/registre-be/items")
@login_required  # type: ignore[untyped-decorator]
@role_required(*_WIZARD_ROLES)
def registre_be_items() -> Response:
    """Liste JSON des items du registre BE pour un n° d'affaire (JS de Q1).

    Query string : ``numero_affaire`` (ex: ``BN0811``).
    """
    numero_affaire = (request.args.get("numero_affaire") or "").strip().upper()
    if not numero_affaire or numero_affaire == NUMERO_AFFAIRE_MANUEL:
        return jsonify({"items": []})

    items = registre_be_svc.list_items_for_numero(numero_affaire)
    return jsonify(
        {
            "items": [
                {
                    "item": i.item,
                    "label": i.label,
                    "client_nom": i.client_nom,
                    "annee": i.annee,
                    "repere": i.repere_client,
                    "type_appareil": i.type_appareil,
                    "nombre": i.nombre,
                }
                for i in items
            ]
        }
    )


@bp.route("/<int:affaire_id>/wizard/<step>", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_WIZARD_ROLES)
def wizard_step(affaire_id: int, step: str) -> str | Response | tuple[str, int]:
    """Affiche / traite une étape Q1-Q4 du wizard (V1.2).

    Les étapes déjà franchies restent navigables (stepper cliquable) ; seule
    une étape pas encore atteinte redirige vers l'étape max. Validation,
    persistance via le service, redirection vers l'étape suivante.
    """
    affaire = _get_wizard_affaire(affaire_id)
    current_step = _parse_step(step)

    # Empêche un saut en avant vers une étape pas encore atteinte.
    if affaire.statut_wizard is None or current_step.numero > affaire.statut_wizard.numero:
        flash("Étape non encore atteinte — reprenez depuis l'étape courante.", "warning")
        return redirect(
            url_for(
                "affaires.wizard_step",
                affaire_id=affaire.id,
                step=(affaire.statut_wizard or StatutWizard.Q1).value,
            )
        )

    form_class = _WIZARD_FORMS[current_step]
    form = form_class(data=_prefill(affaire, current_step))

    if current_step is StatutWizard.Q1:
        form.numero_affaire.choices = _numero_affaire_choices()
    elif current_step is StatutWizard.Q2:
        form.type_equipement_id.choices = _type_equipement_choices()
        form.item.choices = _item_choices(affaire)

    if form.validate_on_submit():
        next_step: StatutWizard | None
        if current_step is StatutWizard.Q4:
            affaire_svc.finish_wizard(
                affaire,
                user=_current_user(),
                commentaire=form.commentaire.data,
            )
            flash(
                f"Dossier {affaire.references_internes} créé — complétez la fiche "
                "technique quand vous le souhaitez.",
                "success",
            )
            return redirect(url_for("affaires.show", affaire_id=affaire.id))

        if current_step is StatutWizard.Q1:
            numero_affaire = _resolve_numero_affaire(form)
            next_step = affaire_svc.resolve_q1_affaire(
                affaire,
                annee=form.annee.data,
                numero_affaire=numero_affaire,
                client_nom=form.client_nom.data,
                references_client=form.references_client.data or None,
                user=_current_user(),
            )
        elif current_step is StatutWizard.Q2:
            resolution = _resolve_q2(form, affaire)
            if resolution is None:
                return _render_wizard(affaire, form, current_step)
            item, registre_item = resolution
            payload = _form_payload(form)
            payload.pop("item", None)
            payload["type_equipement_id"] = int(form.type_equipement_id.data)
            next_step = affaire_svc.resolve_q2_item(
                affaire,
                item=item,
                registre_item=registre_item,
                payload=payload,
                user=_current_user(),
            )
        else:  # Q3 — Réglementation
            payload = _form_payload(form)
            if not payload.get("desp"):
                # Hors DESP, catégorie et module sont sans objet.
                payload["categorie_ped"] = ""
                payload["module_ped"] = ""
            next_step = affaire_svc.save_step(
                affaire,
                current_step,
                payload,
                user=_current_user(),
            )
        return redirect(
            url_for(
                "affaires.wizard_step",
                affaire_id=affaire.id,
                step=(next_step or StatutWizard.Q4).value,
            )
        )

    return _render_wizard(affaire, form, current_step)


# ── Helpers ──────────────────────────────────────────────────────────────


def _current_user() -> User:
    """Cast typé de ``current_user`` (Flask-Login proxy)."""
    return current_user._get_current_object()  # type: ignore[no-any-return]


def _get_wizard_affaire(affaire_id: int) -> Affaire:
    """Récupère une affaire en cours de wizard ou abort 404."""
    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        abort(404)
    if affaire.statut is not Statut.WIZARD_BROUILLON:
        abort(404)
    return affaire


def _parse_step(step_value: str) -> StatutWizard:
    """Convertit une valeur d'URL ``"Q3"`` en ``StatutWizard.Q3`` ou abort 404."""
    try:
        return StatutWizard(step_value.upper())
    except ValueError:
        abort(404)


def _render_wizard(affaire: Affaire, form: object, step: StatutWizard) -> str:
    """Rend le template du wizard avec le contexte commun (stepper, modules)."""
    return render_template(
        "affaires/wizard.html",
        affaire=affaire,
        form=form,
        step=step,
        steps=list(StatutWizard),
        max_step=affaire.statut_wizard or StatutWizard.Q1,
        ped_modules=MODULES_PED,
        ped_modules_par_cat=MODULES_PAR_CATEGORIE,
        ped_modules_sup_par_cat=MODULES_SUPERIEURS_PAR_CATEGORIE,
        numeros_clients=_numeros_clients() if step is StatutWizard.Q1 else {},
    )


def _prefill(affaire: Affaire, step: StatutWizard) -> dict[str, object]:
    """Pré-remplit le formulaire d'une étape avec les valeurs déjà saisies.

    L'étape Réglementation (Q3) est de plus préremplie depuis les colonnes
    R/S/T du registre BE (import Lot 0) tant qu'elle n'a jamais été
    enregistrée pour ce dossier.
    """
    data: dict[str, object] = {}

    if step is StatutWizard.Q1:
        data = {
            "annee": affaire.annee,
            "client_nom": affaire.client_nom,
            "references_client": affaire.references_client,
        }
        if affaire.numero_affaire:
            if registre_be_svc.list_items_for_numero(affaire.numero_affaire):
                data["numero_affaire"] = affaire.numero_affaire
            else:
                data["numero_affaire"] = NUMERO_AFFAIRE_MANUEL
                data["numero_affaire_manuel"] = affaire.numero_affaire
    elif step is StatutWizard.Q2:
        data = {
            "item": affaire.item,
            "repere": affaire.repere,
            "type_echangeur": affaire.type_echangeur,
            "nombre": affaire.nombre,
            "annee_construction": affaire.annee_construction,
        }
        if affaire.type_equipement_id is not None:
            data["type_equipement_id"] = str(affaire.type_equipement_id)
    elif step is StatutWizard.Q3:
        reponses = (
            (affaire.parametrage.reponses or {}) if affaire.parametrage else {}
        )
        if "q4_desp" in reponses:
            # Déjà enregistrée : relecture des clés JSONB (contrat D2).
            data = {
                "desp": reponses.get("q4_desp"),
                "stamp_u": reponses.get("q4_stamp_u"),
                "categorie_ped": reponses.get("q4_categorie_ped") or "",
                "module_ped": reponses.get("q4_module_ped") or "",
            }
        else:
            data = _prefill_reglementation_registre(affaire)

    return data


def _prefill_reglementation_registre(affaire: Affaire) -> dict[str, object]:
    """Préremplit la réglementation depuis les colonnes R/S/T du registre BE.

    Les valeurs historiques non mappables (modules 97/23 « A1 », « B1+F »…)
    sont ignorées : l'utilisateur choisit alors lui-même.
    """
    if not (affaire.numero_affaire and affaire.item):
        return {}
    registre_item = registre_be_svc.get_item(affaire.numero_affaire, affaire.item)
    if registre_item is None:
        return {}

    data: dict[str, object] = {
        "desp": registre_item.desp,
        "stamp_u": registre_item.stamp_u,
    }
    categorie = _REGISTRE_CATEGORIES.get((registre_item.categorie_risque or "").strip())
    if categorie:
        data["categorie_ped"] = categorie
    module = (registre_item.module_evaluation or "").strip()
    if module in MODULES_PED:
        data["module_ped"] = module
    return data


def _form_payload(form: object) -> dict[str, object]:
    """Extrait les champs du formulaire (hors CSRF/submit) sous forme de dict."""
    skipped = {"csrf_token", "submit"}
    return {
        name: field.data
        for name, field in form._fields.items()  # type: ignore[attr-defined]
        if name not in skipped
    }


def _numero_affaire_choices() -> list[tuple[str, str]]:
    """Choix du ``SelectField`` n° d'affaire : registre BE + saisie manuelle."""
    rows = registre_be_svc.list_numeros_affaire()
    choices = [("", "— Sélectionner —")]
    choices += [
        (
            row["numero_affaire"],
            f"{row['numero_affaire']} — {row['client_nom'] or '?'} "
            f"({row['nb_items']} item{'s' if row['nb_items'] > 1 else ''})",
        )
        for row in rows
    ]
    choices.append((NUMERO_AFFAIRE_MANUEL, "Saisie manuelle (affaire non répertoriée)"))
    return choices


def _numeros_clients() -> dict[str, str]:
    """Dict ``{n° affaire: client}`` pour le préremplissage JS du client (Q1)."""
    return {
        row["numero_affaire"]: row["client_nom"] or ""
        for row in registre_be_svc.list_numeros_affaire()
    }


def _type_equipement_choices() -> list[tuple[str, str]]:
    """Choix du ``SelectField`` type d'équipement (référentiel actif, D7)."""
    types = (
        db.session.query(TypeEquipement)
        .filter_by(actif=True)
        .order_by(TypeEquipement.ordre, TypeEquipement.libelle)
        .all()
    )
    return [("", "— Sélectionner —")] + [(str(t.id), t.libelle) for t in types]


def _item_choices(affaire: Affaire) -> list[tuple[str, str]]:
    """Choix initiaux du ``SelectField`` item pour le n° d'affaire du dossier.

    Servent au rendu sans JS et au préremplissage de l'item déjà choisi ; la
    liste est rafraîchie côté client via ``/affaires/registre-be/items``.
    """
    if not affaire.numero_affaire:
        return [("", "— Sélectionner —")]
    items = registre_be_svc.list_items_for_numero(affaire.numero_affaire)
    if not items:
        return [("", "— Saisie manuelle (affaire hors registre) —")]
    return [("", "— Sélectionner —")] + [(i.item, i.label) for i in items]


def _resolve_numero_affaire(form: WizardQ1Form) -> str:
    """N° d'affaire retenu à Q1 (sélection registre ou saisie manuelle)."""
    if form.numero_affaire.data == NUMERO_AFFAIRE_MANUEL:
        return (form.numero_affaire_manuel.data or "").upper()
    return form.numero_affaire.data  # type: ignore[no-any-return]


def _resolve_q2(
    form: WizardQ2Form, affaire: Affaire
) -> tuple[str, RegistreBEItem | None] | None:
    """Résout la sélection d'item Q2 en mode registre ou manuel.

    En mode registre (le n° d'affaire du dossier a des items au registre),
    l'item doit exister au registre. En mode manuel (affaire hors registre),
    l'item est saisi librement (format déjà validé par le formulaire).

    Returns:
        ``(item, registre_item)`` — ``registre_item`` vaut ``None`` en mode
        manuel — ou ``None`` si la sélection est invalide (un ``flash``
        d'erreur a alors été émis).
    """
    item = form.item.data or ""
    numero_affaire = affaire.numero_affaire or ""

    registre_item = registre_be_svc.get_item(numero_affaire, item)
    if registre_item is None and registre_be_svc.list_items_for_numero(numero_affaire):
        flash(
            "Cet item n'est pas reconnu pour ce n° d'affaire — "
            "réessayez la sélection.",
            "danger",
        )
        return None

    clash = (
        db.session.query(Affaire)
        .filter(
            Affaire.numero_affaire == numero_affaire,
            Affaire.item == item,
            Affaire.id != affaire.id,
        )
        .first()
    )
    if clash is not None:
        flash(
            f"Un dossier {numero_affaire}-{item} existe déjà — vérifiez le n° d'item.",
            "danger",
        )
        return None

    return item, registre_item
