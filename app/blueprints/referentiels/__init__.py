from flask import Blueprint

bp = Blueprint("referentiels", __name__, template_folder="../../templates/referentiels")

from app.blueprints.referentiels import routes  # noqa: E402, F401
