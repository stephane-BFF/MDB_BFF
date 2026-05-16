MDB BFF — Dossier Constructeur Qualité

Application interne Brown Fintube France Energy pour la gestion des dossiers 
constructeurs selon la Directive Équipements sous Pression (PED 2014/68/UE).

Fonctionnalités :
- Wizard de création d'affaire (Q1-Q8) persisté en base
- 27 formulaires qualité (chapitres A-G) avec workflow BROUILLON → SIGNÉ
- Jalons JP0-JP6 avec prérequis documentaires et Hold Points
- Génération PDF individuelle (WeasyPrint) et dossier complet (Celery)
- Signatures électroniques avec hash SHA-256 + audit trail immuable
- Référentiels qualité (soudeurs, opérateurs CND, instruments, matériaux)
- Alertes email automatiques (jalons en retard, certifications expirées)
- Import de fichiers par drag & drop

Stack : Python 3.14 · Flask 3.1 · SQLAlchemy 2.0 · PostgreSQL · Bootstrap 5
