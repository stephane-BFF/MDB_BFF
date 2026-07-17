"""Tests d'intégration — wizard de création V1.2 (Q1 Affaire → Q4 Récap).

Couvre le flux registre (préremplissages R/S/T inclus), le flux manuel, la
navigation par stepper (étape max), les modules de catégories supérieures
(art. 14 PED) et les protections (item en doublon, saut en avant).
"""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.enums import Statut, StatutWizard
from app.extensions import db as _db
from app.models.affaire import Affaire
from app.models.referentiel import TypeEquipement
from app.models.registre_be import RegistreBEItem
from app.models.user import User


@pytest.fixture()
def registre_items(app: Flask) -> list[RegistreBEItem]:  # noqa: ARG001
    """Deux items BN0811 au registre BE : un DESP cat IV/H1, un STAMP U seul."""
    rows = [
        RegistreBEItem(
            numero_affaire="BN0811",
            item="8975",
            client_nom="Chantiers de l'Atlantique",
            repere_client="Navire Y34",
            type_appareil="W2 03-01-12",
            nombre=7,
            annee=2026,
            references_client="AEQU-001",
            libelle_brut="BN0811 - RM11721",
            certification_brute="DESP 2014/68/UE",
            desp=True,
            stamp_u=False,
            categorie_risque="IV",
            module_evaluation="H1",
        ),
        RegistreBEItem(
            numero_affaire="BN0811",
            item="8976",
            client_nom="Chantiers de l'Atlantique",
            repere_client="Navire Y35",
            type_appareil="W2 04-01-12",
            nombre=6,
            annee=2026,
            references_client="AEQU-002",
            libelle_brut="BN0811 - RM11722",
            certification_brute="STAMP U",
            desp=False,
            stamp_u=True,
        ),
    ]
    _db.session.add_all(rows)
    _db.session.commit()
    return rows


@pytest.fixture()
def type_equipement(app: Flask) -> TypeEquipement:  # noqa: ARG001
    """Un type d'équipement actif (référentiel D7)."""
    t = TypeEquipement(libelle="SHELL&TUBE", ordre=4, actif=True)
    _db.session.add(t)
    _db.session.commit()
    return t


def _start_wizard(client: FlaskClient) -> int:
    """Démarre un wizard et retourne l'id de l'affaire créée."""
    resp = client.post("/affaires/wizard/start", follow_redirects=False)
    assert resp.status_code == 302
    return int(resp.headers["Location"].rstrip("/").split("/")[-3])


def _post_q1(
    client: FlaskClient,
    affaire_id: int,
    *,
    numero: str = "BN0811",
    manuel: str = "",
    client_nom: str = "Chantiers de l'Atlantique",
) -> object:
    return client.post(
        f"/affaires/{affaire_id}/wizard/Q1",
        data={
            "annee": "2026",
            "numero_affaire": numero,
            "numero_affaire_manuel": manuel,
            "client_nom": client_nom,
            "references_client": "AEQU-001",
        },
        follow_redirects=False,
    )


def _post_q2(
    client: FlaskClient,
    affaire_id: int,
    type_equipement: TypeEquipement,
    *,
    item: str = "8975",
) -> object:
    return client.post(
        f"/affaires/{affaire_id}/wizard/Q2",
        data={
            "item": item,
            "repere": "Navire Y34",
            "type_echangeur": "W2 03-01-12",
            "type_equipement_id": str(type_equipement.id),
            "nombre": "7",
            "annee_construction": "2026",
        },
        follow_redirects=False,
    )


def _post_q3(
    client: FlaskClient,
    affaire_id: int,
    data: dict[str, str] | None = None,
) -> object:
    return client.post(
        f"/affaires/{affaire_id}/wizard/Q3",
        data=data
        if data is not None
        else {"desp": "y", "categorie_ped": "IV", "module_ped": "H1"},
        follow_redirects=False,
    )


