"""Configuration de l'application par environnement."""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-key-insecure-change-me")
    WTF_CSRF_ENABLED: bool = True
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(
        minutes=int(os.environ.get("SESSION_TIMEOUT_MINUTES", "480"))
    )
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # PostgreSQL
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/mdb_bff"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Réseau BFF — chemin UNC Windows ou chemin local dev
    NETWORK_BASE_PATH: str = os.environ.get("NETWORK_BASE_PATH", "pdf_output")

    # Email
    MAIL_SERVER: str = os.environ.get("SMTP_SERVER", "localhost")
    MAIL_PORT: int = int(os.environ.get("SMTP_PORT", "587"))
    MAIL_USERNAME: str = os.environ.get("SMTP_USER", "")
    MAIL_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
    MAIL_USE_TLS: bool = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    ALERT_EMAIL: str = os.environ.get("ALERT_EMAIL", "")

    # Uploads
    MAX_CONTENT_LENGTH: int = (
        int(os.environ.get("MAX_UPLOAD_SIZE_MB", "20")) * 1024 * 1024
    )
    ALLOWED_EXTENSIONS: frozenset = frozenset({"pdf", "jpg", "jpeg", "png", "tiff"})

    # PDF
    LOGO_PATH: str = os.environ.get("LOGO_PATH", "static/img/logo_bff.png")

    # Celery / Redis — génération PDF asynchrone
    # Les clés sont préfixées CELERY_ pour celery_app.config_from_object(namespace="CELERY")
    CELERY_BROKER_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list = ["json"]
    CELERY_TIMEZONE: str = "Europe/Paris"

    # Authentification Windows / LDAP Active Directory
    WINDOWS_AUTH_ENABLED: bool = (
        os.environ.get("WINDOWS_AUTH_ENABLED", "false").lower() == "true"
    )
    LDAP_SERVER: str = os.environ.get("LDAP_SERVER", "")
    LDAP_BASE_DN: str = os.environ.get("LDAP_BASE_DN", "")
    LDAP_BIND_DN: str = os.environ.get("LDAP_BIND_DN", "")
    LDAP_BIND_PASSWORD: str = os.environ.get("LDAP_BIND_PASSWORD", "")


class DevelopmentConfig(Config):
    DEBUG: bool = True
    SQLALCHEMY_ECHO: bool = False  # True pour voir les requêtes SQL en console


class ProductionConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True  # Requiert HTTPS
    WTF_CSRF_SSL_STRICT: bool = True


config_by_name: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
