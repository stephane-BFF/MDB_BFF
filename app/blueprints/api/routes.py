"""API REST ``/api/v1/`` — accès en lecture aux dossiers MDB BFF.

Périmètre V1 (lecture seule) : consultation des affaires, de leurs formulaires,
de leurs jalons et du statut d'avancement. **Aucune écriture métier** n'est
exposée : la création/validation/signature reste dans l'interface web, pour ne
pas contourner le workflow de signature (hash SHA-256, audit trail).

Authentification : jeton porteur par utilisateur (``Authorization: Bearer <token>``
ou en-tête ``X-API-Key``). Le jeton est émis via ``flask api-token issue <email>``.

Réponses : JSON UTF-8. Les erreurs suivent un format uniforme
``{"error": {"code": <http>, "message": "..."}}``.

Documentation machine : ``GET /api/v1/openapi.json`` (OpenAPI 3.0 minimal).
"""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from flask import g, jsonify, request
from werkzeug.exceptions import HTTPException

from app.blueprints.api import bp
from app.enums import JalonCode
from app.extensions import db
from app.models.affaire import Affaire
from app.models.jalon import Jalon
from app.models.user import User

if TYPE_CHECKING:
    from flask.wrappers import Response

API_VERSION = "1.0.0"
_MAX_PER_PAGE = 100
_DEFAULT_PER_PAGE = 20


# ── Authentification par jeton ─────────────────────────────────────────────


