"""Commande ``flask seed`` — initialise les données de référence MDB BFF.

Crée :
    - 7 utilisateurs BFF (équipe qualité réelle), mot de passe initial ``BFF-init-2026!``.
    - Les templates ``FormulaireTemplate`` pour les 27 formulaires (chapitre A–G).
    - Trace les créations dans ``audit_trail`` (action ``"seed.created"``).

La commande est **idempotente** : un second appel ne duplique pas les lignes.
Pour la prod, utiliser ``flask seed --force`` n'est pas requis — les `INSERT`
sont gardés par un `SELECT` préalable sur les clés uniques.

Équipe BFF :
    - Stéphane PAUMELLE  <stephane.paumelle@ait-stein.com>  — Admin (Directeur pôle décarbonation)
    - Brice GIRARD       <brice.girard@bffrance.com>         — Approbateur (Responsable QC)
    - Vincent VAUTHIER   <vincent.vauthier@bffrance.com>     — Approbateur (Inspecteur QC, CND niv II Cofrend + niv III ASNT)
    - Loïc CUVELIER      <loic.cuvelier@bffrance.com>        — Vérificateur (Contrôleur CND niv II Cofrend + ASNT)
    - Paul BRITO         <paul.brito@bffrance.com>           — Vérificateur (Inspecteur QC)
    - Florence MARQUE    <florence.marque@bffrance.com>      — Vérificateur (Inspecteur QC)
    - Corentin DUVAL-ARNOULD <corentin.duval-arnould@bffrance.com> — Rédacteur (Responsable production et soudage)

Tous les e-mails de seed sont normalisés en minuscules : les logins sont
insensibles à la casse (``ldap_auth._find_user`` compare via ``func.lower``),
mais la donnée stockée doit rester cohérente avec l'identifiant réel de
l'utilisateur pour éviter toute confusion en base ou dans les exports.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import click
from flask import current_app
from flask.cli import with_appcontext

from app.cli.data_metaux_apport import METAUX_APPORT
from app.cli.data_organismes_notifies import ORGANISMES_NOTIFIES
from app.cli.data_soudeurs import SOUDEURS
from app.enums import Chapitre, Role
from app.extensions import db
from app.models.audit import AuditTrail
from app.models.formulaire import FormulaireTemplate
from app.models.referentiel import MetalApport, OrganismeNotifie, Soudeur
from app.models.user import User


@dataclass(frozen=True)
class _TemplateSpec:
    """Spec typée d'un template de formulaire pour le seed initial."""

    code: str
    version: int
    chapitre: Chapitre
    libelle: str
    libelle_en: str | None
    schema: dict[str, Any]

_SEED_PASSWORD = "BFF-init-2026!"  # noqa: S105 — placeholder de seed, à changer au 1er login

_SEED_USERS: tuple[tuple[str, str, str, Role], ...] = (
    ("stephane.paumelle@ait-stein.com", "Stéphane", "PAUMELLE", Role.ADMIN),
    ("brice.girard@bffrance.com", "Brice", "GIRARD", Role.APPROBATEUR),
    ("vincent.vauthier@bffrance.com", "Vincent", "VAUTHIER", Role.APPROBATEUR),
    ("loic.cuvelier@bffrance.com", "Loïc", "CUVELIER", Role.VERIFICATEUR),
    ("paul.brito@bffrance.com", "Paul", "BRITO", Role.VERIFICATEUR),
    ("florence.marque@bffrance.com", "Florence", "MARQUE", Role.VERIFICATEUR),
    ("corentin.duval-arnould@bffrance.com", "Corentin", "DUVAL-ARNOULD", Role.REDACTEUR),
)

