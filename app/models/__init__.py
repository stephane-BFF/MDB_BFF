"""Modèles SQLAlchemy MDB BFF.

L'enregistrement effectif des modèles dans ``Base.metadata`` est fait par
``app/__init__.py:_register_models()`` qui importe explicitement chaque
module. Ce ``__init__.py`` reste vide pour éviter un cycle d'import avec
``app/extensions.py`` (qui importe ``Base`` depuis ``app.models.base``).

Pour utiliser un modèle dans le reste du code :

    from app.models.user import User
    from app.models.affaire import Affaire
    # etc.

Les classes exportées au niveau paquet (pour ``from app.models import ...``)
sont peuplées dynamiquement dans ``_register_models()``.
"""
