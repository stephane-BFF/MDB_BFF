"""Blueprint Fichiers — import et gestion des fichiers extérieurs d'une affaire."""
from flask import Blueprint

bp = Blueprint("fichiers", __name__)

from app.blueprints.fichiers import routes  # noqa: E402, F401
