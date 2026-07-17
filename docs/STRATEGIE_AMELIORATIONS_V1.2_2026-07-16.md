# Stratégie de mise en œuvre — Demandes d'amélioration « Affaires / Items / Fiche technique » (V1.2)

**Date** : 2026-07-16 · **Rédacteur** : Claude (développeur / coéquipier QC) · **Statut** : proposition à valider par S. Paumelle
**Périmètre** : 9 demandes exprimées le 2026-07-16, à réaliser après/en parallèle des chantiers V1.1 restants (LDAP, recette).

---

## 1. Synthèse des demandes et réponses proposées

| # | Demande | Réponse proposée | Lot |
|---|---------|------------------|-----|
| 1 | Plusieurs dossiers constructeurs par affaire (1 par item) — arborescence ou regroupement | Regroupement par n° d'affaire sans refonte du modèle (décision D1) : vue groupée, page « Affaire », bouton « Ajouter un item » | Lot 3 |
| 2 | Création en 2 temps : infos génériques de l'affaire, puis création de l'ITEM | Wizard réorganisé : étape « Affaire » (n°, année, client, commande) puis étape « Item » | Lot 1 |
| 3 | Création possible dès Q3 + question DESP / STAMP U (+ catégorie et module si DESP), préremplis depuis les colonnes R, S, T du registre BE | Import registre étendu (R/S/T) + nouvelle étape « Réglementation » ; le dossier passe en BROUILLON dès cette étape | Lot 0 + Lot 1 |
| 4 | Onglets Q1 à Q3 cliquables et navigables, nom affiché sous l'onglet | Stepper cliquable (étapes déjà atteintes) + libellé sous chaque pastille | Lot 1 |
| 5 | Modules de conformité : autoriser aussi les modules des catégories supérieures, de façon lisible | Select à deux groupes « Catégorie X (usuels) » / « Catégories supérieures » + validation serveur élargie (art. 14 PED) | Lot 1 |
| 6 | Données consultables et modifiables une fois l'affaire/item créés | Fiche technique de l'item, éditable selon statut et rôle, auditée | Lot 2 |
| 7 | Q4 à Q8 → fiche technique de l'ITEM + bouton de vérification de la catégorie de risque (fluide, dangerosité, volume) | Page « Fiche technique » regroupant les ex-Q4→Q7 + service de calcul annexe II et comparaison calculé/déclaré | Lot 2 |
| 8 | Q6 : cases à cocher pour les procédés de soudage ; Q7 : idem pour les tests de pression | Cases à cocher Bootstrap (widgets WTForms) ; tests de pression passent en multi-choix | Lot 2 |
| 9 | BIMSOUD : n° de lot en 1re colonne, remplissage de toute la ligne d'un coup | Colonne `num_lot` en tête + datalist avec autofill de la ligne (mécanisme existant réutilisé) | Lot 4 |
| 10 | Suppression en mode admin d'un dossier / d'une affaire complète *(ajout 2026-07-17)* | Suppression Admin tout statut, double confirmation + **export PDF préalable obligatoire** (décision D6) | Lot 5 |
| 11 | Type d'équipement sur chaque ITEM, liste déroulante (Réfrigérant, HPIN, BHM, RM, SHELL&TUBE, FAISCEAU de rechange, CALANDRE de rechange, BEU…) *(ajout 2026-07-17)* | Référentiel administrable `TypeEquipement` + colonne sur l'affaire, choisi à l'étape « Item » du wizard (décision D7) | Lot 1 |
| 12 | Architecture type de dossier consultable via le sommaire + personnalisation via une bibliothèque d'éléments *(ajout 2026-07-17)* | Modèle de sommaire par type d'équipement + page « Sommaire » avec inclusion/exclusion des 27 formulaires (décision D8) | Lot 6 |

---

## 2. Ce que dit le code aujourd'hui (état des lieux ciblé)

