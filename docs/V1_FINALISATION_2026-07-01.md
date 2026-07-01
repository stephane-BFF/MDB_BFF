# Finalisation V1.0.0-rc — MDB BFF — 2026-07-01

> Clôture des 4 chantiers de finition identifiés dans
> `ETAT_DES_LIEUX_2026-07-01.md`. Périmètre validé avec le commanditaire
> (S. Paumelle) : les 4 chantiers sont dans la V1 ; authentification cible
> **LDAP/AD** ; déploiement hors périmètre ; livrable = code + tests verts + tag.

## 1. Synthèse

| Chantier | Statut | Livrables |
|---|---|---|
| Sécurité (LDAP/AD + 2FA TOTP) | ✅ Fait | `services/ldap_auth.py`, 2FA sur `User`, routes `/auth/2fa*`, migration |
| API REST `/api/v1/` | ✅ Fait | `blueprints/api/routes.py`, jeton porteur, OpenAPI, CLI `flask api-token` |
| i18n Flask-Babel | ✅ Fait | `babel.init_app`, sélecteur de langue, catalogues FR/EN/DE/IT |
| Durcissement PDF/alertes | ✅ Fait | Tests ciblés + **correction d'un bug** de log (voir §5) |

## 2. Sécurité — LDAP/AD + 2FA TOTP

- **`app/services/ldap_auth.py`** : `authenticate(email, password)` choisit LDAP
  (bind Active Directory, `WINDOWS_AUTH_ENABLED`) ou repli local (hash Werkzeug).
  Le bind réel (`_ldap_bind`) est isolé et **mockable** — aucun serveur AD requis
  pour les tests. Un compte doit exister en base (rôle métier) même en mode LDAP.
- **2FA TOTP** (`pyotp`) portée par le modèle `User` : `start_totp_enrollment`,
  `confirm_totp`, `verify_totp`, codes de secours à usage unique (hash SHA-256),
  `requires_2fa` (Approbateur/Admin). Enrôlement self-service `/auth/2fa/setup`
  (QR code + clé manuelle), challenge `/auth/2fa` au login si 2FA active.
- **Compat non régressive** : sans 2FA activée, le login reste direct (aucun test
  existant cassé). Durcissement optionnel `ENFORCE_2FA` (défaut `false`).
- **Migration** `b7c8d9e0f1a2` : colonnes `totp_secret`, `totp_enabled`,
  `backup_codes`, `api_token_hash` (+ index) sur `users`.

## 3. API REST `/api/v1/` (lecture seule)

- Auth par **jeton porteur** (`Authorization: Bearer` ou `X-API-Key`), haché en
  SHA-256 et indexé (`User.api_token_hash`). Émission : `flask api-token issue <email>`.
- Endpoints : `GET /health` (public), `/affaires` (paginée + filtres statut/année),
  `/affaires/<id>` (détail + formulaires + jalons + avancement),
  `/affaires/<id>/formulaires`, `/affaires/<id>/jalons`, `/openapi.json`.
- **Aucune écriture métier exposée** : le workflow de signature (hash + audit)
  reste dans l'interface web. Erreurs JSON uniformes `{"error": {code, message}}`.

## 4. Internationalisation (Flask-Babel)

- `babel.init_app` avec sélecteur de langue : `?lang=` (persisté en session) →
  session → `Accept-Language` → défaut `fr`. Langues : **FR / EN / DE / IT**.
- Catalogues `app/translations/<lang>/LC_MESSAGES/messages.po|.mo`, `babel.cfg`.
- Sélecteur de langue dans le pied de page (visible dès la page de connexion).

## 5. Durcissement & bug corrigé

Couverture des zones critiques portée au-dessus de 70 % :

| Module | Avant | Après |
|---|---|---|
| `utils/validators.py` | 35 % | **100 %** |
| `services/pdf/tasks.py` | 37 % | **100 %** |
| `services/pdf/assemblage.py` | 17 % | **88 %** |
| `services/tasks_alertes.py` | 0 % | **82 %** |

**Bug corrigé (`assemblage.py`)** : `current_app.logger.warning(..., extra={"filename": …})`
levait `KeyError: "Attempt to overwrite 'filename' in LogRecord"` (`filename` est un
attribut réservé de `LogRecord`). Le log « fichier manquant », censé être non bloquant,
**faisait planter l'assemblage** dès qu'un fichier importé était absent. Clé renommée
en `fichier`. Détecté par les nouveaux tests de couverture.

## 6. Reporté en V1.1

- Déploiement HTTPS sur le NAS Synology (Gunicorn/Waitress) + recette terrain équipe BFF.
- Activation par défaut de `ENFORCE_2FA` (enrôlement obligatoire des rôles à privilège).
- Extension de l'i18n aux libellés WTForms et aux 27 formulaires (au-delà de la nav).
