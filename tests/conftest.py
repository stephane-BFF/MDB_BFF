"""Configuration pytest — fixtures partagées pour tous les tests MDB BFF."""
import pytest
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Instance Flask configurée pour les tests (base SQLite en mémoire)."""
    _app = create_app("testing")
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Client HTTP Flask pour les tests d'intégration."""
    return app.test_client()


@pytest.fixture()
def db(app):
    """Session de base de données avec rollback automatique après chaque test."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        yield _db
        transaction.rollback()
        connection.close()
