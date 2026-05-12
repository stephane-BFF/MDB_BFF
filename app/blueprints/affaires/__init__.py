from flask import Blueprint

bp = Blueprint("affaires", __name__, template_folder="../../templates/affaires")

from app.blueprints.affaires import routes  # noqa: E402, F401