_SEED_TEMPLATES: tuple[_TemplateSpec, ...] = (
    _TemplateSpec(
        code="HYDR",
        version=1,
        chapitre=Chapitre.E,
        libelle="Procès-verbal d'épreuve hydrostatique",
        libelle_en="Hydrostatic test record",
        schema={
            "type": "object",
            "properties": {
                "ps": {"type": "number", "description": "Pression de service (bar)"},
                "pt": {"type": "number", "description": "Pression d'épreuve PT = PS × 1.43 (bar)"},
                "temperature_C": {"type": "number"},
                "duree_minutes": {"type": "integer", "minimum": 30},
                "fluide": {"type": "string", "enum": ["eau", "huile"]},
                "observations": {"type": "string"},
            },
            "required": ["ps", "pt", "fluide"],
        },
    ),
    _TemplateSpec(
        code="VISUFINAL",
        version=1,
        chapitre=Chapitre.F,
        libelle="Contrôle visuel final",
        libelle_en="Final visual inspection",
        schema={},
    ),
    _TemplateSpec(
        code="PROPRETE",
        version=1,
        chapitre=Chapitre.F,
        libelle="Contrôle propreté",
        libelle_en="Cleanliness inspection",
        schema={},
    ),
    _TemplateSpec(
        code="SECHAGE",
        version=1,
        chapitre=Chapitre.F,
        libelle="Séchage",
        libelle_en="Drying record",
        schema={},
    ),
    _TemplateSpec(
        code="PESAGE",
        version=1,
        chapitre=Chapitre.F,
        libelle="Pesage",
        libelle_en="Weighing record",
        schema={},
    ),
    _TemplateSpec(
        code="CONFCOM",
        version=1,
        chapitre=Chapitre.A,
        libelle="Conformité commerciale",
        libelle_en="Commercial conformity",
        schema={},
    ),
    _TemplateSpec(
        code="ATTDECR",
        version=1,
        chapitre=Chapitre.A,
        libelle="Attestation de conformité directive",
        libelle_en="Directive conformity declaration",
        schema={},
    ),
    _TemplateSpec(
        code="ATTREP",
        version=1,
        chapitre=Chapitre.A,
        libelle="Attestation du représentant habilité",
        libelle_en="Authorized representative declaration",
        schema={},
    ),
    _TemplateSpec(
        code="ETATDESC",
        version=1,
        chapitre=Chapitre.A,
        libelle="État descriptif de l'équipement",
        libelle_en="Equipment descriptive record",
        schema={},
    ),
    _TemplateSpec(
        code="AIRSAV",
        version=1,
        chapitre=Chapitre.E,
        libelle="Procès-verbal de test air-savon",
        libelle_en="Soap bubble leak test report",
        schema={},
    ),
    _TemplateSpec(
        code="RECORDHYDRO",
        version=1,
        chapitre=Chapitre.E,
        libelle="Enregistrement continu — épreuve hydrostatique",
        libelle_en="Hydrostatic test continuous record",
        schema={},
    ),
    _TemplateSpec(
        code="AZOTE",
        version=1,
        chapitre=Chapitre.E,
        libelle="Procès-verbal de mise sous azote",
        libelle_en="Nitrogen pressurization record",
        schema={},
    ),
    _TemplateSpec(
        code="TTH1",
        version=1,
        chapitre=Chapitre.C,
        libelle="Procès-verbal de traitement thermique — opération 1",
        libelle_en="Heat treatment record — operation 1",
        schema={},
    ),
    _TemplateSpec(
        code="TTH2",
        version=1,
        chapitre=Chapitre.C,
        libelle="Procès-verbal de traitement thermique — opération 2",
        libelle_en="Heat treatment record — operation 2",
        schema={},
    ),
    _TemplateSpec(
        code="BIM",
        version=1,
        chapitre=Chapitre.B,
        libelle="Bordereau d'identification des matériaux de base",
        libelle_en="Bill of material — base materials",
        schema={},
    ),
    _TemplateSpec(
        code="BIMSOUD",
        version=1,
        chapitre=Chapitre.B,
        libelle="Bordereau d'identification des matériaux de soudage",
        libelle_en="Bill of material — welding consumables",
        schema={},
    ),
    _TemplateSpec(
        code="PMI",
        version=1,
        chapitre=Chapitre.B,
        libelle="Rapport de contrôle PMI",
        libelle_en="Positive material identification report",
        schema={},
    ),
    _TemplateSpec(
        code="LISTSOUD",
        version=1,
        chapitre=Chapitre.C,
        libelle="Liste des soudeurs qualifiés",
        libelle_en="Qualified welders list",
        schema={},
    ),
    _TemplateSpec(
        code="ROLLING",
        version=1,
        chapitre=Chapitre.C,
        libelle="Procès-verbal de dudgeonnage",
        libelle_en="Tube rolling / expansion record",
        schema={},
    ),
    _TemplateSpec(
        code="DIM",
        version=1,
        chapitre=Chapitre.C,
        libelle="Procès-verbal de contrôle dimensionnel",
        libelle_en="Dimensional inspection record",
        schema={},
    ),
    _TemplateSpec(
        code="LISTCND",
        version=1,
        chapitre=Chapitre.D,
        libelle="Liste des contrôleurs CND certifiés",
        libelle_en="Certified NDT operators list",
        schema={},
    ),
    _TemplateSpec(
        code="NDEMAP",
        version=1,
        chapitre=Chapitre.D,
        libelle="Carte des contrôles non destructifs",
        libelle_en="Non-destructive testing map",
        schema={},
    ),
    _TemplateSpec(
        code="DURETE",
        version=1,
        chapitre=Chapitre.D,
        libelle="Procès-verbal de contrôle de dureté",
        libelle_en="Hardness test record",
        schema={},
    ),
    _TemplateSpec(
        code="FERRITE",
        version=1,
        chapitre=Chapitre.D,
        libelle="Procès-verbal de contrôle de teneur en ferrite",
        libelle_en="Delta ferrite content inspection record",
        schema={},
    ),
    _TemplateSpec(
        code="UT0FAIS",
        version=1,
        chapitre=Chapitre.D,
        libelle="Mesures d'épaisseur initiale — Zone faisceau",
        libelle_en="Initial thickness measurements — Tube bundle zone",
        schema={},
    ),
    _TemplateSpec(
        code="UT0SHELL",
        version=1,
        chapitre=Chapitre.D,
        libelle="Mesures d'épaisseur initiale — Zone calandre",
        libelle_en="Initial thickness measurements — Shell zone",
        schema={},
    ),
    _TemplateSpec(
        code="UT0RET",
        version=1,
        chapitre=Chapitre.D,
        libelle="Mesures d'épaisseur initiale — Zone retour",
        libelle_en="Initial thickness measurements — Return zone",
        schema={},
    ),
    _TemplateSpec(
        code="UT0UBEND",
        version=1,
        chapitre=Chapitre.D,
        libelle="Mesures d'épaisseur initiale — Zone U-coudes",
        libelle_en="Initial thickness measurements — U-bend zone",
        schema={},
    ),
    _TemplateSpec(
        code="PEDMOD",
        version=1,
        chapitre=Chapitre.G,
        libelle="Déclaration UE de conformité (modules PED)",
        libelle_en="EU Declaration of Conformity (PED modules)",
        schema={},
    ),
)


