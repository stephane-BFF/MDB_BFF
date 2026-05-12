# MDB BFF — Dossier Constructeur Qualité (Application Web)

## Projet

Application web Flask/PostgreSQL pour gérer les **dossiers constructeurs qualité** de Brown Fintube France Energy (BFF), fabricant de réchauffeurs de masse industriels.

- ~100 affaires/an · **27 formulaires qualité** · chapitres **A–G** · jalons **JP0–JP6**
- Norme : Directive Équipements sous Pression (PED 2014/68/UE)
- Utilisateurs : 5 agents BFF — rôles : **Admin, Approbateur, Vérificateur, Rédacteur, Lecteur**
- Hébergement : NAS BFF réseau interne · URL cible `https://bff-mdb.local`
- CDC v1–v6 disponibles dans `../Cahier des charges/` — **lire avant tout développement**

## Stack Technique

- **Backend** : Python 3.14+, Flask 3.1+ (factory `create_app`), Flask-Login, Flask-WTF, SQLAlchemy 2.0+ typé
- **Base de données** : PostgreSQL + migrations Alembic
- **Config** : pydantic-settings (validation au démarrage)
- **Logging** : structlog (JSON structuré)
- **PDF synchrone** : WeasyPrint (formulaires individuels) + pypdf (assemblage)
- **PDF asynchrone** : Celery + Redis (dossiers complets Phase 2+)
- **I18n** : Flask-Babel + fichiers .po (FR/EN/DE/IT — Phase 2, avant les 16 templates PED)
- **Frontend** : Bootstrap 5, JavaScript vanilla — pas de npm, pas de bundler
- **Auth locale** : Werkzeug (`generate_password_hash` / `check_password_hash`)
- **Auth Windows/AD** : ldap3 — activable via `WINDOWS_AUTH_ENABLED=true`
- **Tests** : pytest + pytest-flask + pytest-cov (structure unit/ + integration/ dès Phase 1)
- **Qualité code** : ruff + black + mypy + pre-commit (configurés dans `pyproject.toml`)
- **WSGI Linux/NAS Synology** : Gunicorn · **WSGI Windows Server** : Waitress · **Dev** : `flask run`

## Architecture des fichiers

```text
app/
├── __init__.py          ← create_app factory
├── config.py            ← DevelopmentConfig, ProductionConfig, TestingConfig
├── extensions.py        ← db, login_manager, csrf, mail, migrate
├── celery_app.py        ← celery_init_app (PDF async)
├── enums.py             ← Role, Statut, Chapitre, JalonCode (Python Enum)
├── models/              ← SQLAlchemy 2.0 typé (DeclarativeBase + Mapped[type])
│   ├── base.py          ← DeclarativeBase + TimestampMixin
│   ├── user.py          ← User avec rôle Enum
│   ├── affaire.py       ← Affaire (statut WIZARD_BROUILLON → BROUILLON → …)
│   ├── formulaire.py    ← Formulaire GÉNÉRIQUE (data JSONB + template_version)
│   ├── jalon.py         ← Jalon, HoldPoint
│   ├── referentiel.py   ← Soudeur, OperateurCND, Materiau, Instrument
│   ├── signature.py     ← Signature avec hash SHA-256
│   └── audit.py         ← AuditTrail (insert only, jamais d'update)
├── blueprints/
│   ├── auth/            ← login local + LDAP Windows
│   ├── dashboard/       ← tableau de bord post-login
│   ├── affaires/        ← liste, wizard (persisté en base dès Q1), page affaire
│   ├── formulaires/     ← blueprint générique + overrides par code (hydr/, dim/…)
│   ├── jalons/          ← timeline JP0-JP6, Hold Points (Phase 4)
│   ├── referentiels/    ← CRUD référentiels (Phase 4)
│   ├── admin/           ← gestion utilisateurs, logs (Phase 5)
│   └── api/             ← REST /api/v1/ (flask-smorest Phase 4)
├── forms/               ← WTForms séparés des routes
│   ├── auth.py
│   ├── affaire.py
│   └── formulaires/     ← 1 fichier WTForms par formulaire métier
├── services/
│   ├── pdf/
│   │   ├── unitaire.py  ← WeasyPrint (formulaire → PDF)
│   │   ├── assemblage.py ← pypdf (dossier complet + signets)
│   │   └── tasks.py     ← tâches Celery
│   ├── network.py       ← sauvegarde chemin UNC NAS
│   ├── email.py         ← Flask-Mail (jalons, certifications)
│   ├── audit.py         ← audit_trail (insert only)
│   ├── ldap_auth.py     ← authentification LDAP/AD
│   └── formulaires/     ← logique métier par formulaire (hydr.py, dim.py…)
├── cli/                 ← commandes flask (seed, backup, export)
├── translations/        ← Flask-Babel .po/.mo (FR/EN/DE/IT)
├── templates/
│   ├── base.html
│   ├── components/      ← macros Jinja2 réutilisables
│   ├── pdf/             ← templates WeasyPrint par formulaire
│   └── {blueprint}/     ← auth/ dashboard/ affaires/ formulaires/ admin/
├── utils/
│   ├── decorators.py    ← @role_required
│   ├── validators.py    ← calculate_test_pressure, is_valid_numero_affaire
│   └── file_handler.py  ← validate_mime, build_network_path, save_file
└── static/              ← css/, js/, img/logo_bff.png
migrations/              ← fichiers Alembic (à committer)
tests/
├── conftest.py          ← app, client, db fixtures
├── unit/                ← tests services et utils
├── integration/         ← tests routes HTTP
└── fixtures/            ← données de test (users, affaires, formulaires)
docs/
scripts/                 ← maintenance ponctuelle
```