class TestWizardFlowRegistre:
    def test_flux_complet_cree_le_dossier(
        self,
        client_redacteur: FlaskClient,
        registre_items: list[RegistreBEItem],
        type_equipement: TypeEquipement,
        user_redacteur: User,
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)

        resp = _post_q1(client_redacteur, affaire_id)
        assert resp.status_code == 302 and "/wizard/Q2" in resp.headers["Location"]

        resp = _post_q2(client_redacteur, affaire_id, type_equipement)
        assert resp.status_code == 302 and "/wizard/Q3" in resp.headers["Location"]

        resp = _post_q3(client_redacteur, affaire_id)
        assert resp.status_code == 302 and "/wizard/Q4" in resp.headers["Location"]

        resp = client_redacteur.post(
            f"/affaires/{affaire_id}/wizard/Q4",
            data={"confirmation": "y", "commentaire": ""},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/affaires/{affaire_id}")

        affaire = _db.session.get(Affaire, affaire_id)
        assert affaire.statut is Statut.BROUILLON
        assert affaire.statut_wizard is None
        assert affaire.references_internes == "BN0811-8975"
        assert affaire.client_nom == "Chantiers de l'Atlantique"
        assert affaire.type_equipement_id == type_equipement.id
        reponses = affaire.parametrage.reponses
        assert reponses["q4_desp"] is True
        assert reponses["q4_stamp_u"] is False
        assert reponses["q4_categorie_ped"] == "IV"
        assert reponses["q4_module_ped"] == "H1"
        assert affaire.jalons  # jalons initialisés à la création

    def test_q3_preremplie_depuis_registre(
        self,
        client_redacteur: FlaskClient,
        registre_items: list[RegistreBEItem],
        type_equipement: TypeEquipement,
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)
        _post_q1(client_redacteur, affaire_id)
        _post_q2(client_redacteur, affaire_id, type_equipement)

        resp = client_redacteur.get(f"/affaires/{affaire_id}/wizard/Q3")
        body = resp.data.decode("utf-8")
        # desp coché, catégorie IV et module H1 présélectionnés (colonnes R/S/T).
        # NB : WTForms trie les attributs HTML par ordre alphabétique.
        assert 'checked class="form-check-input" id="desp"' in body
        assert '<option selected value="IV">' in body
        assert '<option selected value="H1">' in body

    def test_item_inconnu_du_registre_refuse(
        self,
        client_redacteur: FlaskClient,
        registre_items: list[RegistreBEItem],
        type_equipement: TypeEquipement,
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)
        _post_q1(client_redacteur, affaire_id)
        resp = _post_q2(client_redacteur, affaire_id, type_equipement, item="9999")
        assert resp.status_code == 200  # re-rendu avec flash d'erreur
        affaire = _db.session.get(Affaire, affaire_id)
        assert affaire.item is None

    def test_item_deja_utilise_refuse(
        self,
        client_redacteur: FlaskClient,
        registre_items: list[RegistreBEItem],
        type_equipement: TypeEquipement,
        user_redacteur: User,
    ) -> None:
        existante = Affaire(
            numero_affaire="BN0811",
            item="8975",
            annee=2026,
            statut=Statut.BROUILLON,
            cree_par_id=user_redacteur.id,
        )
        _db.session.add(existante)
        _db.session.commit()

        affaire_id = _start_wizard(client_redacteur)
        _post_q1(client_redacteur, affaire_id)
        resp = _post_q2(client_redacteur, affaire_id, type_equipement)
        assert resp.status_code == 200
        assert "existe déjà".encode() in resp.data


class TestWizardFlowManuel:
    def test_flux_manuel_hors_registre(
        self,
        client_redacteur: FlaskClient,
        type_equipement: TypeEquipement,
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)
        resp = _post_q1(
            client_redacteur,
            affaire_id,
            numero="__manuel__",
            manuel="BN0999",
            client_nom="Client hors registre",
        )
        assert resp.status_code == 302 and "/wizard/Q2" in resp.headers["Location"]

        resp = _post_q2(client_redacteur, affaire_id, type_equipement, item="4242")
        assert resp.status_code == 302 and "/wizard/Q3" in resp.headers["Location"]

        affaire = _db.session.get(Affaire, affaire_id)
        assert affaire.numero_affaire == "BN0999"
        assert affaire.references_internes == "BN0999-4242"

    def test_sans_desp_ni_stamp_creation_possible(
        self,
        client_redacteur: FlaskClient,
        type_equipement: TypeEquipement,
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)
        _post_q1(client_redacteur, affaire_id, numero="__manuel__", manuel="BN0998")
        _post_q2(client_redacteur, affaire_id, type_equipement, item="4243")
        # Aucune case cochée : catégorie/module envoyés mais sans objet → purgés.
        resp = _post_q3(
            client_redacteur,
            affaire_id,
            data={"categorie_ped": "IV", "module_ped": "H1"},
        )
        assert resp.status_code == 302

        affaire = _db.session.get(Affaire, affaire_id)
        reponses = affaire.parametrage.reponses
        assert reponses["q4_desp"] is False
        assert reponses["q4_categorie_ped"] == ""
        assert reponses["q4_module_ped"] == ""


class TestModulesSuperieurs:
    """Art. 14 PED : les modules des catégories supérieures sont recevables."""

    def _jusqua_q3(
        self, client: FlaskClient, type_equipement: TypeEquipement
    ) -> int:
        affaire_id = _start_wizard(client)
        _post_q1(client, affaire_id, numero="__manuel__", manuel="BN0997")
        _post_q2(client, affaire_id, type_equipement, item="4244")
        return affaire_id

    def test_module_categorie_superieure_accepte(
        self, client_redacteur: FlaskClient, type_equipement: TypeEquipement
    ) -> None:
        affaire_id = self._jusqua_q3(client_redacteur, type_equipement)
        # Catégorie II : H (module de la catégorie III) est recevable.
        resp = _post_q3(
            client_redacteur,
            affaire_id,
            data={"desp": "y", "categorie_ped": "II", "module_ped": "H"},
        )
        assert resp.status_code == 302
        affaire = _db.session.get(Affaire, affaire_id)
        assert affaire.parametrage.reponses["q4_module_ped"] == "H"

    def test_module_categorie_inferieure_refuse(
        self, client_redacteur: FlaskClient, type_equipement: TypeEquipement
    ) -> None:
        affaire_id = self._jusqua_q3(client_redacteur, type_equipement)
        # Catégorie IV : A (module de la catégorie I) n'est pas recevable.
        resp = _post_q3(
            client_redacteur,
            affaire_id,
            data={"desp": "y", "categorie_ped": "IV", "module_ped": "A"},
        )
        assert resp.status_code == 200
        assert b"non recevable" in resp.data

    def test_categorie_requise_si_desp(
        self, client_redacteur: FlaskClient, type_equipement: TypeEquipement
    ) -> None:
        affaire_id = self._jusqua_q3(client_redacteur, type_equipement)
        resp = _post_q3(
            client_redacteur,
            affaire_id,
            data={"desp": "y", "categorie_ped": "", "module_ped": ""},
        )
        assert resp.status_code == 200
        assert "catégorie de risque est requise".encode() in resp.data


class TestNavigationStepper:
    def test_saut_en_avant_bloque(
        self, client_redacteur: FlaskClient
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)
        resp = client_redacteur.get(
            f"/affaires/{affaire_id}/wizard/Q3", follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/wizard/Q1" in resp.headers["Location"]

    def test_retour_sur_etape_franchie_autorise(
        self,
        client_redacteur: FlaskClient,
        registre_items: list[RegistreBEItem],
        type_equipement: TypeEquipement,
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)
        _post_q1(client_redacteur, affaire_id)
        _post_q2(client_redacteur, affaire_id, type_equipement)

        resp = client_redacteur.get(f"/affaires/{affaire_id}/wizard/Q1")
        assert resp.status_code == 200

    def test_reenregistrer_une_etape_ne_recule_pas_le_max(
        self,
        client_redacteur: FlaskClient,
        registre_items: list[RegistreBEItem],
        type_equipement: TypeEquipement,
    ) -> None:
        affaire_id = _start_wizard(client_redacteur)
        _post_q1(client_redacteur, affaire_id)
        _post_q2(client_redacteur, affaire_id, type_equipement)
        affaire = _db.session.get(Affaire, affaire_id)
        assert affaire.statut_wizard is StatutWizard.Q3

        # Ré-enregistre Q1 : redirige vers Q2, mais le max reste Q3.
        resp = _post_q1(client_redacteur, affaire_id, client_nom="Client corrigé")
        assert resp.status_code == 302 and "/wizard/Q2" in resp.headers["Location"]
        _db.session.expire_all()
        affaire = _db.session.get(Affaire, affaire_id)
        assert affaire.statut_wizard is StatutWizard.Q3
        assert affaire.client_nom == "Client corrigé"
