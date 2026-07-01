"""Tests unitaires — tâches Celery d'alertes email (`app.services.tasks_alertes`).

Les services métier et l'envoi email sont mockés : on valide l'orchestration
et le dict de retour, sans SMTP ni base peuplée. Celery s'exécute en synchrone
(``CELERY_TASK_ALWAYS_EAGER=True``).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from app.services import tasks_alertes


class TestSendAlertesJalons:
    def test_envoi_ok(self, app: Flask) -> None:
        jalons = [SimpleNamespace(), SimpleNamespace()]
        with app.app_context(), patch(
            "app.services.jalons.get_jalons_en_retard", return_value=jalons
        ), patch(
            "app.services.email.send_alerte_jalons_retard", return_value=True
        ) as mock_send:
            result = tasks_alertes.send_alertes_jalons.run()
        assert result == {"sent": True, "nb_jalons": 2}
        mock_send.assert_called_once_with(jalons)

    def test_aucun_jalon(self, app: Flask) -> None:
        with app.app_context(), patch(
            "app.services.jalons.get_jalons_en_retard", return_value=[]
        ), patch("app.services.email.send_alerte_jalons_retard", return_value=True):
            result = tasks_alertes.send_alertes_jalons.run()
        assert result == {"sent": True, "nb_jalons": 0}


class TestSendAlertesCerts:
    def test_filtre_les_jalons(self, app: Flask) -> None:
        alertes = [
            SimpleNamespace(type="soudeur"),
            SimpleNamespace(type="jalon"),      # doit être exclu
            SimpleNamespace(type="instrument"),
        ]
        with app.app_context(), patch(
            "app.services.alertes.get_alertes_actives", return_value=alertes
        ), patch(
            "app.services.email.send_alerte_certifications", return_value=True
        ) as mock_send:
            result = tasks_alertes.send_alertes_certs.run()
        assert result == {"sent": True, "nb_alertes": 2}
        # Les jalons ne sont pas transmis à l'email certifications.
        envoyees = mock_send.call_args.args[0]
        assert all(a.type != "jalon" for a in envoyees)