## Décisions architecturales clés (actées)

### Formulaires : table générique + JSONB (pas 27 tables)

Une seule table `formulaires` avec colonne `data JSONB` pour les champs spécifiques.
Colonnes indexées pour les champs réellement requêtés (statut, code, affaire_id).
Pour HYDR : property Python qui expose `ps`, `pt`, `conformite` depuis `data`.

```python
class Formulaire(db.Model):
    id, affaire_id, code, statut, chapitre   # colonnes communes + indexées
    data: Mapped[dict] = mapped_column(JSONB) # champs spécifiques du formulaire
    template_version: Mapped[int]             # versioning du schéma de champs
```

### Wizard affaire : persisté en base dès Q1

Statut `WIZARD_BROUILLON` créé dès la première étape, mis à jour à chaque étape.
Basculement vers `BROUILLON` à la fin du wizard. Zéro perte de données.

### Signatures : hash SHA-256 + audit immutable

- Hash SHA-256 du formulaire calculé au moment de la signature, stocké en base
- Vérification du hash à chaque affichage post-signature
- AuditTrail : **insert only**, jamais d'UPDATE sur les lignes existantes
- Phase 5 : 2FA TOTP (Google Authenticator) pour les approbateurs

### Versioning des formulaires

- Colonne `template_version` sur chaque formulaire
- Table `formulaire_templates` versionne les schémas de champs
- Affichage toujours fidèle au schéma de la version signée

### I18n PED : Flask-Babel + fichiers .po

Un seul template PED par module, traductions externalisées en `.po`.
Ajouter une langue = un fichier `.po`, pas un nouveau template HTML.

## Les 5 Rôles

| Rôle | Créer affaire | Saisir | Valider | Signer | Référentiels | Admin |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Lecteur** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Rédacteur** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Vérificateur** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Approbateur** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Les 27 Formulaires

| Chap. | Formulaires | Type |
| --- | --- | --- |
| A | PdG, CCC, ConfCom, AttDecr, AttRep, EtatDesc | Simples |
| B | BIM, BIMSoud, PMI | Tableaux dynamiques JS |
| C | ListSoud, Rolling, DIM, TTH1, TTH2 | Tableaux + upload fichier |
| D | ListCND, NDE_Map, Dureté, Ferrite, Point0×4 | Conditionnels |
| E | HYDR*, RecordHydro, AirSav, Azote | Calculs automatiques |
| F | VisuFinal, Proprete, Sechage, Pesage | Conditionnels simples |
| G | PED_module (4 modules × 4 langues via Flask-Babel) | Multi-langues |

**HYDR est le formulaire pilote** — pattern répliqué sur tous les autres.

## Règles Métier Critiques

- **Pression épreuve** : `PT = round(PS × 1.43, 1)` — JS temps réel + revalidation serveur
- **Workflow statuts** : `BROUILLON → SOUMIS → VALIDE → SIGNE` (irréversible sauf Admin)
- **Jalons** : un jalon ne peut être franchi que si tous ses prérequis sont VALIDE
- **Numéro d'affaire** : format `BN{AAAA}-{NNN}` (ex: BN2026-042)
- **Chemin réseau PDF** : `\\BFF-FICHIERS\Affaires\{annee}\{num_affaire}\MDB\`

## Conventions — NON NÉGOCIABLES

```python
# TOUJOURS : type hints + docstring sur les fonctions publiques
# TOUJOURS : SQLAlchemy 2.0 typé (DeclarativeBase + Mapped[type])
# TOUJOURS : Enums Python pour Role, Statut, Chapitre (pas de strings comparées)
# TOUJOURS : calculs métier dans services/ ou utils/, jamais dans les routes
# TOUJOURS : @role_required avant toute route d'écriture
# TOUJOURS : audit_trail pour tout changement de statut (insert only)
# TOUJOURS : hash SHA-256 calculé et vérifié sur les formulaires signés
# TOUJOURS : structlog pour les logs (pas print, pas logging.info bare)
# JAMAIS : secrets dans le code (tout dans .env via pydantic-settings)
# JAMAIS : flask db modify manuel (toujours alembic migrate)
# JAMAIS : chemins réseau hardcodés (NETWORK_BASE_PATH depuis config)
# JAMAIS : génération PDF >10 pages en synchrone (utiliser une tâche Celery)
# JAMAIS : UPDATE sur la table audit_trail
```

Routes standards par formulaire :

- `GET /affaires/<id>/formulaires/<code>` — affichage
- `POST /affaires/<id>/formulaires/<code>` — sauvegarde brouillon (AJAX)
- `POST /affaires/<id>/formulaires/<code>/valider`
- `POST /affaires/<id>/formulaires/<code>/signer`

## Commandes

```bash
# Activer le venv (Windows)
.venv\Scripts\activate

