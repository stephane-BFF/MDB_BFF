"""Application factory MDB BFF."""
import os

from flask import Flask

from app.config import config_by_name
from app.extensions import csrf, db, login_manager, mail, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Crée et configure l'application Flask.

    Args:
        config_name: Nom de la config ('development', 'production'). Utilise
                     FLASK_ENV si omis, sinon 'development'.

    Returns:
        Instance Flask configurée avec tous les blueprints enregistrés.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    _init_extensions(app)
    _register_models()
    _register_blueprints(app)
    _register_cli(app)
    _register_context_processors(app)

    return app


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)


def _register_models() -> None:
    """Importe explicitement chaque module de modèle pour qu'il s'enregistre
    dans ``Base.metadata`` (requis pour Flask-Migrate)."""
    from app.models import affaire, audit, fichier, formulaire, jalon, referentiel, signature, user  # noqa: F401


def _register_context_processors(app: Flask) -> None:
    """Injecte les variables globales dans tous les templates."""
    from flask_login import current_user  # noqa: PLC0415

    @app.context_processor
    def inject_globals() -> dict:
        nb_alertes = 0
        if current_user.is_authenticated:
            try:
                from app.services.alertes import count_alertes  # noqa: PLC0415
                nb_alertes = count_alertes()
            except Exception:  # noqa: BLE001
                pass
        return {"nb_alertes": nb_alertes}


def _register_cli(app: Flask) -> None:
    """Enregistre les commandes ``flask <…>`` personnalisées."""
    from app.cli.seed import seed_command

    app.cli.add_command(seed_command)


def _register_blueprints(app: Flask) -> None:
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.affaires import bp as affaires_bp
    from app.blueprints.api import bp as api_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.dashboard import bp as dashboard_bp
    from app.blueprints.dossier import bp as dossier_bp
    from app.blueprints.fichiers import bp as fichiers_bp
    from app.blueprints.formulaires import bp as formulaires_bp
    from app.blueprints.jalons import bp as jalons_bp
    from app.blueprints.referentiels import bp as referentiels_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(affaires_bp, url_prefix="/affaires")
    app.register_blueprint(
        formulaires_bp,
        url_prefix="/affaires/<int:affaire_id>/formulaires",
    )
    app.register_blueprint(
        dossier_bp,
        url_prefix="/affaires/<int:affaire_id>/dossier",
    )
    app.register_blueprint(
        fichiers_bp,
        url_prefix="/affaires/<int:affaire_id>/fichiers",
    )
    app.register_blueprint(
        jalons_bp,
        url_prefix="/affaires/<int:affaire_id>/jalons",
    )
    app.register_blueprint(referentiels_bp, url_prefix="/referentiels")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
