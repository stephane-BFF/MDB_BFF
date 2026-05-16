"""Configuration pytest — fixtures partagées pour tous les tests MDB BFF."""
from __future__ import annotations

from collections.abc import Generator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.enums import Chapitre, Role, Statut
from app.extensions import db as _db
from app.models.affaire import Affaire, ParametrageAffaire
from app.models.formulaire import FormulaireTemplate
from app.models.user import User


# ── App & DB ──────────────────────────────────────────────────────────────


@pytest.fixture()
def app() -> Generator[Flask, None, None]:
    """Flask app avec SQLite in-memory, base de données fraîche par test."""
    _app = create_app("testing")
    with _app.app_context():
        _db.create_all()
        _seed_formulaire_templates()
        yield _app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app: Flask) -> type[_db]:  # type: ignore[valid-type]
    """Accès direct à l'objet db Flask-SQLAlchemy (déjà initialisé par `app`)."""
    return _db


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Client HTTP non authentifié."""
    return app.test_client()


# ── Users ─────────────────────────────────────────────────────────────────


def _make_user(
    email: str,
    prenom: str,
    nom: str,
    role: Role,
    password: str = "Test1234!",
) -> User:
    user = User(email=email, prenom=prenom, nom=nom, role=role, actif=True)
    user.set_password(password)
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture()
def user_redacteur(app: Flask) -> User:  # noqa: ARG001
    return _make_user("redacteur@bff.fr", "Rémi", "Rédacteur", Role.REDACTEUR)


@pytest.fixture()
def user_verificateur(app: Flask) -> User:  # noqa: ARG001
    return _make_user("verificateur@bff.fr", "Véra", "Vérificateur", Role.VERIFICATEUR)


@pytest.fixture()
def user_approbateur(app: Flask) -> User:  # noqa: ARG001
    return _make_user("approbateur@bff.fr", "Alain", "Approbateur", Role.APPROBATEUR)


# ── Authenticated clients ─────────────────────────────────────────────────


def _login(client: FlaskClient, email: str, password: str = "Test1234!") -> None:
    """Connecte un utilisateur via la route /auth/login."""
    resp = client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert resp.status_code == 302, (
        f"Échec de login pour {email!r} : HTTP {resp.status_code}. "
        "Vérifiez que l'utilisateur existe et que le mot de passe est correct."
    )


@pytest.fixture()
def client_redacteur(client: FlaskClient, user_redacteur: User) -> FlaskClient:
    """Client HTTP authentifié en tant que Rédacteur."""
    _login(client, user_redacteur.email)
    return client


@pytest.fixture()
def client_verificateur(client: FlaskClient, user_verificateur: User) -> FlaskClient:
    """Client HTTP authentifié en tant que Vérificateur."""
    _login(client, user_verificateur.email)
    return client


@pytest.fixture()
def client_approbateur(client: FlaskClient, user_approbateur: User) -> FlaskClient:
    """Client HTTP authentifié en tant qu'Approbateur."""
    _login(client, user_approbateur.email)
    return client


# ── Affaire ───────────────────────────────────────────────────────────────


@pytest.fixture()
def affaire(app: Flask, user_redacteur: User) -> Affaire:  # noqa: ARG001
    """Affaire BN2026-001 en statut BROUILLON, paramétrage q5_ps_bar=10.0."""
    a = Affaire(
        numero_affaire="BN2026-001",
        annee=2026,
        client_nom="Client Test",
        references_client="REF-001",
        references_internes="INT-001",
        repere="TEST-REP",
        type_echangeur="H1",
        nombre=1,
        annee_construction=2026,
        statut=Statut.BROUILLON,
        cree_par_id=user_redacteur.id,
    )
    _db.session.add(a)
    _db.session.flush()
    p = ParametrageAffaire(
        affaire_id=a.id,
        reponses={"q5_ps_bar": 10.0},
        template_version=1,
    )
    _db.session.add(p)
    _db.session.commit()
    return a


# ── Seeds ─────────────────────────────────────────────────────────────────


