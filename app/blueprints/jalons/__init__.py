from flask import Blueprint

bp = Blueprint("jalons", __name__, template_folder="../../templates/jalons")

from app.blueprints.jalons import routes  # noqa: E402, F401
