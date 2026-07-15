# Comparatif hébergement V1.1 — NAS Synology vs Windows Server

**Date** : 2026-07-15 · **Statut** : proposition — décision à trancher par S. Paumelle
**Objet** : choisir la plateforme de production de MDB BFF avant de figer la procédure
de déploiement HTTPS (`docs/DEPLOIEMENT_HTTPS.md`) et la recette terrain.

## Rappel du besoin

- Application interne BFF : 7 utilisateurs, ~100 affaires/an — charge très faible.
- Stack à héberger : Flask (WSGI) + PostgreSQL + **Redis + Celery** (PDF asynchrones,
  alertes jalons) + WeasyPrint (dépendances Pango/GTK).
- Cible CDC v1 : NAS BFF réseau interne, URL `https://bff-mdb.local`.
- Écriture des PDF sur le partage `\\BFF-FICHIERS\Affaires\...` (SMB).
- Authentification LDAP/AD : simple flux réseau vers le contrôleur de domaine —
  **neutre vis-à-vis du choix** (les deux plateformes conviennent).

## Tableau comparatif

| Critère | NAS Synology (Linux/Docker + Gunicorn) | Windows Server (Waitress) |
|---|---|---|
| **Alignement CDC** | ✅ Cible explicite du CDC v1 | ⚠️ Écart à documenter/justifier |
| **Serveur WSGI** | Gunicorn 4 workers — référence en prod Linux | Waitress — correct mais mono-machine, moins outillé |
| **Redis (obligatoire pour Celery)** | ✅ Conteneur officiel `redis:7` | ❌ Pas de support officiel Windows → Memurai (licence commerciale) ou WSL2 (bricolage en prod) |
| **Celery worker** | ✅ Pool prefork standard | ⚠️ Prefork non supporté sur Windows → pool `solo`/`threads`, perfs et fiabilité moindres |
| **WeasyPrint** | ✅ `apt install libpango…` dans l'image Docker — reproductible | ⚠️ MSYS2 + `WEASYPRINT_DLL_DIRECTORIES` à maintenir à la main (déjà éprouvé en dev, mais fragile aux mises à jour) |
| **PostgreSQL** | Conteneur officiel `postgres:16` + volume | Installeur EDB Windows — supporté, exploitation plus manuelle |
| **HTTPS / reverse proxy** | ✅ Reverse proxy DSM intégré (certificat en 3 clics, renouvellement géré) | IIS + ARR ou nginx/Caddy à installer et maintenir |
| **Certificat `bff-mdb.local`** | Certificat interne (AD CS ou auto-signé importé DSM) — domaine `.local` ⇒ pas de Let's Encrypt | Idem (AD CS recommandé) — à parité |
| **Services au démarrage** | `docker compose up -d` : app, worker, beat, redis, postgres — un seul fichier versionné | 4–5 services Windows à créer (NSSM/sc.exe) et à maintenir un par un |
| **Sauvegarde** | Hyper Backup intégré (volumes + dump pg) | Windows Server Backup / Veeam à configurer |
| **Accès SMB vers BFF-FICHIERS** | ✅ Montage CIFS (déjà prévu par `NETWORK_BASE_PATH`) | ✅ Natif — léger avantage Windows |
| **Compétences d'exploitation BFF/AIT** | Docker/DSM — courbe d'apprentissage modérée | Windows — équipe IT déjà à l'aise |
| **Mises à jour applicatives** | `git pull` + rebuild image + `docker compose up -d` — rollback par tag d'image | Copie de fichiers + redémarrage services — rollback manuel |

## Chiffrage (estimations HT, à valider avec l'IT BFF)

| Poste | NAS Synology | Windows Server |
|---|---|---|
| Matériel | 0 € si NAS existant compatible Container Manager ; sinon DS923+ (4 Go → 16 Go RAM) ≈ **750–950 €** une fois | 0 € si VM sur hyperviseur existant ; sinon serveur ≈ 2 000 €+ |
| Licence OS | **0 €** (DSM inclus) | Windows Server 2022/2025 Standard ≈ **1 100–1 300 €** + CALs (souvent déjà couverts par le contrat MS — à vérifier) |
| Redis | **0 €** (conteneur officiel) | Memurai Enterprise ≈ **300–400 €/an**, ou WSL2 non recommandé en prod |
| Certificat TLS | 0 € (AD CS interne) | 0 € (AD CS interne) |
| Exploitation annuelle (estimation temps) | ≈ 1–2 j/an (MàJ DSM + images) | ≈ 3–5 j/an (Windows Update + 5 services + MSYS2/WeasyPrint) |
| **Total 1re année (ordre de grandeur)** | **0 à ~950 €** | **~1 400 à 3 700 €** (selon licences déjà détenues) |

## Recommandation

**NAS Synology (Linux, Docker Compose, Gunicorn)** — c'est la cible du CDC, le seul
scénario où Redis/Celery/WeasyPrint tournent sur leurs plateformes officiellement
supportées, le coût de licence est nul et le déploiement est reproductible (un
`docker-compose.yml` + un `.env` versionnés).

Le scénario Windows Server reste viable si la politique IT du groupe impose Windows :
il est documenté en variante dans `docs/DEPLOIEMENT_HTTPS.md`, avec ses deux points
durs (remplacement de Redis par Memurai, pool Celery `threads`).

### Prérequis à vérifier avant de valider la piste NAS (checklist IT)

- [ ] Modèle du NAS BFF existant et version DSM ≥ 7.2 (Container Manager disponible).
- [ ] RAM disponible ≥ 8 Go (app + postgres + redis + worker ≈ 2–3 Go).
- [ ] Autorisation d'ouvrir le port 443 du NAS sur le VLAN bureautique.
- [ ] Enregistrement DNS interne `bff-mdb.local` → IP du NAS (zone AD).
- [ ] Émission d'un certificat serveur par l'AD CS (ou politique de cert interne).
- [ ] Compte de service SMB en écriture sur `\\BFF-FICHIERS\Affaires\6 - AFFAIRES EN COURS`.

**Décision attendue** : GO NAS / GO Windows — à acter par S. Paumelle avec l'IT.
La doc de déploiement est rédigée pour la piste NAS et contient la variante Windows ;
aucun développement applicatif ne dépend du choix (config 12-factor via `.env`).
