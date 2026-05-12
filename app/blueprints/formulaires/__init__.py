from flask import Blueprint

bp = Blueprint("formulaires", __name__, template_folder="../../templates/formulaires")

from app.blueprints.formulaires import routes  # noqa: E402, F401
