"""Tests d'intégration — internationalisation Flask-Babel (FR/EN/DE/IT)."""
from __future__ import annotations

from flask.testing import FlaskClient


def _body(client: FlaskClient, url: str) -> str:
    return client.get(url).data.decode("utf-8")


class TestSelecteurLangue:
    def test_defaut_francais(self, client: FlaskClient) -> None:
        body = _body(client, "/auth/login")
        assert "Dossier Constructeur Qualité" in body
        assert 'lang="fr"' in body

    def test_anglais(self, client: FlaskClient) -> None:
        body = _body(client, "/auth/login?lang=en")
        assert "Manufacturer Quality Data Book" in body
        assert 'lang="en"' in body

    def test_allemand(self, client: FlaskClient) -> None:
        body = _body(client, "/auth/login?lang=de")
        assert "Herstellerqualitätsdokumentation" in body

    def test_italien(self, client: FlaskClient) -> None:
        body = _body(client, "/auth/login?lang=it")
        assert "Fascicolo qualità del costruttore" in body

    def test_langue_inconnue_retombe_sur_defaut(self, client: FlaskClient) -> None:
        body = _body(client, "/auth/login?lang=zz")
        assert "Dossier Constructeur Qualité" in body

    def test_langue_persiste_en_session(self, client: FlaskClient) -> None:
        # Bascule en anglais…
        client.get("/auth/login?lang=en")
        # …puis une requête sans paramètre conserve l'anglais.
        body = _body(client, "/auth/login")
        assert "Manufacturer Quality Data Book" in body


class TestCatalogues:
    def test_traductions_chargees(self, app) -> None:  # noqa: ANN001
        """Vérifie que gettext renvoie bien la traduction pour chaque langue."""
        from flask_babel import force_locale, gettext

        attendus = {
            "en": "Log out",
            "de": "Abmelden",
            "it": "Esci",
        }
        with app.test_request_context():
            for locale, attendu in attendus.items():
                with force_locale(locale):
                    assert gettext("Se déconnecter") == attendu
