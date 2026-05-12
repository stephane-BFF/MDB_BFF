"""Intégration Celery + Flask pour la génération PDF asynchrone (Phase 2+)."""
from celery import Celery, Task
from flask import Flask


def celery_init_app(app: Flask) -> Celery:
    """Crée et configure l'instance Celery liée au contexte Flask.

    Les tâches Celery s'exécutent dans un contexte Flask actif, ce qui permet
    d'utiliser SQLAlchemy, les configs et les services sans configuration
    supplémentaire.

    Args:
        app: Instance Flask créée par create_app.

    Returns:
        Instance Celery configurée, stockée dans app.extensions['celery'].

    Usage:
        from app.celery_app import celery_init_app
        celery = celery_init_app(create_app())
        # Lancer un worker : celery -A make_celery worker --loglevel=info
    """

    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    # Les clés CELERY_* de app.config sont lues via namespace="CELERY"
    celery_app.config_from_object(app.config, namespace="CELERY")
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app