- **Le modèle porte déjà le multi-items** : `Affaire` = 1 dossier par couple (`numero_affaire`, `item`), contrainte composite `uq_affaires_numero_item` (`app/models/affaire.py:54-56`). Ce qui manque est purement UX (regroupement, navigation, ajout d'item pré-rempli).
- **Wizard monolithique Q1→Q8** : l'affaire n'est utilisable qu'après Q8 (`finish_wizard`, `app/services/affaire.py:187`) ; les sauts en avant sont bloqués et le retour ne passe que par un bouton POST (`app/blueprints/affaires/routes.py:349-357`, `go_back` `app/services/affaire.py:171`) ; le stepper n'est pas cliquable et n'affiche pas les noms (`app/templates/affaires/wizard.html:40-56`).
- **Q4 porte déjà catégorie + module PED**, mais en fin de parcours ; `MODULES_PAR_CATEGORIE` est strict — un module d'une catégorie supérieure est refusé (`app/forms/wizard.py:195-200` + JS `wizard.html:244-298`).
- **L'import registre ignore R/S/T** : seules les colonnes 4→16 sont lues (`app/services/registre_be.py:50-58`) ; le modèle `RegistreBEItem` n'a pas de champs certification/catégorie/module.
- **Q6/Q7 en `<select multiple>`** (`wizard.html:13-15`) ; le test de pression est un choix **unique** (`app/forms/wizard.py:374-383`).
- **Les clés JSONB `q4_*`–`q7_*` sont un contrat interne** consommé par 4 services : `attdecr.py:85`, `etatdesc.py:77-99`, `hydr.py:60`, `ped.py:232`. Les renommer imposerait une migration de données — on ne le fera pas (décision D2).
- **BIMSOUD** : `num_lot` est en 4e colonne (`app/services/formulaires/bimsoud.py:45`) ; le mécanisme d'autofill par datalist existe déjà côté template (`_table.html:337-346`) et est alimenté par `get_reference_options()` (`bimsoud.py:58`) — il suffit de fournir un dictionnaire par lot.

---

## 3. Décisions de conception

### D1 — Regrouper par affaire plutôt que restructurer le modèle ★ recommandé
- **Option A (recommandée)** : conserver le modèle actuel (1 ligne `affaires` = 1 dossier/item) et construire le regroupement en UI/service : liste groupée par `numero_affaire`, page « Affaire » listant ses items, « Ajouter un item » qui copie les infos génériques. Migration : aucune. Les 549 tests restent le filet de sécurité.
- **Option B (écartée pour V1.2)** : vraie table parente « affaire » + table enfant « dossier/item ». Impacts en cascade sur toutes les FK (`formulaires`, `jalons`, `fichiers_importes`, audit, API REST), migration de données risquée, plusieurs semaines de travail pour un bénéfice essentiellement d'intégrité (infos génériques stockées une seule fois).
- **Compensation du point faible de l'option A** : l'édition d'une info générique (client, réf. commande) proposera une **propagation contrôlée** aux autres items de la même affaire (case « appliquer aux N autres items », auditée).

### D2 — Clés JSONB stables, seule l'UI bouge
Les clés `q4_*`–`q7_*` restent inchangées (contrat des 4 services consommateurs). La fiche technique lit/écrit **les mêmes clés** ; `template_version` passe à 2 pour tracer « saisi via fiche technique ». **Zéro migration de données.**

### D3 — Test de pression : passage en multi-choix compatible
`q7_test_pression` (str) → nouvelle clé `q7_test_pressions` (liste). Écriture sur la nouvelle clé ; lecture avec repli sur l'ancienne (les affaires existantes restent lisibles sans migration). L'activation conditionnelle des formulaires HYDR / AirSav / Azote est adaptée en conséquence.

### D4 — Source de l'autofill « n° de lot » BIMSOUD (à arbitrer, voir §7)
- **Option 1 (rapide, recommandée en premier)** : historique — les lignes BIMSOUD déjà saisies (toutes affaires confondues) forment le dictionnaire `lot → (désignation, norme, Ø, fournisseur, réf. CCPU)`.
- **Option 2 (pérenne)** : référentiel `LotMetalApport` administrable (écran admin + import), sur le modèle de `MetalApport`.
- Recommandation : livrer l'option 1, ajouter l'option 2 si le besoin d'administration se confirme à l'usage.

### D5 — Catégorie calculée ≠ catégorie déclarée
Le bouton « Vérifier la catégorie de risque » **calcule** (tableaux 1–4, annexe II PED) et **compare** à la valeur déclarée sans l'écraser : l'utilisateur reste maître (bouton « Appliquer » optionnel, à arbitrer). Atout QC : les ~640 lignes du registre portant une CAT permettent de **rejouer le calcul sur des cas réels** et de valider la fonction.

### D6 — Suppression admin : tout statut, mais export PDF préalable **obligatoire** *(arbitré 2026-07-17)*
L'Admin peut supprimer un dossier (ou une affaire complète : tous ses items) **quel que soit le statut**, avec double confirmation par saisie de la référence (ex. taper `BN0811-8975`). Avant toute suppression, un **PDF complet du dossier est assemblé et archivé** (répertoire d'export horodaté) — si l'assemblage échoue (WeasyPrint/GTK indisponible), **la suppression est refusée** : pas de suppression sans filet. La suppression est tracée en détail dans l'audit trail (statut, formulaires, signatures au moment de la suppression — l'audit étant insert-only, la trace survit à l'affaire) ; les fichiers importés sur disque sont également supprimés.

