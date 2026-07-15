# Mise en service de l'authentification LDAP/AD réelle + 2FA progressive

**Date** : 2026-07-15 · **Périmètre V1.1 arbitré** — le code est prêt et testé (bind
mocké) ; ce document décrit le branchement sur l'Active Directory réel de BFF.
**Point bloquant** : accès (réseau + informations d'annuaire) au contrôleur de
domaine AD de BFF — à obtenir auprès de l'IT.

## 1. Rappel de l'architecture (implémentée)

- Point d'entrée unique : `app/services/ldap_auth.py::authenticate(email, password)`.
- `WINDOWS_AUTH_ENABLED=true` → bind LDAP (`_ldap_bind`, ldap3, timeout 5 s), puis
  résolution du compte applicatif en base (le rôle vient de la base, jamais de l'AD).
- `WINDOWS_AUTH_ENABLED=false` → repli local Werkzeug (hash en base) — mode actuel.
- Garde-fous en place : mot de passe vide rejeté avant bind (anti bind anonyme),
  bind tenté même si l'e-mail est inconnu (pas de divulgation d'existence de compte),
  AD injoignable → échec propre `ldap_unreachable` (pas de repli silencieux en local).
- Un utilisateur doit exister dans la table `users` pour se connecter, même avec un
  bind AD réussi : l'AD prouve l'identité, la base porte le rôle et l'activation.

## 2. Informations à demander à l'IT BFF

| Information | Exemple | Variable `.env` |
|---|---|---|
| URI du contrôleur de domaine (préférer LDAPS) | `ldaps://dc01.bffrance.local:636` | `LDAP_SERVER` |
| Suffixe UPN des comptes utilisateurs | `@bffrance.com` ou `@bffrance.local` | sert à construire `LDAP_USER_DN_TEMPLATE` |
| Base DN (référence, pour évolutions futures) | `DC=bffrance,DC=local` | `LDAP_BASE_DN` |
| Certificat de l'autorité interne (si LDAPS) | CA racine AD CS | à installer sur l'hôte d'exécution |
| Flux réseau à ouvrir | hôte app → DC, port 636 (ou 389) | — |

Le bind se fait **avec les identifiants de l'utilisateur** (UPN), pas avec un compte
de service : `LDAP_BIND_DN`/`LDAP_BIND_PASSWORD` restent vides dans cette version.

## 3. Configuration `.env` (production)

```dotenv
WINDOWS_AUTH_ENABLED=true
LDAP_SERVER=ldaps://dc01.bffrance.local:636
LDAP_BASE_DN=DC=bffrance,DC=local
# {username} = partie locale de l'e-mail applicatif ; {email} = e-mail complet.
# Si l'UPN AD = e-mail applicatif, utiliser directement {email}.
LDAP_USER_DN_TEMPLATE={username}@bffrance.com
```

⚠️ Piège connu : les e-mails applicatifs sont `prenom.nom@bffrance.com` (équipe QC)
et `stephane.paumelle@ait-stein.com` (S. Paumelle). Si les UPN AD ne suivent pas le
même schéma pour tout le monde (deux domaines !), deux options :
1. faire porter l'UPN exact par le gabarit `{email}` si l'UPN = e-mail applicatif ;
2. sinon, prévoir un ticket V1.1.x pour ajouter une colonne `ldap_upn` sur `users`
   (mapping explicite compte applicatif → identité AD).

## 4. Procédure de test du bind réel (hors application)

Depuis l'hôte d'exécution (venv actif), tester le bind sans lancer l'appli :

```python
# scripts/test_ldap_bind.py — test manuel, ne pas committer de mot de passe
import ldap3
server = ldap3.Server("ldaps://dc01.bffrance.local:636", connect_timeout=5)
conn = ldap3.Connection(server, user="prenom.nom@bffrance.com", password="***")
print("bind:", conn.bind(), conn.result)
```

Résultats attendus :
- identifiants valides → `bind: True` ;
- mauvais mot de passe → `bind: False`, result `invalidCredentials` ;
- serveur injoignable → exception (l'appli la convertit en `ldap_unreachable`).

## 5. Bascule applicative

1. `flask seed` déjà exécuté avec les 7 comptes réels (rôles portés par la base).
2. Renseigner le `.env` (§3) et redémarrer le service.
3. Test de connexion avec 1 compte pilote (proposé : B. Girard, Approbateur).
4. Vérifier dans les logs structlog : absence de `ldap.unreachable`, événement
   d'audit `login` avec méthode LDAP.
5. Tester le cas « AD injoignable » (débrancher/bloquer le flux) : l'application
   doit refuser la connexion proprement, sans stack trace utilisateur.

## 6. Activation progressive du 2FA (décision arbitrée)

- **Go-live** : `ENFORCE_2FA=false` (défaut). Enrôlement volontaire via
  `/auth/2fa/setup` (QR code TOTP + codes de secours).
- **Phase 2 — après recette terrain** : basculer `ENFORCE_2FA=true` → tout
  Approbateur/Admin sans 2FA actif est redirigé vers l'enrôlement au login.
  Aucun code à écrire, un seul flag à changer + redémarrage.
- Population concernée par l'obligation : S. Paumelle (Admin), B. Girard,
  V. Vauthier (Approbateurs). Les Vérificateurs/Rédacteurs restent en volontaire.

## 7. Recette terrain (avec les 7 comptes réels)

Checklist par utilisateur (sur une affaire réelle) :
- [ ] Connexion LDAP (mot de passe Windows) OK.
- [ ] Rôle applicatif correct (droits de saisie/validation/signature conformes).
- [ ] Enrôlement 2FA volontaire proposé et fonctionnel (Approbateurs/Admin).
- [ ] Déconnexion/reconnexion, verrouillage sur mauvais mot de passe.
- [ ] Événements d'audit visibles dans le module admin.
