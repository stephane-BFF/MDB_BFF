# État des lieux — MDB BFF — 2026-07-01

> Établi par reprise sur le code réel (et non la mémoire projet, obsolète).
> Reprise après ~6 semaines d'interruption (dernier commit : 2026-05-17).

## 1. Synthèse (TL;DR)

Le projet est **beaucoup plus avancé que ne le laissait croire la mémoire** (qui annonçait « Phase 2 en cours, 190 tests »). En réalité, **les 5 phases de la roadmap sont livrées à ~90 %** : application fonctionnelle de bout en bout (wizard → 27 formulaires → PDF individuels + dossier assemblé → jalons → référentiels → alertes → admin). **430 tests passent (100 %), couverture 78 %.** Restent 4 chantiers de finition avant mise en production : **API REST, i18n Flask-Babel, 2FA/TOTP, et durcissement/déploiement NAS**.

## 2. Métriques vérifiées (exécutées ce jour)

| Métrique | Valeur réelle | Source |
|---|---|---|
| Tests | **430 passés / 430** (0 échec) | `pytest -q` (150 s) |
| Couverture | **78 %** (2869 stmts, 622 manquants) | `pytest --cov=app` |
| Services formulaires | **29 codes** enregistrés (27 formulaires + variantes UT0×4, TTH×2) | `services/formulaires/__init__.py` |
| Commits | 8 commits, branche **`main`** | `git log` |
| Dernier commit | **2026-05-17** (« seed équipe BFF réelle ») | `git log -1` |
| Modifs non commitées | `.claude/`, `lancer_serveur.bat`, `test_mdb.py`, `*.txt` (untracked) | `git status` |

> ⚠️ La mémoire (`project-mdb-bff`, 190 tests / 79 % / branche `master` / « Phase 2 ») est **périmée** → à réactualiser.

## 3. Avancement par phase (roadmap 5 phases)

| # | Phase | Statut réel | Preuve / réserve |
|---|---|---|---|
| **1** | Infrastructure & MVP | ✅ **Complète** | Factory, modèles JSONB, auth, wizard Q1–Q8, HYDR, PDF |
| **2** | 27 formulaires + PDF + Babel + Celery | ✅ **Quasi complète** | 29 services + tests 100 % ; Celery PDF présent. ⚠️ **Flask-Babel non câblé** (PED multilingue fait via dict embarqué dans `pdf/ped.html`) |
| **3** | PDF complet & imports | ✅ **Complète (à consolider)** | Routes `dossier/pdf`, `/pdf/async`, `/pdf/status`, blueprint `fichiers` (drag&drop). ⚠️ Couverture `assemblage.py` **17 %**, QR code à confirmer |
| **4** | Jalons, référentiels & notifs | 🔶 **Partielle** | Jalons JP0–JP6 (89 %), référentiels CRUD, alertes email OK. ❌ **API REST `/api/v1/` = stub** (`routes.py` : « à implémenter ») |
| **5** | Admin, sécurité & production | 🔶 **Partielle** | Module admin, dashboard enrichi, audit. ❌ **2FA/TOTP absent**, ❌ LDAP/Windows **config seule** (pas de service), déploiement HTTPS NAS non vérifié |

## 4. Périmètre fonctionnel livré

- **Cœur métier** : wizard affaire persisté dès Q1, 27 formulaires (simples / tableaux dynamiques / conditionnels / calculés), workflow `BROUILLON → SOUMIS → VALIDE → SIGNE`, signatures SHA-256 + audit trail insert-only.
- **Formulaires** : HYDR (pilote, calcul PT=PS×1.43), chapitres A–G tous couverts, dont **PEDMOD** (4 modules × 4 langues via dict) — le « restant » de la mémoire est en fait **fait**.
- **PDF** : unitaire WeasyPrint + assemblage pypdf (page de garde, sommaire) + génération async Celery/Redis.
- **Pilotage** : jalons avec prérequis/Hold Points, référentiels (soudeurs, CND, matériaux, instruments), alertes email (jalons en retard, certifs expirées).
- **Admin & sécurité** : 5 rôles enum, `@role_required`, module admin (users, reset MDP, logs audit), 7 utilisateurs réels BFF seedés.

## 5. Écarts & risques

| Priorité | Écart / risque | Impact | Preuve |
|---|---|---|---|
| 🔴 P1 | **API REST `/api/v1/` non implémentée** (stub) | Livrable Phase 4 manquant | `blueprints/api/routes.py` |
| 🔴 P1 | **Sécurité prod incomplète** : pas de 2FA/TOTP, LDAP non implémenté | Bloquant mise en prod | grep TOTP=0, `config.py` LDAP sans service |
| 🟠 P2 | **i18n Flask-Babel non câblé** (`translations/` absent) | Dette vs décision d'archi actée ; multilingue non industrialisé | pas d'init Babel dans `__init__.py` |
| 🟠 P2 | **Zones peu testées** : `assemblage.py` 17 %, `tasks_alertes.py` 0 %, `pdf/tasks.py` 37 %, `validators.py` 35 % | Risque de régression silencieuse sur PDF/alertes | rapport `--cov` |
| 🟡 P3 | **Travail non commité + 6 semaines sans commit** | Perte de traçabilité, risque de perte | `git status` |
| 🟡 P3 | **Déploiement NAS (HTTPS, WSGI) non vérifié** | Reste avant go-live | Phase 5 non close |

## 6. Actions priorisées pour la reprise

**P1 — Débloquer la production (2–3 semaines)**
1. Committer et taguer l'état actuel (`v0.5.0-rc`) ; nettoyer les fichiers untracked.
2. Trancher le **périmètre API REST** (nécessaire au go-live ? sinon la déprioriser explicitement).
3. Implémenter/valider l'**authentification** cible : LDAP/AD réel **ou** décision « auth locale + 2FA TOTP pour Approbateurs/Admin ».

**P2 — Sécuriser la qualité (1–2 semaines)**
4. Remonter la couverture des zones critiques PDF/alertes (`assemblage`, `tasks_alertes`) à ≥ 70 %.
5. Décider du sort de **Flask-Babel** : câbler proprement (`.po` FR/EN/DE/IT) **ou** acter officiellement l'approche « dict embarqué » et amender le CLAUDE.md.

**P3 — Clôturer la roadmap (1 semaine)**
6. Rédiger la doc utilisateur + procédure de déploiement NAS (Waitress/Gunicorn + HTTPS).
7. Recette fonctionnelle sur une affaire réelle avec l'équipe BFF (les 7 comptes).

## 7. Question de cadrage

Avant de relancer le développement, un arbitrage décisif :
**l'API REST `/api/v1/` et l'i18n Flask-Babel sont-ils dans le périmètre de la V1 de production, ou reportés en V1.1 ?** La réponse conditionne le chemin critique vers le go-live.