@click.command("seed")
@with_appcontext
def seed_command() -> None:
    """Initialise les utilisateurs et templates de base."""
    created_users = _seed_users()
    created_templates = _seed_templates()
    created_metaux = _seed_metaux_apport()
    created_soudeurs = _seed_soudeurs()
    created_on = _seed_organismes_notifies()
    db.session.commit()

    click.echo(f"[OK] {created_users} utilisateur(s) cree(s) (deja presents ignores).")
    click.echo(f"[OK] {created_templates} templates de formulaire crees.")
    click.echo(f"[OK] {created_metaux} metal(aux) d'apport cree(s) (referentiel BIMSOUD).")
    click.echo(f"[OK] {created_soudeurs} soudeur(s) cree(s) (referentiel LISTSOUD).")
    click.echo(f"[OK] {created_on} organisme(s) notifie(s) cree(s) (referentiel ATTDECR).")
    click.echo(f"     Mot de passe initial : {_SEED_PASSWORD!r} (a changer au 1er login).")
    current_app.logger.info(
        "seed completed",
        extra={
            "users": created_users,
            "templates": created_templates,
            "metaux_apport": created_metaux,
            "soudeurs": created_soudeurs,
            "organismes_notifies": created_on,
        },
    )


def _seed_users() -> int:
    """Crée les 7 utilisateurs de l'équipe BFF. Retourne le nombre de créations effectives.

    La recherche d'existence est insensible à la casse : si un compte a été
    créé lors d'un seed antérieur avec une casse différente de l'e-mail
    canonique (ex. ``Stephane.Paumelle@…``), il est retrouvé et sa casse est
    corrigée plutôt que de créer un doublon.
    """
    from sqlalchemy import func  # noqa: PLC0415

    created = 0
    for email, prenom, nom, role in _SEED_USERS:
        existing = (
            db.session.query(User).filter(func.lower(User.email) == email).first()
        )
        if existing is not None:
            if existing.email != email:
                existing.email = email
            continue
        u = User(email=email, prenom=prenom, nom=nom, role=role, actif=True)
        u.set_password(_SEED_PASSWORD)
        db.session.add(u)
        db.session.flush()
        AuditTrail.log(
            "seed.user_created",
            entity_type="user",
            entity_id=u.id,
            new_value=role,
            contexte={"email": email},
        )
        created += 1
    return created