# Sélectionner l'interpréteur VS Code : Ctrl+Shift+P > Python: Select Interpreter > .venv

# Installation complète (dev)
pip install -r requirements-dev.txt

# Hooks qualité code
pre-commit install

# Setup base
cp .env.example .env      # renseigner DATABASE_URL et SECRET_KEY
flask db upgrade          # créer les tables
flask seed                # 5 utilisateurs BFF + 4 modules PED

# Développement
flask run --debug

# Tests
pytest                                         # tous les tests
pytest --cov=app --cov-report=html            # avec couverture HTML
pytest tests/unit/                            # tests unitaires seuls
pytest -k "hydr"                              # tests d'un formulaire

# Qualité code
ruff check app/                               # lint
black app/                                    # formatage
mypy app/                                     # typage statique

# Migrations
flask db migrate -m "description"
flask db upgrade

# PDF async (dev)
celery -A make_celery worker --loglevel=info
celery -A make_celery flower                  # dashboard http://localhost:5555

# Production Linux/NAS Synology
gunicorn run:app -w 4 -b 0.0.0.0:5000

# Production Windows Server
waitress-serve --port=5000 run:app
```

## Phase Actuelle : PHASE 1 — Infrastructure & MVP

**Livrable** : wizard affaire + formulaire HYDR complet + PDF HYDR avec en-tête BFF.

**Ordre d'implémentation :**

1. ~~Structure Flask + blueprints + config + extensions~~ **FAIT**
2. `app/enums.py` : Role, Statut, Chapitre, JalonCode
3. Modèles SQLAlchemy : User, Affaire, Formulaire (JSONB), Signature, AuditTrail
4. Migration Alembic initiale + `flask seed`
5. Authentification Flask-Login + CSRF + `@role_required`
6. `base.html` Bootstrap 5 : header BFF, nav, breadcrumb, flash messages
7. Dashboard : compteurs + dernières affaires
8. Liste affaires paginée + filtres
9. Wizard affaire : Q1–Q8 persisté en base (WIZARD_BROUILLON → BROUILLON)
10. Page affaire : accordéon A–G
11. Formulaire HYDR : calcul PT JS, sauvegarde AJAX, validation, signature + hash
12. PDF HYDR : WeasyPrint, en-tête BFF, sauvegarde NAS
13. Tests Phase 1 : login, création affaire, calcul PT, génération PDF

## Roadmap — 5 Phases

| # | Nom | Livrables clés | Complexité |
| --- | --- | --- | --- |
| **1** | Infrastructure & MVP | App + wizard + HYDR + PDF HYDR + tests intégration | XL |
| **2** | 27 formulaires complets | 27 formulaires + PDFs individuels + Flask-Babel + Celery PDF | XL |
| **3** | PDF complet & imports | Dossier assemblé, signets, QR code, imports drag&drop | L |
| **4** | Jalons, référentiels & notifs | JP0-JP6, CRUD référentiels, alertes email, API REST OpenAPI | L |
| **5** | Admin, sécurité & production | HTTPS NAS, module admin, 2FA TOTP, doc utilisateur | M |

## Référence Documentaire (CDC)

```text
../Cahier des charges/
├── CDC_MDB_BFF_v1.docx                              ← contexte, rôles, jalons
├── CDC_MDB_BFF_v2_Specifications_Formulaires.docx   ← chaque formulaire champ par champ
├── CDC_MDB_BFF_v3_Matrice_Parametrage.docx          ← règles activation Q1–Q8
├── CDC_MDB_BFF_WEB_v4.docx                          ← SCHÉMA COMPLET base de données
├── CDC_MDB_BFF_WEB_v5.docx                          ← architecture UX et routes
└── CDC_MDB_BFF_WEB_v6_Plan_Developpement.docx       ← roadmap 5 phases
```