### D7 — Type d'équipement : référentiel administrable *(arbitré 2026-07-17)*
Nouvelle table référentiel `TypeEquipement` (sur le modèle de `MetalApport`/`OrganismeNotifie`) + écran admin CRUD, seedée avec : Réfrigérant, HPIN, BHM, RM, SHELL&TUBE, FAISCEAU de rechange, CALANDRE de rechange, BEU. Colonne `type_equipement_id` (FK nullable) sur `Affaire`, choisie en liste déroulante à l'étape « Item » du wizard (Lot 1), consultable/modifiable dans la fiche technique (Lot 2). Distinct de `type_echangeur` (référence type BFF, ex. « H1 06-01-72 »), qui reste inchangé.

### D8 — Architecture type par type d'équipement + bibliothèque = les 27 formulaires *(arbitré 2026-07-17)*
Chaque `TypeEquipement` porte son **modèle de sommaire par défaut** (liste des codes formulaires inclus — ex. « FAISCEAU de rechange » = dossier allégé, « SHELL&TUBE » = complet). À la création du dossier, ce modèle initialise la **composition du dossier** (stockée en JSON sur l'affaire) ; une page « Sommaire » la rend consultable et personnalisable : la **bibliothèque** liste les 27 formulaires (périmètre arbitré — les fichiers importés gardent leur mécanisme actuel par chapitre) et chacun peut être inclus/exclu. Règles de sécurité : exclure un formulaire **masque** du sommaire/PDF mais **ne supprime aucune donnée** ; un formulaire déjà **signé** ne peut pas être exclu sans avertissement explicite. L'assemblage PDF (`assemblage.py`), la page affaire (`show.html`) et le sommaire PDF respectent la composition.

---

## 4. Stratégie par lots

### Lot 0 — Fondations données : registre BE étendu (effort S)
1. Modèle `RegistreBEItem` : + 5 colonnes — `certification_brute` (col. R telle quelle), `desp` (bool), `stamp_u` (bool), `categorie_risque` (col. S), `module_evaluation` (col. T).
2. Parsing (`app/services/registre_be.py`) : `desp = "DESP" in R.upper()` ; `stamp_u = "STAMP U" in R.upper()` ; S et T stockés bruts (valeurs historiques conservées, voir annexe A). Colonnes source : R=18, S=19, T=20 (en-têtes ligne 4 : CERTIFICATION / CAT / MODULE — vérifié sur le fichier réel le 2026-07-16).
3. Migration Alembic **additive** (aucun DROP) + réimport `flask import-registre-be`.
4. ⚠️ Pratique : le fichier Excel ouvert dans Excel/OneDrive est **verrouillé** (PermissionError constatée ce jour) → l'import copiera le fichier vers un emplacement temporaire avant lecture.
5. Tests : parsing des 36 libellés distincts observés en colonne R (dont fautes de frappe réelles : `DESP 2014/98/UE`, `DESP 2014/968/EU`, `DESP2014/68/UE` sans espace).

### Lot 1 — Wizard raccourci « Affaire → Item → Réglementation » (effort M) — ✅ LIVRÉ le 2026-07-17
Nouvelle séquence — **4 étapes + récapitulatif** au lieu de 8 :

| Étape | Nom affiché | Contenu | Persistance |
|-------|-------------|---------|-------------|
| Q1 | **Affaire** | année, n° d'affaire (registre / saisie manuelle), client + réf. commande préremplis | colonnes `Affaire` |
| Q2 | **Item** | n° item (liste dépendante), repère, type d'échangeur, **type d'équipement (liste déroulante, référentiel D7)**, nombre, année de construction | colonnes `Affaire` |
| Q3 | **Réglementation** | DESP (oui/non), STAMP U (oui/non) ; si DESP : catégorie de risque + module d'évaluation — **préremplis depuis R/S/T du registre** | JSONB `q4_desp`, `q4_stamp_u`, `q4_categorie_ped`, `q4_module_ped` |
| Q4 | **Récapitulatif** | relecture + confirmation → **BROUILLON** (dossier créé et utilisable) | — |

- Les ex-Q4→Q7 (fluide, conditions de service, procédés, contrôles) **sortent du wizard** et deviennent la fiche technique (Lot 2). Les clés JSONB ne changent pas (D2).
- **Stepper cliquable** : chaque étape déjà atteinte devient un lien GET ; nom affiché sous la pastille. Côté route : autoriser la consultation/modification d'une étape ≤ étape max atteinte sans reculer le compteur (`statut_wizard` = étape max, plus « étape courante ») — aujourd'hui le retour est un POST destructeur de position (`routes.py:424-437`).
- **Modules des catégories supérieures** : `modules_autorises(cat) = union(modules de cat, modules des catégories > cat)` ; le `<select>` est rendu en deux `<optgroup>` — « Catégorie II (usuels) » puis « Catégories supérieures (III, IV) » ; validation serveur élargie à l'union. Base réglementaire : l'article 14 de la PED 2014/68/UE autorise le fabricant à appliquer une procédure prévue pour une catégorie supérieure.
- Catégorie/module requis **uniquement si DESP** ; STAMP U seul (459 lignes du registre !) crée le dossier sans catégorie PED.
- Affaires actuellement en cours de wizard (WIZARD_BROUILLON) : inventaire avant bascule, purge ou finalisation manuelle (point d'arbitrage §7.5).
- Vérifier par tests que les formulaires consommant `q5_*`–`q7_*` (ETATDESC, HYDR, PED) **dégradent proprement** tant que la fiche technique n'est pas remplie (message « à compléter dans la fiche technique », pas de crash ni de PDF silencieusement vide).
- **Type d'équipement (D7, ajout 2026-07-17)** : référentiel `TypeEquipement` (table + seed des 8 valeurs + CRUD admin sur le modèle des référentiels existants), colonne `type_equipement_id` sur `Affaire` (migration additive), liste déroulante à l'étape « Item » ; affiché dans la liste des affaires et la page dossier.

### Lot 2 — Fiche technique de l'item (effort M/L)
- Nouvelle page `/affaires/<id>/fiche-technique` (GET/POST), accessible depuis la page affaire (`show.html`) et depuis le récapitulatif du wizard.
- Sections : Réglementation (reprise éditable de l'étape Q3) · Caractéristiques fluide (ex-Q4 : état, groupe, nom) · Conditions de service (ex-Q5 : PS, T° min/max, volume) · Procédés de fabrication (ex-Q6) · Contrôles & essais (ex-Q7).
- **Cases à cocher** : `SelectMultipleField` rendus avec `ListWidget(prefix_label=False)` + `CheckboxInput` (form-check Bootstrap) pour procédés de soudage, méthodes CND **et tests de pression** (passage multi, D3).
- **Bouton « Vérifier la catégorie de risque »** : service pur `compute_categorie_ped(fluide_etat, fluide_groupe, ps_bar, volume_l)` → catégorie + tableau annexe II applicable ; endpoint JSON ; affichage comparatif calculée / déclarée (D5). Volume requis pour le calcul (aujourd'hui optionnel en Q5 — le bouton le signale s'il manque).
- Éditabilité : `affaire.is_editable` + rôle Rédacteur minimum ; chaque enregistrement passe par `AuditTrail`.
- i18n : toutes les nouvelles chaînes en `_l()` / `_()` + cycle extract → update → traduire (EN/DE/IT) → compile.

### Lot 3 — Regroupement par affaire (effort M)
- **Liste des affaires** : bascule « vue à plat / vue groupée par n° d'affaire » (compteur d'items, statuts agrégés).
- **Page « Affaire BNxxxx »** : infos génériques + tableau des items/dossiers (statut, jalons, liens) ; bouton **« Ajouter un item »** → wizard avec l'étape Affaire pré-remplie et verrouillée, items du registre non encore utilisés proposés en premier.
- **Édition des infos génériques** depuis cette page avec propagation contrôlée aux autres items (D1).
- Fil d'Ariane : Dossier ↔ Affaire ↔ liste, dans `show.html` et la fiche technique.

### Lot 4 — BIMSOUD « lot d'abord » (effort S)
- `TABLE_SPEC` réordonné : `num_lot` en 1re colonne, avec `datalist="lots"` (`bimsoud.py`).
- `get_reference_options()` : dictionnaire `lot → {designation, norme, diametre, fournisseur, ref_ccpu}` construit depuis l'historique des lignes BIMSOUD (option D4-1).
- **Aucune modification JS** (`_table.html:337-346` gère déjà l'autofill de la ligne) et **aucune migration** : les lignes sont stockées par clés de colonnes, l'ordre est purement visuel.

### Lot 5 — Suppression admin d'un dossier / d'une affaire complète (effort S/M) *(ajout 2026-07-17)*
- Route `POST /affaires/<id>/supprimer` (rôle Admin uniquement) + bouton sur la page dossier ; sur la page « Affaire » (Lot 3), bouton « Supprimer l'affaire complète » supprimant tous ses items en une opération.
- **Double confirmation** : modale exigeant la saisie de la référence exacte (`BN0811-8975`, ou le n° d'affaire pour une suppression complète).
- **Export préalable obligatoire (D6)** : assemblage synchrone du PDF complet (`assemble_dossier()` est une fonction pure appelable sans Celery — important sur le PC pilote où Redis est absent) archivé dans un répertoire d'export horodaté ; échec d'export ⇒ suppression refusée.
- Suppression : cascade ORM (parametrage, formulaires, jalons, fichiers, signatures) + **fichiers importés effacés du disque** + entrée d'audit détaillée (l'audit trail, insert-only, survit à l'affaire).
- Tests : rôle non-admin refusé, référence erronée refusée, échec d'export bloque, cascade complète vérifiée, fichiers disque nettoyés.

### Lot 6 — Architecture type du dossier + bibliothèque d'éléments (effort M/L) *(ajout 2026-07-17)*
- **Modèle** : `TypeEquipement.formulaires_defaut` (liste JSON des codes formulaires du sommaire type, éditable dans l'écran admin du référentiel) ; colonne `composition_dossier` (JSON) sur `Affaire` — liste des codes inclus, initialisée depuis le modèle du type d'équipement à la création (fin du wizard), migration additive (`NULL` = comportement actuel : tout inclus, rétrocompatible pour les dossiers existants).
- **Page « Sommaire »** `/affaires/<id>/sommaire` : vue chapitres A–G avec, pour chaque formulaire, son état (non créé / brouillon / signé) et un interrupteur inclure/exclure alimenté par la **bibliothèque des 27 formulaires** (périmètre arbitré D8). Exclusion = masquage sans perte de données ; formulaire signé ⇒ avertissement explicite avant exclusion.
- **Consommateurs adaptés** : `show.html` (accordéon filtré sur la composition), `assemblage.py` + `pdf/sommaire.html` (le PDF ne reprend que les éléments inclus), activation conditionnelle existante conservée (la composition s'ajoute comme filtre, elle ne remplace pas la logique d'activation).
- Dépend du Lot 1 (type d'équipement porté par l'affaire).
- Tests : initialisation par type, rétrocompatibilité `NULL`, exclusion d'un signé (avertissement), PDF assemblé conforme à la composition.

---

## 5. Ordre de réalisation, dépendances, méthode

```
Lot 0 ✅ (registre R/S/T)  ──►  Lot 1 (wizard raccourci + type équipement)  ──►  Lot 2 (fiche technique)  ──►  Lot 3 (regroupement)
                                                          │
                                                          ├──►  Lot 6 (architecture + bibliothèque)
                                                          └──►  Lot 5 (suppression admin) — dès que utile
                                Lot 4 (BIMSOUD) — indépendant, intercalable
```

- **Lot 0 avant Lot 1** : le préremplissage DESP/cat/module a besoin des colonnes importées. *(Lot 0 livré le 2026-07-16.)*
- **Lot 1 avant Lot 2** : le wizard raccourci définit exactement ce qui bascule en fiche technique.
- **Lot 3 après Lot 1** : « Ajouter un item » réutilise le wizard réorganisé.
- **Lot 4 indépendant** : livrable à tout moment (victoire rapide possible dès la première séance).
- **Lot 5 après Lot 1** (petit, utile tôt pour nettoyer les essais de recette) ; le bouton « supprimer l'affaire complète » arrive avec la page Affaire du Lot 3.
- **Lot 6 après Lot 1** (a besoin du type d'équipement) — recommandé après le Lot 2 pour capitaliser sur la page dossier consolidée.
- Méthode par lot : branche courte → développement + tests (les 549 existants doivent rester verts, plus les nouveaux) → commit → **validation par S. Paumelle sur un cas réel du registre** (une affaire BN récente multi-items) avant d'ouvrir le lot suivant.
- Toutes les migrations sont **additives et réversibles** (SQLite dev + PostgreSQL cible).
- Estimations : Lot 0 = S ✅ · Lot 1 = M ✅ (livré 2026-07-17, type équipement inclus) · Lot 2 = M/L (2 séances) · Lot 3 = M (1–2 séances) · Lot 4 = S (½ séance) · Lot 5 = S/M (1 séance) · Lot 6 = M/L (2 séances).

---

## 6. Risques et points de vigilance

1. **Affaires en cours de wizard à la bascule** (statut_wizard Q4+ à l'ancien sens) : inventaire et purge/finalisation en pré-déploiement.
2. **Valeurs historiques du registre** (`3.3`, `A1`, `B1+F`, DRIRE, arrêtés/décrets français, TR CU…) : stockées brutes, préremplissage uniquement quand la valeur est mappable sur le référentiel 2014/68/UE ; jamais bloquant pour la création.
3. **`test_pression` → `test_pressions`** : repli de lecture (D3) + adaptation de l'activation HYDR/AirSav/Azote — tests dédiés.
4. **Fiche technique vide à la création** : ETATDESC/HYDR/PED consomment `q4_*`–`q7_*` → prévoir des messages « à compléter dans la fiche technique » (pas de crash, pas de PDF vide silencieux).
5. **Fichier Excel verrouillé** par Excel/OneDrive au moment de l'import (constaté le 2026-07-16) → copie temporaire avant lecture.
6. **i18n** : toute chaîne oubliée hors `_l()` casse la parité FR/EN/DE/IT livrée le 2026-07-15.
7. **API REST `/api/v1`** (lecture affaires) : n'ajouter que des champs (pas de renommage) pour ne pas casser les clients.
8. **Export préalable à la suppression (Lot 5)** : dépend de WeasyPrint/GTK — sur le PC pilote, appeler l'assemblage **en synchrone** (pas de Celery, Redis absent) ; tester le cas d'échec (suppression refusée) et le temps d'assemblage sur un gros dossier.
9. **Composition du dossier (Lot 6)** : rétrocompatibilité impérative — `composition_dossier = NULL` ⇒ tout inclus (dossiers existants inchangés) ; ne jamais supprimer de données à l'exclusion ; avertir avant d'exclure un formulaire signé.

---

## 7. Arbitrages — **rendus par S. Paumelle le 2026-07-16**

1. **D1** : ✅ **Regroupement UI sans table parente** (option A validée).
2. **D4** : ✅ **Les deux, en 2 temps** — autofill depuis l'historique des saisies livré au Lot 4, référentiel de lots administrable ajouté ensuite si le besoin se confirme à l'usage.
3. **Propagation des infos génériques** : ✅ **Sur confirmation** — case « appliquer aux N autres items de l'affaire » à l'enregistrement, propagation tracée dans l'audit.
4. **Catégorie calculée** : ✅ **Comparer + bouton « Appliquer »** — le clic remplace la valeur déclarée (audité), le module de conformité est re-filtré en conséquence.
5. **Affaires en WIZARD_BROUILLON** : ✅ **Purge des deux** (id 3 vide à Q1 ; id 4 BN0812-8977 à Q4, recréable en ~2 min avec le nouveau wizard). *(Purge effectuée le 2026-07-16.)*

**Arbitrages complémentaires — rendus par S. Paumelle le 2026-07-17** (demandes 10-12) :

6. **Suppression admin (D6)** : ✅ **Tout statut + export PDF préalable obligatoire** — l'échec de l'export bloque la suppression.
7. **Type d'équipement (D7)** : ✅ **Référentiel administrable** (table + écran admin, seed des 8 valeurs fournies).
8. **Architecture type (D8)** : ✅ **Par type d'équipement** — chaque type porte son modèle de sommaire par défaut, personnalisable ensuite.
9. **Bibliothèque d'éléments (D8)** : ✅ **Les 27 formulaires internes** (les fichiers importés gardent leur mécanisme actuel par chapitre ; pas d'éléments libres/placeholders pour l'instant).

---

## Annexe A — Colonnes R/S/T du registre (constaté le 2026-07-16)

Feuille `BE_EF_09_A_Registre`, en-têtes ligne 4 : col. R (18) = **CERTIFICATION**, col. S (19) = **CAT**, col. T (20) = **MODULE**.

- **R « CERTIFICATION »** — 36 libellés distincts, dont : `DESP 2014/68/UE` (128) et variantes/fautes réelles (`DESP2014/68/UE` 42, `DESP 2014/68/EU` 9, `DESP 2014/98/UE` 1, `DESP 2014/968/EU` 1), `DESP` (440), `DESP (sans CE)` (7), `DESP + STAMP U` (8+2+1), `STAMP U` (459), `STAMP U-2` (16), régimes historiques (`DRIRE` 34, `AM 15/03/2000` 107, `Décret 13/12/1999` 48, `Décret 2015/799` 109, `AM 20/11/2017` 48, `TR CU 032/2013` 24, `ISPESL` 2…), et du bruit libre (`Idem 11418`, `Attention surface = 15,4 m2`…).
  → Règles : `desp = "DESP" ∈ R` ; `stamp_u = "STAMP U" ∈ R` ; texte brut toujours conservé.
- **S « CAT »** : IV (222) · II (207) · III (118) · I (80) · `3.3` (16, ancienne référence art. 3 §3 de la PED 97/23, équivalent fonctionnel de l'art. 4.3 actuel) · `4.3` (11).
- **T « MODULE »** : H1 (194) · D1 (160) · H (116) · A (78) · E1 (35) · G (27) · A1 (2, ancien 97/23) · B1+F (1, ancien).

## Annexe B — Calcul de la catégorie de risque (bouton « Vérifier »)

Fonction pure `compute_categorie_ped(fluide_etat, fluide_groupe, ps_bar, volume_l)` fondée sur les **tableaux 1 à 4 (récipients) de l'annexe II PED 2014/68/UE** (les échangeurs tubulaires BFF sont des récipients sous pression) : choix du tableau par (état du fluide, groupe de dangerosité), catégorie par seuils sur PS, V et PS·V. Les seuils exacts seront **transcrits depuis le texte de la directive au moment de l'implémentation** (pas de valeurs de mémoire) et validés par :
1. des tests unitaires aux frontières de chaque tableau ;
2. le **rejeu sur les lignes du registre où CAT est renseignée** (~640 lignes) — tout écart entre catégorie calculée et catégorie du registre sera listé et arbitré avec le QC.
