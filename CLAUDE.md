# MDB BFF — Dossier Constructeur Qualité (Application Web)

## Projet
Application web Flask/PostgreSQL pour gérer les **dossiers constructeurs qualité** de Brown Fintube France Energy (BFF), fabricant de réchauffeurs de masse industriels.
- ~100 affaires/an · **27 formulaires qualité** · chapitres **A–G** · jalons **JP0–JP6**
- Norme : Directive Équipements sous Pression (PED 2014/68/UE)
- Utilisateurs : 5 agents BFF — rôles : **Admin, Approbateur, Vérificateur, Rédacteur, Lecteur**
- Hébergement : NAS BFF réseau interne · URL cible `https://bff-mdb.local`
- CDC v1–v6 disponibles dans `../Cahier des charges/` — **lire avant tout développement**

## Stack Technique
- **Backend** : Python 3.14+, Flask 3.1+ (factory `create_app`), Flask-Login, Flask-WTF, SQLAlchemy 2+
- **Base de données** : PostgreSQL + migrations Alembic
- **PDF synchrone** : WeasyPrint (formulaires individuels) + pypdf (assemblage dossier complet)
- **PDF asynchrone** : Celery + Redis (gros dossiers, Phase 2+) — worker : `celery -A make_celery worker`
- **Frontend** : Bootstrap 5, JavaScript vanilla — pas de npm, pas de bundler
- **Auth locale** : Werkzeug (`generate_password_hash` / `check_password_hash`)
- **Auth Windows/AD** : ldap3 — activable via `WINDOWS_AUTH_ENABLED=true` dans `.env`
- **Tests** : pytest + pytest-flask + pytest-cov
- **WSGI Production Linux/NAS Synology** : Gunicorn (4 workers) → `gunicorn run:app -w 4`
- **WSGI Production Windows Server** : Waitress → `waitress-serve --port=5000 run:app`
- **Dev local** : `flask run --debug`

## Architecture des fichiers
```
app/
├── __init__.py          ← create_app factory
├── config.py            ← DevelopmentConfig, ProductionConfig
├── extensions.py        ← db, login_manager, csrf, mail, migrate
├── celery_app.py        ← celery_init_app (PDF async)
├── models/              ← SQLAlchemy models (user, affaire, formulaire, jalon, referentiel, audit)
├── blueprints/
│   ├── auth/            ← login, logout (+ auth LDAP Windows si activée)
│   ├── dashboard/       ← tableau de bord post-login
│   ├── affaires/        ← liste, wizard Q1-Q8, page affaire
│   ├── formulaires/
│   │   └── {code}/      ← 1 sous-dossier par formulaire (ex: hydr/)
│   ├── jalons/          ← timeline JP0-JP6, Hold Points (Phase 4)
│   ├── referentiels/    ← CRUD soudeurs, CND, matériaux, PED, instruments (Phase 4)
│   ├── admin/           ← gestion utilisateurs, logs audit (Phase 5)
│   └── api/             ← REST /api/v1/
├── services/            ← pdf_service.py, network_service.py, email_service.py
├── templates/
│   ├── base.html
│   ├── pdf/             ← templates WeasyPrint par formulaire
│   └── {blueprint}/     ← auth/ dashboard/ affaires/ formulaires/ admin/
├── utils/
│   ├── decorators.py    ← @role_required
│   ├── validators.py    ← calculate_test_pressure, is_valid_numero_affaire
│   └── file_handler.py  ← validate_mime, build_network_path, save_file
└── static/              ← css/, js/, img/logo_bff.png
migrations/              ← fichiers Alembic (à committer)
tests/
```

## Les 5 Rôles

| Rôle | Création affaire | Saisie formulaire | Valider/Signer | Gérer référentiels | Admin |
|---|:---:|:---:|:---:|:---:|:---:|
| **Lecteur** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Rédacteur** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Vérificateur** | ✅ | ✅ | Valider seult | ❌ | ❌ |
| **Approbateur** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ |

## Les 27 Formulaires

| Chap. | Formulaires | Type |
|---|---|---|
| A | PdG, CCC, ConfCom, AttDecr, AttRep, EtatDesc | Simples |
| B | BIM, BIMSoud, PMI | Tableaux dynamiques JS |
| C | ListSoud, Rolling, DIM, TTH1, TTH2 | Tableaux + upload fichier |
| D | ListCND, NDE_Map, Dureté, Ferrite, Point0×4 | Conditionnels |
| E | HYDR*, RecordHydro, AirSav, Azote | Calculs automatiques |
| F | VisuFinal, Proprete, Sechage, Pesage | Conditionnels simples |
| G | PED_module (4 modules × 4 langues = 16 templates) | Multi-langues FR/EN/DE/IT |

**HYDR est le formulaire pilote** — son pattern architectural s'applique à tous les autres.

Activation des formulaires : déterminée par le paramétrage affaire (Q1–Q8 du wizard).
Un formulaire désactivé reste visible mais grisé dans l'accordéon A–G.

## Règles Métier Critiques
- **Pression épreuve** : `PT = round(PS × 1.43, 1)` — calculée en JS temps réel, revalidée serveur
- **Workflow statuts** : `BROUILLON → SOUMIS → VALIDE → SIGNE` (irréversible sauf Admin)
- **Signatures** : Rédacteur peut rédiger, Vérificateur+ pour valider, Approbateur pour signer
- **Jalons** : un jalon ne peut être franchi que si tous ses documents prérequis sont VALIDE
- **Chemin réseau PDF** : `\\BFF-FICHIERS\Affaires\{annee}\{num_affaire}\MDB\` (via `NETWORK_BASE_PATH`)
- **Numéro d'affaire** : format `BN{AAAA}-{NNN}` (ex: BN2026-042) — validé par `is_valid_numero_affaire`

## Conventions — NON NÉGOCIABLES

```python
# TOUJOURS : type hints + docstring sur les fonctions publiques
def calculate_test_pressure(design_pressure: float, coefficient: float = 1.43) -> float:
    """Calcule PT selon la règle BFF. PS en bar, retourne PT arrondi à 1 décimale."""
    return round(design_pressure * coefficient, 1)

# TOUJOURS : calculs métier dans services/ ou utils/validators.py, jamais dans les routes
# TOUJOURS : @role_required avant toute route d'écriture (depuis app/utils/decorators.py)
# TOUJOURS : audit_trail pour tout changement de statut
# JAMAIS : secrets dans le code (tout dans .env via python-dotenv)
# JAMAIS : flask db modify manuel (toujours alembic migrate)
# JAMAIS : chemins réseau hardcodés (lire NETWORK_BASE_PATH depuis config)
# JAMAIS : génération de PDF >10 pages en synchrone (utiliser une tâche Celery)
```

Chaque formulaire expose exactement ces routes :
- `GET /affaires/<id>/formulaires/<code>` — affichage
- `POST /affaires/<id>/formulaires/<code>` — sauvegarde brouillon (AJAX)
- `POST /affaires/<id>/formulaires/<code>/valider` — validation
- `POST /affaires/<id>/formulaires/<code>/signer` — signature

## Authentification Windows (LDAP)

Quand `WINDOWS_AUTH_ENABLED=true` dans `.env`, la page de login propose une connexion
avec les identifiants Windows/AD (via `ldap3`). Les variables LDAP à renseigner :
`LDAP_SERVER`, `LDAP_BASE_DN`, `LDAP_BIND_DN`, `LDAP_BIND_PASSWORD`.
Les comptes locaux (table `users`) restent disponibles même si LDAP est activé.

## Génération PDF Asynchrone (Celery + Redis)

Pour les dossiers complets (Phase 2+, 50-100 pages) :
1. La route déclenche une tâche Celery : `generer_dossier_pdf.delay(affaire_id)`
2. Le worker Redis traite la génération en arrière-plan
3. L'interface affiche la progression (polling AJAX ou SSE)
4. Le PDF est sauvegardé sur le NAS et un lien de téléchargement est fourni

Lancer le worker (dev) :
```bash
celery -A make_celery worker --loglevel=info
celery -A make_celery flower        # dashboard http://localhost:5555
```

## Commandes
```bash
# Activer le venv (Windows)
.venv\Scripts\activate