def _seed_formulaire_templates() -> None:
    """Insère les templates de tous les formulaires implémentés."""
    _TEMPLATES = [
        (Chapitre.E, "HYDR",        "Procès-verbal d'épreuve hydrostatique",        "Hydrostatic test report"),
        (Chapitre.F, "VISUFINAL",   "Procès-verbal de contrôle visuel final",        "Final visual inspection report"),
        (Chapitre.F, "PROPRETE",    "Procès-verbal de contrôle de propreté",         "Cleanliness inspection report"),
        (Chapitre.F, "SECHAGE",     "Procès-verbal de séchage",                      "Drying record"),
        (Chapitre.F, "PESAGE",      "Procès-verbal de pesage",                       "Weighing record"),
        (Chapitre.A, "CONFCOM",     "Conformité commerciale",                        "Commercial conformity"),
        (Chapitre.A, "ATTDECR",     "Attestation de conformité directive",           "Directive conformity declaration"),
        (Chapitre.A, "ATTREP",      "Attestation du représentant habilité",          "Authorized representative declaration"),
        (Chapitre.A, "ETATDESC",    "État descriptif de l'équipement",               "Equipment descriptive record"),
        (Chapitre.E, "AIRSAV",      "Procès-verbal de test air-savon",               "Soap bubble leak test report"),
        (Chapitre.E, "RECORDHYDRO", "Enregistrement continu — épreuve hydrostatique", "Hydrostatic test continuous record"),
        (Chapitre.E, "AZOTE",       "Procès-verbal de mise sous azote",              "Nitrogen pressurization record"),
        (Chapitre.C, "TTH1",        "PV de traitement thermique — opération 1",       "Heat treatment record — operation 1"),
        (Chapitre.C, "TTH2",        "PV de traitement thermique — opération 2",       "Heat treatment record — operation 2"),
        (Chapitre.B, "BIM",         "Bordereau d'identification des matériaux de base", "Bill of material — base materials"),
        (Chapitre.B, "BIMSOUD",     "Bordereau d'identification des matériaux de soudage", "Bill of material — welding consumables"),
        (Chapitre.B, "PMI",         "Rapport de contrôle PMI",                       "Positive material identification report"),
        (Chapitre.C, "LISTSOUD",    "Liste des soudeurs qualifiés",                  "Qualified welders list"),
        (Chapitre.C, "ROLLING",     "Procès-verbal de dudgeonnage",                  "Tube rolling / expansion record"),
        (Chapitre.C, "DIM",         "Procès-verbal de contrôle dimensionnel",        "Dimensional inspection record"),
        (Chapitre.D, "LISTCND",     "Liste des contrôleurs CND certifiés",           "Certified NDT operators list"),
        (Chapitre.D, "NDEMAP",      "Carte des contrôles non destructifs",           "Non-destructive testing map"),
        (Chapitre.D, "DURETE",      "Procès-verbal de contrôle de dureté",           "Hardness test record"),
        (Chapitre.D, "FERRITE",     "Procès-verbal de contrôle de ferrite",          "Delta ferrite content record"),
        (Chapitre.D, "UT0FAIS",     "Mesures d'épaisseur initiale — Faisceau",       "Initial thickness — Tube bundle"),
        (Chapitre.D, "UT0SHELL",    "Mesures d'épaisseur initiale — Calandre",       "Initial thickness — Shell"),
        (Chapitre.D, "UT0RET",      "Mesures d'épaisseur initiale — Retour",         "Initial thickness — Return"),
        (Chapitre.D, "UT0UBEND",    "Mesures d'épaisseur initiale — U-coudes",       "Initial thickness — U-bend"),
        (Chapitre.G, "PEDMOD",      "Déclaration UE de conformité (modules PED)",     "EU Declaration of Conformity (PED modules)"),
    ]
    for chapitre, code, libelle, libelle_en in _TEMPLATES:
        _db.session.add(
            FormulaireTemplate(
                code=code,
                version=1,
                chapitre=chapitre,
                libelle=libelle,
                libelle_en=libelle_en,
                schema={},
                actif=True,
            )
        )
    _db.session.commit()
