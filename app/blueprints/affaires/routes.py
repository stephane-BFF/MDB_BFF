"""Routes du module Affaires — liste paginée + wizard de création Q1-Q8."""
from __future__ import annotations

from datetime import datetime

import csv
import io

from flask import abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload
from werkzeug.wrappers.response import Response

from app.blueprints.affaires import bp
from app.enums import Role, Statut, StatutWizard
from app.extensions import db
from app.forms.affaire import AffaireFilterForm
from app.forms.wizard import (
    WizardQ1Form,
    WizardQ2Form,
    WizardQ3Form,
    WizardQ4Form,
    WizardQ5Form,
    WizardQ6Form,
    WizardQ7Form,
    WizardQ8Form,
)
from app.models.affaire import Affaire
from app.models.user import User
from app.services import affaire as affaire_svc
from app.utils.decorators import role_required

# Nombre d'affaires par page — peut devenir paramétrable plus tard.
_PER_PAGE = 20

# Mapping étape → classe de formulaire et liste de champs sauvegardés.
_WIZARD_FORMS: dict[StatutWizard, type] = {
    StatutWizard.Q1: WizardQ1Form,
    StatutWizard.Q2: WizardQ2Form,
    StatutWizard.Q3: WizardQ3Form,
    StatutWizard.Q4: WizardQ4Form,
    StatutWizard.Q5: WizardQ5Form,
    StatutWizard.Q6: WizardQ6Form,
    StatutWizard.Q7: WizardQ7Form,
    StatutWizard.Q8: WizardQ8Form,
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
    writer.writerow(["Numéro", "Client", "Repère", "Type échangeur", "Statut", "Année", "Créé par", "Créé le"])
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
# Wizard de création d'affaire (Q1 → Q8)
# ────────────────────────────────────────────────────────────────────────


@bp.route("/wizard/start", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_WIZARD_ROLES)
def wizard_start() -> Response:
    """Crée une nouvelle affaire en WIZARD_BROUILLON et redirige vers Q1.

    Le numéro d'affaire est auto-généré pour l'année courante (modifiable en Q1).
    """
    annee = datetime.now().year
    affaire = affaire_svc.start_wizard(user=_current_user(), annee=annee)
    flash(f"Affaire {affaire.numero_affaire} créée. Étape 1/8.", "success")
    return redirect(
        url_for("affaires.wizard_step", affaire_id=affaire.id, step="Q1")
    )


@bp.route("/<int:affaire_id>/wizard/<step>", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_WIZARD_ROLES)
def wizard_step(affaire_id: int, step: str) -> str | Response | tuple[str, int]:
    """Affiche / traite une étape Q1-Q8 du wizard.

    Validation, persistance via le service, redirection vers la step suivante.
    """
    affaire = _get_wizard_affaire(affaire_id)
    current_step = _parse_step(step)

    # Empêche un saut d'étape en arrière (UX : utiliser le bouton "Précédent").
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

    if form.validate_on_submit():
        if current_step is StatutWizard.Q8:
            affaire_svc.finish_wizard(
                affaire,
                user=_current_user(),
                commentaire=form.commentaire.data,
            )
            flash(
                f"Affaire {affaire.numero_affaire} créée — passage en BROUILLON.",
                "success",
            )
            return redirect(url_for("affaires.index"))

        next_step = affaire_svc.save_step(
            affaire,
            current_step,
            _form_payload(form),
            user=_current_user(),
        )
        return redirect(
            url_for(
                "affaires.wizard_step",
                affaire_id=affaire.id,
                step=(next_step or StatutWizard.Q8).value,
            )
        )

    return render_template(
        "affaires/wizard.html",
        affaire=affaire,
        form=form,
        step=current_step,
        steps=list(StatutWizard),
    )


@bp.route("/<int:affaire_id>/wizard/back", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
@role_required(*_WIZARD_ROLES)
def wizard_back(affaire_id: int) -> Response:
    """Recule d'une étape (POST anti-CSRF)."""
    affaire = _get_wizard_affaire(affaire_id)
    prev = affaire_svc.go_back(affaire)
    return redirect(
        url_for(
            "affaires.wizard_step",
            affaire_id=affaire.id,
            step=(prev or StatutWizard.Q1).value,
        )
    )


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


def _prefill(affaire: Affaire, step: StatutWizard) -> dict[str, object]:
    """Pré-remplit le formulaire d'une étape avec les valeurs déjà saisies."""
    data: dict[str, object] = {}

    if step is StatutWizard.Q1:
        data = {
            "annee": affaire.annee,
            "numero_affaire": affaire.numero_affaire,
            "references_internes": affaire.references_internes,
        }
    elif step is StatutWizard.Q2:
        data = {
            "client_nom": affaire.client_nom,
            "references_client": affaire.references_client,
        }
    elif step is StatutWizard.Q3:
        data = {
            "repere": affaire.repere,
            "type_echangeur": affaire.type_echangeur,
            "nombre": affaire.nombre,
            "annee_construction": affaire.annee_construction,
        }
    elif step in (
        StatutWizard.Q4,
        StatutWizard.Q5,
        StatutWizard.Q6,
        StatutWizard.Q7,
    ):
        if affaire.parametrage is not None:
            prefix = f"{step.value.lower()}_"
            for key, value in (affaire.parametrage.reponses or {}).items():
                if key.startswith(prefix):
                    data[key.removeprefix(prefix)] = value

    return data


def _form_payload(form: object) -> dict[str, object]:
    """Extrait les champs du formulaire (hors CSRF/submit) sous forme de dict."""
    skipped = {"csrf_token", "submit"}
    return {
        name: field.data
        for name, field in form._fields.items()  # type: ignore[attr-defined]
        if name not in skipped
    }
