# Déploiement HTTPS production — MDB BFF

**Date** : 2026-07-15 · **Prérequis** : décision d'hébergement (voir
`HEBERGEMENT_V1.1_COMPARATIF.md` — recommandation : NAS Synology).
Ce document décrit la **piste A (NAS Synology, recommandée)** en détail et la
**piste B (Windows Server)** en variante. Rien dans le code ne dépend du choix :
toute la configuration passe par `.env` (pydantic-settings).

---

## Piste A — NAS Synology (Docker Compose + Gunicorn) — RECOMMANDÉE

### A.1 Prérequis DSM
- DSM ≥ 7.2 avec **Container Manager** installé.
- Dossier partagé `docker/mdb-bff/` pour les volumes (postgres, uploads, logs).
- DNS interne : `bff-mdb.local` → IP du NAS (zone DNS AD).
- Certificat serveur émis par l'AD CS (ou importé) dans DSM
  (Panneau de configuration → Sécurité → Certificat).

### A.2 Architecture conteneurs

```
[Client] --443--> [Reverse proxy DSM (TLS)] --5000--> [app: gunicorn run:app -w 4]
                                                        ├── [db: postgres:16]  (volume pgdata)
                                                        ├── [redis: redis:7]
                                                        ├── [worker: celery -A make_celery worker]
                                                        └── [beat:   celery -A make_celery beat]
```

### A.3 `docker-compose.yml` (squelette à committer en V1.1)

```yaml
services:
  app:
    build: .
    command: gunicorn run:app -w 4 -b 0.0.0.0:5000 --timeout 120
    env_file: .env
    ports: ["5000:5000"]
    depends_on: [db, redis]
    volumes:
      - ./uploads:/app/uploads
      - //BFF-FICHIERS/Affaires:/mnt/affaires   # montage CIFS côté NAS
  worker:
    build: .
    command: celery -A make_celery worker --loglevel=info
    env_file: .env
    depends_on: [db, redis]
    volumes:
      - //BFF-FICHIERS/Affaires:/mnt/affaires
  beat:
    build: .
    command: celery -A make_celery beat --loglevel=info
    env_file: .env
    depends_on: [redis]
  db:
    image: postgres:16
    environment: [POSTGRES_DB=mdb_bff, POSTGRES_USER=mdb, POSTGRES_PASSWORD_FILE=/run/secrets/pg]
    volumes: [pgdata:/var/lib/postgresql/data]
  redis:
    image: redis:7
volumes:
  pgdata:
```

Le `Dockerfile` (à créer) part de `python:3.14-slim` + `apt-get install -y
libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0` (WeasyPrint) — plus de
dépendance MSYS2, contrairement au dev Windows.

### A.4 Reverse proxy DSM (TLS)
1. Panneau de configuration → Portail de connexion → Avancé → **Proxy inversé**.
2. Source : HTTPS, `bff-mdb.local`, 443 — certificat AD CS sélectionné.
3. Destination : HTTP, `localhost`, 5000.
4. En-têtes personnalisés : activer `X-Forwarded-For` / `X-Forwarded-Proto`
   (l'app est derrière un proxy → cookies `Secure` fonctionnels).
5. Pare-feu DSM : 443 autorisé depuis le VLAN bureautique uniquement.

### A.5 Mise en service
```bash
docker compose up -d db redis
docker compose run --rm app flask db upgrade
docker compose run --rm app flask seed              # 7 comptes réels
docker compose run --rm app flask import-registre-be "Registre general commande BE.xlsx"
docker compose up -d
```

### A.6 Sauvegarde
- **Hyper Backup** : volume `pgdata` (arrêt court ou `pg_dump` planifié via
  tâche DSM : `docker exec db pg_dump -U mdb mdb_bff > /volume1/backup/mdb_$(date +%F).sql`),
  dossier `uploads/`, fichier `.env` (coffre).
- Rétention proposée : 30 jours quotidiens + 12 mois mensuels.

---

## Piste B — Windows Server (Waitress) — VARIANTE

À n'utiliser que si l'IT impose Windows. Points durs assumés : Redis n'existe pas
officiellement sur Windows (→ **Memurai**, licence commerciale) et le pool Celery
`prefork` n'est pas supporté (→ `--pool=threads`).

### B.1 Composants
| Rôle | Produit | Service Windows |
|---|---|---|
| WSGI | Waitress (`waitress-serve --port=5000 run:app`) | via NSSM |
| TLS / reverse proxy | IIS + ARR (ou Caddy) → 443 → 5000 | IIS |
| Base | PostgreSQL 16 (installeur EDB) | natif |
| Broker | Memurai (compatible Redis) | natif |
| Worker | `celery -A make_celery worker --pool=threads --loglevel=info` | via NSSM |
| Beat | `celery -A make_celery beat` | via NSSM |
| WeasyPrint | MSYS2 + `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin` | (env système) |

### B.2 Étapes
1. Installer Python 3.14, créer le venv, `pip install -r requirements.txt`.
2. Installer MSYS2 : `pacman -S mingw-w64-x86_64-pango` (note projet existante).
3. PostgreSQL + création base/rôle ; Memurai en service.
4. `.env` de production (`REDIS_URL=redis://localhost:6379/0`, `DATABASE_URL=…`).
5. `flask db upgrade && flask seed && flask import-registre-be …`.
6. Créer les 3 services NSSM (waitress, worker, beat), démarrage automatique + recovery.
7. IIS : site 443 avec certificat AD CS, ARR reverse proxy vers `http://localhost:5000`,
   en-têtes `X-Forwarded-*`.
8. Sauvegarde : `pg_dump` planifié + Windows Server Backup.

---

## Checklist commune post-déploiement (les deux pistes)

- [ ] `https://bff-mdb.local` répond, redirection HTTP→HTTPS active, cadenas valide
      sur les postes du domaine (CA interne déployée par GPO).
- [ ] `SESSION_COOKIE_SECURE=true` (cookies non transmis en clair).
- [ ] Login LDAP OK (voir `LDAP_AD_MISE_EN_SERVICE.md`) ; repli local désactivé
      (`WINDOWS_AUTH_ENABLED=true`).
- [ ] Génération PDF unitaire OK (WeasyPrint) + dossier complet (Celery/Redis).
- [ ] Écriture du PDF sur `\\BFF-FICHIERS\Affaires\6 - AFFAIRES EN COURS\{references_internes}\MDB\`.
- [ ] E-mails de jalons envoyés (SMTP interne).
- [ ] Sauvegarde testée par une restauration à blanc.
- [ ] Recette terrain avec les 7 comptes (checklist dans `LDAP_AD_MISE_EN_SERVICE.md` §7).
