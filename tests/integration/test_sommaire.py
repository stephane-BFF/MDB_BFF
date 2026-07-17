"""Tests d'intégration — architecture type et sommaire du dossier (V1.2 Lot 6)."""
from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from app.enums import Statut, StatutWizard
from app.extensions import db as _db
from app.models.affaire import Affaire
from app.models.referentiel import TypeEquipement
from app.models.user import User
from app.services import affaire as affaire_svc


class TestFormulaireInclus:
    def test_composition_null_inclut_tout(self, affaire: Affaire, app: Flask) -> None:
        assert affaire.composition_dossier is None
        assert affaire_svc.formulaire_inclus(affaire, "HYDR") is True

    def test_composition_filtre(self, affaire: Affaire, app: Flask) -> None:
        affaire.composition_dossier = ["HYDR", "CONFCOM"]
        assert affaire_svc.formulaire_inclus(affaire, "HYDR") is True
        assert affaire_svc.formulaire_inclus(affaire, "PESAGE") is False


class TestPageSommaire:
    def test_get_liste_les_formulaires_coches(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.get(f"/affaires/{affaire.id}/sommaire")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "Sommaire du dossier constructeur" in body
        assert "Architecture complète (par défaut)" in body
        # Tous les templates actifs sont cochés (composition NULL).
        assert 'value="HYDR" id="som-HYDR"\n                       checked' in body \
            or ("som-HYDR" in body and "checked" in body)

    def test_post_enregistre_la_composition(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        resp = client_redacteur.post(
            f"/affaires/{affaire.id}/sommaire",
            data={"codes": ["HYDR", "CONFCOM"]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        _db.session.expire_all()
        a = _db.session.get(Affaire, affaire.id)
        assert a.composition_dossier == ["CONFCOM", "HYDR"]

    def test_exclusion_masque_sur_la_page_dossier(
        self, client_redacteur: FlaskClient, affaire: Affaire
    ) -> None:
        client_redacteur.post(
            f"/affaires/{affaire.id}/sommaire",
            data={"codes": ["CONFCOM"]},
        )
        resp = client_redacteur.get(f"/affaires/{affaire.id}")
        body = resp.data.decode("utf-8")
        assert "CONFCOM" in body
        # HYDR exclu : plus de lien vers son formulaire sur la page dossier.
        assert f"/affaires/{affaire.id}/formulaires/HYDR" not in body

    def test_lecteur_ne_peut_pas_modifier(
        self, client: FlaskClient, affaire: Affaire, app: Flask
    ) -> None:
        from app.enums import Role  # noqa: PLC0415
        from tests.conftest import _login, _make_user  # noqa: PLC0415

        _make_user("lecteur.som@bff.fr", "Lec", "Teur", Role.LECTEUR)
        _login(client, "lecteur.som@bff.fr")
        resp = client.post(
            f"/affaires/{affaire.id}/sommaire", data={"codes": ["HYDR"]}
        )
        assert resp.status_code == 403


class TestInitialisationParTypeEquipement:
    def test_finish_wizard_copie_l_architecture_type(
        self, app: Flask, user_redacteur: User
    ) -> None:
        type_allege = TypeEquipement(
            libelle="FAISCEAU de rechange",
            formulaires_defaut=["CONFCOM", "BIM"],
            actif=True,
        )
        _db.session.add(type_allege)
        _db.session.flush()
        affaire = Affaire(
            numero_affaire="BN0900",
            item="1234",
            references_internes="BN0900-1234",
            annee=2026,
            client_nom="Client",
            statut=Statut.WIZARD_BROUILLON,
            statut_wizard=StatutWizard.Q4,
            type_equipement_id=type_allege.id,
            cree_par_id=user_redacteur.id,
        )
        _db.session.add(affaire)
        _db.session.commit()

        affaire_svc.finish_wizard(affaire, user=user_redacteur)
        assert affaire.composition_dossier == ["CONFCOM", "BIM"]

    def test_type_sans_architecture_laisse_null(
        self, app: Flask, user_redacteur: User
    ) -> None:
        type_complet = TypeEquipement(libelle="SHELL&TUBE", actif=True)
        _db.session.add(type_complet)
        _db.session.flush()
        affaire = Affaire(
            numero_affaire="BN0901",
            item="1235",
            annee=2026,
            statut=Statut.WIZARD_BROUILLON,
            statut_wizard=StatutWizard.Q4,
            type_equipement_id=type_complet.id,
            cree_par_id=user_redacteur.id,
        )
        _db.session.add(affaire)
        _db.session.commit()

        affaire_svc.finish_wizard(affaire, user=user_redacteur)
        assert affaire.composition_dossier is None


class TestArchitectureTypeReferentiel:
    def test_edition_de_l_architecture_type(
        self, client_approbateur: FlaskClient, app: Flask
    ) -> None:
        t = TypeEquipement(libelle="BHM", actif=True)
        _db.session.add(t)
        _db.session.commit()

        resp = client_approbateur.get(f"/referentiels/types-equipement/{t.id}/architecture")
        assert resp.status_code == 200

        resp = client_approbateur.post(
            f"/referentiels/types-equipement/{t.id}/architecture",
            data={"codes": ["HYDR", "CONFCOM"]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        _db.session.expire_all()
        assert _db.session.get(TypeEquipement, t.id).formulaires_defaut == [
            "CONFCOM",
            "HYDR",
        ]

    def test_retour_au_dossier_complet(
        self, client_approbateur: FlaskClient, app: Flask
    ) -> None:
        t = TypeEquipement(
            libelle="RM", formulaires_defaut=["HYDR"], actif=True
        )
        _db.session.add(t)
        _db.session.commit()

        client_approbateur.post(
            f"/referentiels/types-equipement/{t.id}/architecture",
            data={"dossier_complet": "1", "codes": ["HYDR"]},
        )
        _db.session.expire_all()
        assert _db.session.get(TypeEquipement, t.id).formulaires_defaut is None
