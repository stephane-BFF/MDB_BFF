"""Commande ``flask seed`` — initialise les données de référence MDB BFF.

Crée :
    - 5 utilisateurs BFF (un par rôle), mot de passe initial ``BFF-init-2026!``.
    - 1 ``FormulaireTemplate`` pilote ``HYDR v1`` (chapitre E).
    - Trace les créations dans ``audit_trail`` (action ``"seed.created"``).

La commande est **idempotente** : un second appel ne duplique pas les lignes.
Pour la prod, utiliser ``flask seed --force`` n'est pas requis — les `INSERT`
sont gardés par un `SELECT` préalable sur les clés uniques.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import click
from flask import current_app
from flask.cli import with_appcontext

from app.enums import Chapitre, Role
from app.extensions import db
from app.models.audit import AuditTrail
from app.models.formulaire import FormulaireTemplate
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
    ("lecteur@bff.fr", "Lecteur", "BFF", Role.LECTEUR),
    ("redacteur@bff.fr", "Rédacteur", "BFF", Role.REDACTEUR),
    ("verificateur@bff.fr", "Vérificateur", "BFF", Role.VERIFICATEUR),
    ("approbateur@bff.fr", "Approbateur", "BFF", Role.APPROBATEUR),
    ("admin@bff.fr", "Admin", "BFF", Role.ADMIN),
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
    db.session.commit()

    click.echo(f"[OK] {created_users} utilisateurs crees (deja presents ignores).")
    click.echo(f"[OK] {created_templates} templates de formulaire crees.")
    click.echo(f"     Mot de passe initial : {_SEED_PASSWORD!r} (a changer au 1er login).")
    current_app.logger.info(
        "seed completed",
        extra={"users": created_users, "templates": created_templates},
    )


def _seed_users() -> int:
    """Crée les 5 utilisateurs BFF. Retourne le nombre de créations effectives."""
    created = 0
    for email, prenom, nom, role in _SEED_USERS:
        if db.session.query(User).filter_by(email=email).first() is not None:
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
