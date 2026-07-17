"""Tests d'intégration — regroupement par affaire (V1.2 Lot 3)."""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Statut, StatutWizard
from app.extensions import db as _db
from app.models.affaire import Affaire
from app.models.registre_be import RegistreBEItem
from app.models.user import User


@pytest.fixture()
def deux_dossiers(app: Flask, user_redacteur: User) -> list[Affaire]:  # noqa: ARG001
    """Deux dossiers BN0811 : item 8975 en BROUILLON, item 8976 SIGNÉ."""
    d1 = Affaire(
        numero_affaire="BN0811",
        item="8975",
        references_internes="BN0811-8975",
        annee=2026,
        client_nom="Chantiers de l'Atlantique",
        references_client="AEQU-001",
        repere="Navire Y34",
        statut=Statut.BROUILLON,
        cree_par_id=user_redacteur.id,
    )
    d2 = Affaire(
        numero_affaire="BN0811",
        item="8976",
        references_internes="BN0811-8976",
        annee=2026,
        client_nom="Chantiers de l'Atlantique",
        statut=Statut.SIGNE,
        cree_par_id=user_redacteur.id,
    )
    _db.session.add_all([d1, d2])
    _db.session.commit()
    return [d1, d2]


@pytest.fixture()
def registre_bn0811(app: Flask) -> list[RegistreBEItem]:  # noqa: ARG001
    """Trois items BN0811 au registre — le 8977 n'a pas encore de dossier."""
    rows = [
        RegistreBEItem(numero_affaire="BN0811", item=i, client_nom="Chantiers de l'Atlantique")
        for i in ("8975", "8976", "8977")
    ]
    _db.session.add_all(rows)
    _db.session.commit()
    return rows


class TestPageParAffaire:
    def test_404_si_affaire_inconnue(self, client_redacteur: FlaskClient) -> None:
        assert client_redacteur.get("/affaires/par-affaire/BN9999").status_code == 404

    def test_liste_les_dossiers_et_items_restants(
        self,
        client_redacteur: FlaskClient,
        deux_dossiers: list[Affaire],
        registre_bn0811: list[RegistreBEItem],
    ) -> None:
        resp = client_redacteur.get("/affaires/par-affaire/BN0811")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "BN0811-8975" in body
        assert "BN0811-8976" in body
        assert "2 dossiers" in body
        # L'item 8977 du registre n'a pas de dossier → listé comme restant.
        assert "8977" in body

    def test_breadcrumb_depuis_le_dossier(
        self, client_redacteur: FlaskClient, deux_dossiers: list[Affaire]
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{deux_dossiers[0].id}")
        assert b"/affaires/par-affaire/BN0811" in resp.data


class TestNouvelItem:
    def test_demarre_le_wizard_a_l_etape_item(
        self, client_redacteur: FlaskClient, deux_dossiers: list[Affaire]
    ) -> None:
        resp = client_redacteur.post(
            "/affaires/par-affaire/BN0811/nouvel-item", follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/wizard/Q2" in resp.headers["Location"]

        nouveau = (
            _db.session.query(Affaire)
            .filter(Affaire.statut == Statut.WIZARD_BROUILLON)
            .one()
        )
        assert nouveau.numero_affaire == "BN0811"
        assert nouveau.statut_wizard is StatutWizard.Q2
        # Infos génériques reprises du dossier le plus récent de l'affaire.
        assert nouveau.client_nom == "Chantiers de l'Atlantique"
        assert nouveau.annee == 2026

    def test_lecteur_refuse(
        self, client: FlaskClient, deux_dossiers: list[Affaire], app: Flask
    ) -> None:
        from app.enums import Role  # noqa: PLC0415
        from tests.conftest import _login, _make_user  # noqa: PLC0415

        _make_user("lecteur.pa@bff.fr", "Lec", "Teur", Role.LECTEUR)
        _login(client, "lecteur.pa@bff.fr")
        resp = client.post("/affaires/par-affaire/BN0811/nouvel-item")
        assert resp.status_code == 403


class TestPropagationInfosGeneriques:
    def test_propage_aux_dossiers_modifiables_seulement(
        self, client_redacteur: FlaskClient, deux_dossiers: list[Affaire]
    ) -> None:
        resp = client_redacteur.post(
            "/affaires/par-affaire/BN0811/infos-generiques",
            data={
                "client_nom": "Chantiers de l'Atlantique — Nouveau nom",
                "references_client": "AEQU-002",
                "confirmer": "1",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "1 dossier(s)" in body
        assert "non modifiable" in body

        _db.session.expire_all()
        brouillon = _db.session.get(Affaire, deux_dossiers[0].id)
        signe = _db.session.get(Affaire, deux_dossiers[1].id)
        assert brouillon.client_nom == "Chantiers de l'Atlantique — Nouveau nom"
        assert signe.client_nom == "Chantiers de l'Atlantique"  # inchangé

    def test_sans_confirmation_rien_ne_change(
        self, client_redacteur: FlaskClient, deux_dossiers: list[Affaire]
    ) -> None:
        client_redacteur.post(
            "/affaires/par-affaire/BN0811/infos-generiques",
            data={"client_nom": "Autre nom"},
        )
        _db.session.expire_all()
        assert (
            _db.session.get(Affaire, deux_dossiers[0].id).client_nom
            == "Chantiers de l'Atlantique"
        )


class TestVueGroupee:
    def test_vue_groupee_agrege_par_numero(
        self, client_redacteur: FlaskClient, deux_dossiers: list[Affaire]
    ) -> None:
        resp = client_redacteur.get("/affaires/?vue=groupee")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "BN0811" in body
        assert "vue groupée" in body
        assert "/affaires/par-affaire/BN0811" in body