def _seed_metaux_apport() -> int:
    """Crée le référentiel des métaux d'apport (BIMSOUD). Retourne le nombre de créations.

    Idempotent : la désignation est la clé naturelle ; une entrée déjà
    présente est ignorée (ses éventuelles corrections manuelles sont
    préservées).
    """
    created = 0
    for designation, classification, fournisseur in METAUX_APPORT:
        existing = (
            db.session.query(MetalApport)
            .filter_by(designation=designation)
            .first()
        )
        if existing is not None:
            continue
        db.session.add(
            MetalApport(
                designation=designation,
                classification=classification,
                fournisseur=fournisseur,
                actif=True,
            )
        )
        created += 1
    return created


def _seed_soudeurs() -> int:
    """Crée le référentiel des soudeurs (identité) pour LISTSOUD. Idempotent.

    La clé naturelle est le matricule s'il est renseigné, sinon le nom. Les
    corrections manuelles d'un soudeur déjà présent sont préservées.
    """
    created = 0
    for matricule, initiales, nom in SOUDEURS:
        existing = (
            db.session.query(Soudeur).filter_by(matricule=matricule).first()
            if matricule
            else db.session.query(Soudeur).filter_by(nom=nom).first()
        )
        if existing is not None:
            continue
        db.session.add(
            Soudeur(matricule=matricule or None, initiales=initiales or None, nom=nom, actif=True)
        )
        created += 1
    return created


def _seed_organismes_notifies() -> int:
    """Crée le référentiel des organismes notifiés (ATTDECR). Idempotent.

    La clé naturelle est le numéro NANDO. Les corrections manuelles d'un ON
    déjà présent sont préservées.
    """
    created = 0
    for numero, nom in ORGANISMES_NOTIFIES:
        existing = (
            db.session.query(OrganismeNotifie).filter_by(numero=numero).first()
        )
        if existing is not None:
            continue
        db.session.add(OrganismeNotifie(numero=numero, nom=nom, actif=True))
        created += 1
    return created


def _seed_templates() -> int:
    """Crée les templates de formulaire initiaux. Retourne le nombre de créations."""
    created = 0
    for spec in _SEED_TEMPLATES:
        existing = (
            db.session.query(FormulaireTemplate)
            .filter_by(code=spec.code, version=spec.version)
            .first()
        )
        if existing is not None:
            continue
        t = FormulaireTemplate(
            code=spec.code,
            version=spec.version,
            chapitre=spec.chapitre,
            libelle=spec.libelle,
            libelle_en=spec.libelle_en,
            schema=spec.schema,
        )
        db.session.add(t)
        db.session.flush()
        AuditTrail.log(
            "seed.template_created",
            entity_type="formulaire_template",
            entity_id=t.id,
            new_value=f"{spec.code} v{spec.version}",
        )
        created += 1
    return created