def _extract_token() -> str | None:
    """Extrait le jeton de ``Authorization: Bearer`` ou de ``X-API-Key``."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer ") :].strip()
    api_key = request.headers.get("X-API-Key")
    return api_key.strip() if api_key else None


def api_token_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """Protège une route API : jeton porteur valide requis.

    En cas d'absence/invalidité du jeton, répond ``401`` JSON. L'utilisateur
    authentifié est déposé dans ``flask.g.api_user``.
    """

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        token = _extract_token()
        if not token:
            return _error(401, "Jeton d'API manquant (Authorization: Bearer …).")
        user = User.by_api_token(token)
        if user is None:
            return _error(401, "Jeton d'API invalide ou révoqué.")
        g.api_user = user
        return view(*args, **kwargs)

    return wrapped


# ── Sérialiseurs ────────────────────────────────────────────────────────────


def _serialize_affaire(affaire: Affaire, *, detail: bool = False) -> dict[str, Any]:
    """Sérialise une affaire (résumé ou détail)."""
    data: dict[str, Any] = {
        "id": affaire.id,
        "numero_affaire": affaire.numero_affaire,
        "annee": affaire.annee,
        "client_nom": affaire.client_nom,
        "repere": affaire.repere,
        "type_echangeur": affaire.type_echangeur,
        "statut": affaire.statut.value,
        "created_at": _iso(affaire.created_at),
    }
    if detail:
        data["references_client"] = affaire.references_client
        data["references_internes"] = affaire.references_internes
        data["nombre"] = affaire.nombre
        data["annee_construction"] = affaire.annee_construction
        data["formulaires"] = [_serialize_formulaire(f) for f in affaire.formulaires]
        data["jalons"] = [_serialize_jalon(j) for j in affaire.jalons]
        data["avancement"] = _avancement(affaire)
    return data


def _serialize_formulaire(formulaire: Any) -> dict[str, Any]:
    """Sérialise un formulaire (métadonnées + statut, sans le contenu ``data``)."""
    return {
        "id": formulaire.id,
        "code": formulaire.code,
        "chapitre": formulaire.chapitre.value,
        "statut": formulaire.statut.value,
        "template_version": formulaire.template_version,
        "signe": formulaire.is_signed,
    }


def _serialize_jalon(jalon: Jalon) -> dict[str, Any]:
    """Sérialise un jalon (statut + prérequis effectifs)."""
    return {
        "code": jalon.code.value,
        "label": jalon.label,
        "statut": jalon.statut.value,
        "date_prevue": _iso(jalon.date_prevue),
        "date_reelle": _iso(jalon.date_reelle),
        "prerequis": jalon.effective_prerequis,
        "verrouille": jalon.est_verrouille,
    }


def _avancement(affaire: Affaire) -> dict[str, Any]:
    """Calcule un résumé d'avancement (formulaires signés, jalons franchis)."""
    from app.enums import Statut, StatutJalon  # noqa: PLC0415

    formulaires = affaire.formulaires
    signes = sum(1 for f in formulaires if f.statut is Statut.SIGNE)
    jalons = affaire.jalons
    franchis = sum(1 for j in jalons if j.statut is StatutJalon.FRANCHI)
    return {
        "formulaires_total": len(formulaires),
        "formulaires_signes": signes,
        "jalons_total": len(jalons),
        "jalons_franchis": franchis,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────


@bp.route("/health", methods=["GET"])
def health() -> Response:
    """Sonde de disponibilité (sans authentification)."""
    return jsonify({"status": "ok", "version": API_VERSION})


@bp.route("/affaires", methods=["GET"])
@api_token_required
def list_affaires() -> Response:
    """Liste paginée des affaires.

    Query params :
        - ``page`` (défaut 1)
        - ``per_page`` (défaut 20, max 100)
        - ``statut`` (filtre optionnel, ex: ``signe``)
        - ``annee`` (filtre optionnel)
    """
    page = _positive_int(request.args.get("page"), default=1, minimum=1)
    per_page = _positive_int(
        request.args.get("per_page"), default=_DEFAULT_PER_PAGE, minimum=1, maximum=_MAX_PER_PAGE
    )

    query = db.session.query(Affaire)
    statut = request.args.get("statut")
    if statut:
        from app.enums import Statut  # noqa: PLC0415

        try:
            query = query.filter(Affaire.statut == Statut(statut))
        except ValueError:
            return _error(400, f"Statut inconnu : {statut!r}.")
    annee = request.args.get("annee")
    if annee:
        query = query.filter(Affaire.annee == _positive_int(annee, default=0, minimum=0))

    query = query.order_by(Affaire.id.desc())
    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()

    return jsonify(
        {
            "items": [_serialize_affaire(a) for a in items],
            "page": page,
            "per_page": per_page,
            "total": total,
        }
    )


@bp.route("/affaires/<int:affaire_id>", methods=["GET"])
@api_token_required
def get_affaire(affaire_id: int) -> Response:
    """Détail d'une affaire (formulaires + jalons + avancement)."""
    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        return _error(404, f"Affaire {affaire_id} introuvable.")
    return jsonify(_serialize_affaire(affaire, detail=True))


@bp.route("/affaires/<int:affaire_id>/formulaires", methods=["GET"])
@api_token_required
def list_formulaires(affaire_id: int) -> Response:
    """Liste des formulaires d'une affaire."""
    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        return _error(404, f"Affaire {affaire_id} introuvable.")
    return jsonify({"items": [_serialize_formulaire(f) for f in affaire.formulaires]})


@bp.route("/affaires/<int:affaire_id>/jalons", methods=["GET"])
@api_token_required
def list_jalons(affaire_id: int) -> Response:
    """Liste des jalons JP0–JP6 d'une affaire (ordre canonique)."""
    affaire = db.session.get(Affaire, affaire_id)
    if affaire is None:
        return _error(404, f"Affaire {affaire_id} introuvable.")
    jalons = sorted(affaire.jalons, key=lambda j: _jalon_order(j.code))
    return jsonify({"items": [_serialize_jalon(j) for j in jalons]})


@bp.route("/openapi.json", methods=["GET"])
def openapi() -> Response:
    """Spécification OpenAPI 3.0 minimale décrivant l'API."""
    return jsonify(_openapi_spec())


# ── Gestion d'erreurs (JSON) ────────────────────────────────────────────────


@bp.errorhandler(HTTPException)
def _handle_http_exception(exc: HTTPException) -> tuple[Response, int]:
    """Convertit toute HTTPException levée dans l'API en JSON uniforme."""
    code = exc.code or 500
    return jsonify({"error": {"code": code, "message": exc.description}}), code


@bp.errorhandler(Exception)
def _handle_unexpected(exc: Exception) -> tuple[Response, int]:
    """Filet de sécurité : erreur non prévue → 500 JSON (pas de HTML de debug)."""
    from flask import current_app  # noqa: PLC0415

    current_app.logger.error("api.unhandled", extra={"error": str(exc)})
    return jsonify({"error": {"code": 500, "message": "Erreur interne."}}), 500


# ── Helpers ────────────────────────────────────────────────────────────────


def _error(code: int, message: str) -> tuple[Response, int]:
    """Construit une réponse d'erreur JSON uniforme."""
    return jsonify({"error": {"code": code, "message": message}}), code


def _iso(value: Any) -> str | None:
    """Formate une date/datetime en ISO 8601, ou ``None``."""
    return value.isoformat() if value is not None else None


def _positive_int(
    raw: str | None, *, default: int, minimum: int = 0, maximum: int | None = None
) -> int:
    """Parse un entier borné depuis une query string (tolérant aux valeurs invalides)."""
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _jalon_order(code: JalonCode) -> int:
    """Ordre numérique d'un jalon (JP0 → 0 … JP6 → 6)."""
    return code.numero


def _openapi_spec() -> dict[str, Any]:
    """Spécification OpenAPI 3.0 minimale (documentation machine)."""
    bearer = {"BearerAuth": []}
    ok_json = {"content": {"application/json": {"schema": {"type": "object"}}}}
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "API MDB BFF",
            "version": API_VERSION,
            "description": "Accès en lecture aux dossiers constructeurs qualité BFF.",
        },
        "servers": [{"url": "/api/v1"}],
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer"}
            }
        },
        "paths": {
            "/health": {
                "get": {
                    "summary": "Sonde de disponibilité",
                    "security": [],
                    "responses": {"200": {"description": "OK", **ok_json}},
                }
            },
            "/affaires": {
                "get": {
                    "summary": "Liste paginée des affaires",
                    "security": [bearer],
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "statut", "in": "query", "schema": {"type": "string"}},
                        {"name": "annee", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {
                        "200": {"description": "Liste", **ok_json},
                        "401": {"description": "Jeton manquant/invalide"},
                    },
                }
            },
            "/affaires/{affaire_id}": {
                "get": {
                    "summary": "Détail d'une affaire",
                    "security": [bearer],
                    "parameters": [
                        {
                            "name": "affaire_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Affaire", **ok_json},
                        "404": {"description": "Introuvable"},
                    },
                }
            },
            "/affaires/{affaire_id}/formulaires": {
                "get": {
                    "summary": "Formulaires d'une affaire",
                    "security": [bearer],
                    "responses": {"200": {"description": "Liste", **ok_json}},
                }
            },
            "/affaires/{affaire_id}/jalons": {
                "get": {
                    "summary": "Jalons d'une affaire",
                    "security": [bearer],
                    "responses": {"200": {"description": "Liste", **ok_json}},
                }
            },
        },
    }