# Installation
pip install -r requirements.txt
cp .env.example .env              # puis renseigner DATABASE_URL et SECRET_KEY
flask db upgrade                  # créer les tables
flask seed                        # 5 utilisateurs BFF + 4 modules PED

# Développement
flask run --debug                 # http://localhost:5000

# Tests
pytest                            # tous les tests
pytest --cov=app --cov-report=html  # avec couverture
pytest -k "hydr"                  # tests d'un formulaire spécifique

# Migrations
flask db migrate -m "ajout table X"
flask db upgrade

# Production Linux/NAS Synology
gunicorn run:app -w 4 -b 0.0.0.0:5000

# Production Windows Server
waitress-serve --port=5000 run:app
```

## Phase Actuelle : PHASE 1 — Infrastructure & MVP

**Livrable attendu** : wizard affaire fonctionnel + formulaire HYDR complet + PDF HYDR avec en-tête BFF.

**Ordre strict d'implémentation** :
1. ~~Structure Flask (create_app, blueprints vides, config, extensions)~~ **FAIT**
2. Modèles SQLAlchemy : User, Affaire, ParametrageAffaire, FormHydr, AuditTrail
3. Migration Alembic initiale + commande `flask seed`
4. Authentification : Flask-Login, CSRF, décorateur `@role_required`
5. `base.html` Bootstrap 5 : header BFF, nav, breadcrumb, flash messages
6. Dashboard : liste affaires paginée, filtres, bouton "Nouvelle affaire"
7. Wizard affaire : 8 pages Q1–Q8 (session Flask), récapitulatif, création en base
8. Page affaire : accordéon A–G avec formulaires actifs/inactifs selon paramétrage
9. Formulaire HYDR : calcul PT JS, sauvegarde AJAX, validation, signature
10. PDF HYDR : WeasyPrint, en-tête BFF, sauvegarde sur chemin réseau

**Critères de validation Phase 1** :
- Wizard complet → HYDR rempli → validé → signé → PDF généré avec logo BFF
- 5 comptes BFF fonctionnels avec leurs restrictions de rôle respectives
- Application accessible depuis `http://localhost:5000` (prod : `https://bff-mdb.local`)

## Roadmap — 5 Phases

| # | Nom | Livrables clés | Complexité |
|---|---|---|---|
| **1** | Infrastructure & MVP | App + wizard + HYDR + PDF HYDR | XL |
| **2** | 27 formulaires complets | 27 formulaires + PDFs individuels + Celery PDF async | XL |
| **3** | PDF complet & imports | Dossier assemblé, signets, QR code, imports drag&drop | L |
| **4** | Jalons, référentiels & notifs | JP0-JP6, CRUD référentiels, alertes email | L |
| **5** | Admin, sécurité & production | HTTPS NAS, module admin, doc utilisateur | M |

## Référence Documentaire (CDC)
```
../Cahier des charges/
├── CDC_MDB_BFF_v1.docx                              ← contexte, rôles, jalons détaillés
├── CDC_MDB_BFF_v2_Specifications_Formulaires.docx   ← chaque formulaire champ par champ
├── CDC_MDB_BFF_v3_Matrice_Parametrage.docx          ← règles activation Q1–Q8
├── CDC_MDB_BFF_WEB_v4.docx                          ← SCHÉMA COMPLET base de données
├── CDC_MDB_BFF_WEB_v5.docx                          ← architecture UX et routes détaillées
└── CDC_MDB_BFF_WEB_v6_Plan_Developpement.docx       ← roadmap 5 phases + prompt Phase 1
```
