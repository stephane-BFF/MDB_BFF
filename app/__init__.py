"""Application factory MDB BFF."""
import os
from flask import Flask
from app.config import config_by_name
from app.extensions import db, login_manager, csrf, mail, migrate


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
    _register_blueprints(app)

    return app


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)


def _register_blueprints(app: Flask) -> None:
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.dashboard import bp as dashboard_bp
    from app.blueprints.affaires import bp as affaires_bp
    from app.blueprints.formulaires import bp as formulaires_bp
    from app.blueprints.jalons import bp as jalons_bp
    from app.blueprints.referentiels import bp as referentiels_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.api import bp as api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(affaires_bp, url_prefix="/affaires")
    app.register_blueprint(formulaires_bp, url_prefix="/formulaires")
    app.register_blueprint(jalons_bp, url_prefix="/jalons")
    app.register_blueprint(referentiels_bp, url_prefix="/referentiels")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
