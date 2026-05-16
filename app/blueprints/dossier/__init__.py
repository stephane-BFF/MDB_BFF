"""Blueprint Dossier — assemblage et téléchargement du dossier PDF complet."""
from flask import Blueprint

bp = Blueprint("dossier", __name__)

from app.blueprints.dossier import routes  # noqa: E402, F401
