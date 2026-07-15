"""Commande ``flask import-registre-be`` — import du registre général BE.

Importe (upsert idempotent) les lignes exploitables du fichier Excel
« Registre general commande BE.xlsx » dans la table ``registre_be_items``,
qui alimente la liste déroulante de sélection du n° d'affaire à l'étape Q1
du wizard de création.

Exemple :
    flask import-registre-be "Fichier source/Registre general commande BE.xlsx"

La commande peut être relancée sans risque de doublon à chaque mise à jour
du fichier par le BE.
"""

from __future__ import annotations

from pathlib import Path

import click
from flask.cli import with_appcontext

from app.services.registre_be import import_registre_be


@click.command("import-registre-be")
@click.argument("fichier", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@with_appcontext
def import_registre_be_command(fichier: Path) -> None:
    """Importe le registre général de commande BE depuis un fichier Excel."""
    stats = import_registre_be(fichier)
    click.echo(
        f"[OK] {stats.lignes_lues} ligne(s) exploitable(s) — "
        f"{stats.crees} créée(s), {stats.mis_a_jour} mise(s) à jour."
    )
