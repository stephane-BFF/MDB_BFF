"""Tests d'intégration — fiche technique de l'item (V1.2 Lot 2)."""
from __future__ import annotations

from flask.testing import FlaskClient

from app.extensions import db as _db
from app.models.affaire import Affaire
from app.services import affaire as affaire_svc


class TestFicheTechniqueAcces:
    def test_get_rend_la_fiche(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/fiche-technique")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "Fiche technique de l'item" in body
        assert "Procédés de fabrication" in body
        # q5_ps_bar=10.0 de la fixture est bien relu (préremplissage).
        assert 'value="10.0"' in body

    def test_lien_depuis_page_dossier(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}")
        assert f"/affaires/{affaire.id}/fiche-technique".encode() in resp.data


class TestFicheTechniqueSauvegarde:
    def test_post_enregistre_sous_les_prefixes_historiques(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/fiche-technique",
            data={
                "desp": "y",
                "categorie_ped": "III",
                "module_ped": "H",
                "fluide_etat": "gaz",
                "fluide_groupe": "1",
                "fluide_nom": "Azote",
                "ps_bar": "16",
                "temperature_min_c": "-10",
                "temperature_max_c": "150",
                "volume_l": "40",
                "procedes_soudage": ["141", "111"],
                "tubes_soudes": "y",
                "cnd_methodes": ["RT", "VT"],
                "test_pressions": ["hydrostatique", "azote"],
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        a = _db.session.get(Affaire, affaire.id)
        reponses = a.parametrage.reponses
        assert reponses["q4_desp"] is True
        assert reponses["q4_categorie_ped"] == "III"
        assert reponses["q4_fluide_etat"] == "gaz"
        assert reponses["q5_ps_bar"] == 16.0
        assert reponses["q5_volume_l"] == 40.0
        assert reponses["q6_procedes_soudage"] == ["141", "111"]
        assert reponses["q6_tubes_soudes"] is True
        assert reponses["q7_cnd_methodes"] == ["RT", "VT"]
        assert reponses["q7_test_pressions"] == ["hydrostatique", "azote"]
        assert a.parametrage.template_version == 2

    def test_lecteur_ne_peut_pas_enregistrer(
        self, client: FlaskClient, affaire: Affaire, app: object
    ) -> None:
        from app.enums import Role  # noqa: PLC0415
        from tests.conftest import _login, _make_user  # noqa: PLC0415

        _make_user("lecteur.fiche@bff.fr", "Lec", "Teur", Role.LECTEUR)
        _login(client, "lecteur.fiche@bff.fr")
        resp = client.post(
            f"/affaires/{affaire.id}/fiche-technique",
            data={"fluide_nom": "Eau"},
        )
        assert resp.status_code == 403

    def test_fallback_ancienne_cle_test_pression(
        self, affaire: Affaire, app: object
    ) -> None:
        # Une affaire historique n'a que q7_test_pression (choix unique).
        reponses = dict(affaire.parametrage.reponses)
        reponses["q7_test_pression"] = "hydrostatique"
        affaire.parametrage.reponses = reponses
        _db.session.commit()

        data = affaire_svc.get_fiche_technique(affaire)
        assert data["test_pressions"] == ["hydrostatique"]


class TestVerifierCategorie:
    def test_calcul_ok(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(
            f"/affaires/{affaire.id}/fiche-technique/verifier-categorie"
            "?etat=gaz&groupe=1&ps=100&volume=10"
        )
        data = resp.get_json()
        assert data["ok"] is True
        assert data["categorie"] == "III"
        assert data["tableau"] == 1

    def test_parametres_manquants(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(
            f"/affaires/{affaire.id}/fiche-technique/verifier-categorie?etat=gaz"
        )
        data = resp.get_json()
        assert data["ok"] is False
        assert "renseign" in data["error"]
