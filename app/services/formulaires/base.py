"""Infrastructure générique des services formulaires MDB BFF.

Toute logique du workflow (BROUILLON → VALIDE → SIGNE) et de la
sanitisation est implémentée ici une seule fois.  Chaque nouveau
formulaire « simple » n'a besoin de déclarer que :

    - ``CODE`` / ``CHAPITRE`` / ``TITLE`` / ``TITLE_EN``
    - ``SECTIONS`` : liste de ``SectionSpec`` décrivant les champs
    - ``REQUIRED_FOR_VALIDATION`` : champs obligatoires pour valider

Et d'éventuellement surcharger ``_sanitize_payload`` pour les champs
calculés (ex : PESAGE recalcule la masse nette).

Pour les formulaires à tableau dynamique, hériter de
``TableFormulaireService`` et déclarer ``HEADER_SECTIONS``,
``TABLE_SPEC``, ``REQUIRED_HEADER`` et ``REQUIRED_LIGNES``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

from flask_babel.speaklater import LazyString

from app.enums import Chapitre, Statut
from app.extensions import db
from app.models.audit import AuditTrail
from app.models.formulaire import Formulaire, FormulaireTemplate
from app.models.signature import Signature

if TYPE_CHECKING:
    from app.models.affaire import Affaire
    from app.models.user import User


# ── Types de champ ────────────────────────────────────────────────────────

FieldType = Literal["text", "float", "integer", "date", "select", "checkbox", "textarea"]

# Libellé affichable : str brut ou chaîne paresseuse Flask-Babel (lazy_gettext),
# évaluée dans la locale de la requête au moment du rendu.
I18nStr: TypeAlias = str | LazyString


# ── Spécification des champs (formulaires simples) ────────────────────────

@dataclass
class FieldSpec:
    """Décrit un champ de saisie dans un formulaire simple.

    Attributes:
        name: Clé dans ``Formulaire.data`` (snake_case).
        label: Libellé affiché à l'utilisateur (en français).
        field_type: Type de contrôle HTML à rendre.
        required: Affiche un astérisque et bloque la validation si absent.
        options: Paires ``(valeur, libellé)`` pour les selects.
        step: Pas de saisie pour les champs numériques (ex: ``"0.1"``).
        min_val: Valeur minimale (attribut HTML ``min``).
        max_val: Valeur maximale (attribut HTML ``max``).
        maxlength: Longueur maximale pour text/textarea.
        rows: Nombre de lignes pour textarea.
        col_class: Classe Bootstrap de largeur de colonne.
        server_computed: Si True, le champ est readonly même en édition
            (valeur calculée côté serveur, ex : masse nette).
        help_text: Texte d'aide affiché sous le champ.
        datalist: Si renseigné, le champ (texte) devient auto-complété via un
            ``<datalist>`` alimenté par ``get_reference_options()`` ;
            sélectionner une valeur peut renseigner d'autres champs.
        visible_when: Condition d'affichage ``{"field": <nom>, "not_in":
            [<valeurs>]}`` — le champ n'est visible que si le champ référencé
            n'a pas l'une de ces valeurs (ex : n° de certificat masqué si le
            module ne requiert pas d'organisme notifié).
    """

    name: str
    label: I18nStr
    field_type: FieldType
    required: bool = False
    options: list[tuple[str, I18nStr]] = field(default_factory=list)
    step: str | None = None
    min_val: str | None = None
    max_val: str | None = None
    maxlength: int | None = None
    rows: int = 3
    col_class: str = "col-sm-6 col-md-3"
    server_computed: bool = False
    help_text: I18nStr = ""
    datalist: str | None = None
    visible_when: dict[str, Any] | None = None


@dataclass
class SectionSpec:
    """Regroupe des champs sous un titre de section dans le formulaire."""

    title: I18nStr
    fields: list[FieldSpec]


# ── Spécification des colonnes (formulaires tableau) ──────────────────────

@dataclass
class ColSpec:
    """Décrit une colonne dans un tableau dynamique de formulaire.

    Attributes:
        name: Clé dans chaque ligne de ``lignes`` (snake_case).
        label: En-tête de colonne (en français).
        col_type: Type de champ HTML dans la cellule.
        required: La colonne est obligatoire sur chaque ligne.
        options: Paires ``(valeur, libellé)`` pour les selects.
        step: Pas pour les numériques.
        min_val: Valeur minimale (attribut HTML ``min``).
        max_val: Valeur maximale (attribut HTML ``max``).
        maxlength: Longueur maximale pour text.
        server_computed: Si True, cellule readonly calculée côté serveur.
        width: Classe CSS de largeur de colonne (ex: ``"w-25"``).
        help_text: Tooltip affiché dans l'en-tête de colonne.
        datalist: Si renseigné, la cellule (texte) devient un champ
            auto-complété adossé à un ``<datalist>`` alimenté par
            ``get_reference_options()`` ; sélectionner une valeur peut
            renseigner automatiquement d'autres colonnes de la même ligne.
    """

    name: str
    label: I18nStr
    col_type: FieldType
    required: bool = False
    options: list[tuple[str, I18nStr]] = field(default_factory=list)
    step: str | None = None
    min_val: str | None = None
    max_val: str | None = None
    maxlength: int | None = None
    server_computed: bool = False
    width: str = ""
    help_text: I18nStr = ""
    datalist: str | None = None


@dataclass
class TableSpec:
    """Décrit un tableau dynamique (lignes ajoutables/supprimables)."""

    title: I18nStr
    cols: list[ColSpec]


# ── Helper de conversion de type ──────────────────────────────────────────

def _coerce_value(val: Any, field_type: FieldType) -> Any:
    """Convertit une valeur brute selon le type de champ.

    Lève ``TypeError`` ou ``ValueError`` pour float/integer si la
    conversion échoue — les appelants doivent gérer l'exception.
    """
    if field_type == "float":
        return float(val)
    if field_type == "integer":
        return int(float(val))
    if field_type == "checkbox":
        if isinstance(val, str):
            return val.lower() in ("true", "1", "oui", "on")
        return bool(val)
    return val


# ── Service formulaire simple ─────────────────────────────────────────────


class SimpleFormulaireService:
    """Base des services formulaires « simples » (pas de tableau dynamique).

    Une sous-classe déclare ses champs via ``SECTIONS`` et hérite
    automatiquement du workflow BROUILLON → VALIDE → SIGNE.

    Class attributes à surcharger :
        CODE: Code court du formulaire (ex: ``"VISUFINAL"``).
        CHAPITRE: Chapitre A–G.
        TITLE: Titre français (en-tête page web + en-tête PDF).
        TITLE_EN: Titre anglais (en-tête PDF).
        SECTIONS: Liste de SectionSpec décrivant le formulaire.
        REQUIRED_FOR_VALIDATION: Champs obligatoires avant validation.
        CUSTOM_TEMPLATE: True si le formulaire utilise son propre template
            Jinja2 au lieu du gabarit générique ``_simple.html``.
    """

    CODE: str = ""
    CHAPITRE: Chapitre = Chapitre.E
    TITLE: str = ""
    TITLE_EN: str = ""
    SECTIONS: list[SectionSpec] = []
    REQUIRED_FOR_VALIDATION: frozenset[str] = frozenset()
    CUSTOM_TEMPLATE: bool = False

    # ── Résolution de templates ───────────────────────────────────────────

    @classmethod
    def get_web_template(cls) -> str:
        """Retourne le nom du template Jinja2 pour l'affichage web."""
        if cls.CUSTOM_TEMPLATE:
            return f"formulaires/{cls.CODE.lower()}.html"
        return "formulaires/_simple.html"

    @classmethod
    def get_pdf_template(cls) -> str:
        """Retourne le nom du template WeasyPrint pour le PDF."""
        if cls.CUSTOM_TEMPLATE:
            return f"pdf/{cls.CODE.lower()}.html"
        return "pdf/_simple.html"

    # ── Lecture ──────────────────────────────────────────────────────────

    @classmethod
    def get_or_none(cls, affaire: Affaire) -> Formulaire | None:
        """Retourne le formulaire de l'affaire, ou None s'il n'existe pas."""
        return (
            db.session.query(Formulaire)
            .filter_by(affaire_id=affaire.id, code=cls.CODE)
            .first()
        )

    @classmethod
    def prefill_from_parametrage(cls, affaire: Affaire) -> dict[str, Any]:  # noqa: ARG003
        """Pré-remplissage depuis les réponses du wizard Q1–Q8.

        Retourne un dict vide par défaut ; surcharger pour les formulaires
        dont certains champs sont dérivés du paramétrage (ex : HYDR/PS depuis Q5).
        """
        return {}

    @classmethod
    def get_reference_options(cls) -> dict[str, Any]:
        """Options de référence pour les colonnes ``datalist`` (listes déroulantes).

        Retourne un dict vide par défaut. Surcharger pour alimenter les
        auto-complétions depuis un référentiel. Structure attendue par le
        template ``_table.html`` ::

            {
                "<datalist_key>": {
                    "options": ["FOX EV 50", "EML 5", ...],
                    "autofill": {
                        "FOX EV 50": {"norme": "A5.1: E7018-1H4R",
                                       "fournisseur": "VOESTALPINE BOHLER WELDING"},
                        ...
                    },
                },
            }
        """
        return {}

    # ── Écriture ─────────────────────────────────────────────────────────

    @classmethod
    def save_brouillon(
        cls, affaire: Affaire, payload: dict[str, Any], user: User
    ) -> Formulaire:
        """Crée ou met à jour le formulaire en statut BROUILLON.

        Raises:
            ValueError: Si le formulaire n'est plus éditable.
        """
        formulaire = cls.get_or_none(affaire)

        if formulaire is None:
            tmpl = cls._get_active_template()
            formulaire = Formulaire(
                affaire_id=affaire.id,
                code=cls.CODE,
                chapitre=cls.CHAPITRE,
                statut=Statut.BROUILLON,
                template_version=tmpl.version,
                data={},
            )
            db.session.add(formulaire)
            db.session.flush()
            AuditTrail.log(
                "formulaire.created",
                user=user,
                entity_type="formulaire",
                entity_id=formulaire.id,
                new_value=cls.CODE,
                contexte={"affaire_id": affaire.id, "template_version": tmpl.version},
            )
        elif not formulaire.statut.is_editable:
            raise ValueError(
                f"Formulaire {cls.CODE} non éditable (statut={formulaire.statut.value})."
            )

        formulaire.data = cls._sanitize_payload(payload)

        AuditTrail.log(
            "formulaire.saved",
            user=user,
            entity_type="formulaire",
            entity_id=formulaire.id,
            contexte={"statut": formulaire.statut.value},
        )
        db.session.commit()
        return formulaire

    @classmethod
    def valider(cls, formulaire: Formulaire, user: User) -> None:
        """Transition BROUILLON → VALIDE.

        Raises:
            ValueError: Si statut incorrect ou champs obligatoires absents.
        """
        if formulaire.statut is not Statut.BROUILLON:
            raise ValueError(
                f"La validation requiert BROUILLON (actuel : {formulaire.statut.value})."
            )
        missing = cls.REQUIRED_FOR_VALIDATION - set(formulaire.data.keys())
        if missing:
            raise ValueError(
                f"Champs obligatoires manquants : {', '.join(sorted(missing))}."
            )
        old_statut = formulaire.statut
        formulaire.statut = Statut.VALIDE
        AuditTrail.log(
            "formulaire.validated",
            user=user,
            entity_type="formulaire",
            entity_id=formulaire.id,
            old_value=old_statut,
            new_value=Statut.VALIDE,
        )
        db.session.commit()

    @classmethod
    def signer(cls, formulaire: Formulaire, user: User) -> Signature:
        """Transition VALIDE → SIGNE + création Signature SHA-256.

        Raises:
            ValueError: Si le statut n'est pas VALIDE.
        """
        if formulaire.statut is not Statut.VALIDE:
            raise ValueError(
                f"La signature requiert VALIDE (actuel : {formulaire.statut.value})."
            )
        hash_val = Signature.compute_hash(
            formulaire.code, formulaire.template_version, formulaire.data
        )
        sig = Signature(
            formulaire_id=formulaire.id,
            user_id=user.id,
            hash_sha256=hash_val,
        )
        db.session.add(sig)
        formulaire.statut = Statut.SIGNE
        AuditTrail.log(
            "formulaire.signed",
            user=user,
            entity_type="formulaire",
            entity_id=formulaire.id,
            old_value=Statut.VALIDE,
            new_value=Statut.SIGNE,
            contexte={"hash_sha256": hash_val[:16]},
        )
        db.session.commit()
        return sig

    # ── Helpers internes ─────────────────────────────────────────────────

    @classmethod
    def _get_active_template(cls) -> FormulaireTemplate:
        tmpl = (
            db.session.query(FormulaireTemplate)
            .filter_by(code=cls.CODE, actif=True)
            .first()
        )
        if tmpl is None:
            raise RuntimeError(
                f"Template {cls.CODE} actif introuvable — exécutez `flask seed`."
            )
        return tmpl

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """Filtre et convertit le payload client selon SECTIONS.

        - Ignore les clés hors whitelist (injection protection).
        - Ignore les valeurs vides (None, ``""``).
        - Convertit les types selon ``field_type`` de chaque FieldSpec.
        """
        allowed = {
            fspec.name
            for section in cls.SECTIONS
            for fspec in section.fields
        }
        clean: dict[str, Any] = {}

        for key, val in raw.items():
            if key not in allowed:
                continue
            if val is None or val == "":
                continue
            clean[key] = val

        for section in cls.SECTIONS:
            for fspec in section.fields:
                if fspec.name not in clean:
                    continue
                try:
                    clean[fspec.name] = _coerce_value(clean[fspec.name], fspec.field_type)
                except (TypeError, ValueError):
                    del clean[fspec.name]

        return clean


# ── Service formulaire à tableau dynamique ────────────────────────────────


class TableFormulaireService(SimpleFormulaireService):
    """Service base pour les formulaires à tableau dynamique (lignes JS ajoutables).

    Les données sont stockées sous la forme :
    - ``{"lignes": [...]}`` — sans en-tête (BIM, BIMSoud)
    - ``{"header": {...}, "lignes": [...]}`` — avec en-tête fixe (PMI)

    Attributs de classe à déclarer :
        HEADER_SECTIONS: Sections de l'en-tête fixe (liste vide si aucun).
        TABLE_SPEC: ``TableSpec`` décrivant les colonnes du tableau.
        REQUIRED_HEADER: Champs d'en-tête obligatoires avant validation.
        REQUIRED_LIGNES: Nombre minimum de lignes pour valider (défaut 1).
    """

    HEADER_SECTIONS: list[SectionSpec] = []
    TABLE_SPEC: TableSpec | None = None
    REQUIRED_HEADER: frozenset[str] = frozenset()
    REQUIRED_LIGNES: int = 1
    REQUIRED_FOR_VALIDATION: frozenset[str] = frozenset()
    SECTIONS: list[SectionSpec] = []

    @classmethod
    def get_web_template(cls) -> str:
        return "formulaires/_table.html"

    @classmethod
    def get_pdf_template(cls) -> str:
        return "pdf/_table.html"

    @classmethod
    def valider(cls, formulaire: Formulaire, user: User) -> None:
        """Valide : vérifie les champs d'en-tête obligatoires et le nombre de lignes.

        Raises:
            ValueError: Si statut incorrect, champs d'en-tête manquants ou pas
                assez de lignes.
        """
        if formulaire.statut is not Statut.BROUILLON:
            raise ValueError(
                f"La validation requiert BROUILLON (actuel : {formulaire.statut.value})."
            )
        data = formulaire.data or {}
        header = data.get("header", {})
        lignes = data.get("lignes", [])

        missing_header = cls.REQUIRED_HEADER - set(header.keys())
        if missing_header:
            raise ValueError(
                f"Champs d'en-tête obligatoires manquants : "
                f"{', '.join(sorted(missing_header))}."
            )
        if len(lignes) < cls.REQUIRED_LIGNES:
            raise ValueError(
                f"Au moins {cls.REQUIRED_LIGNES} ligne(s) requise(s) "
                f"(actuellement {len(lignes)})."
            )
        old_statut = formulaire.statut
        formulaire.statut = Statut.VALIDE
        AuditTrail.log(
            "formulaire.validated",
            user=user,
            entity_type="formulaire",
            entity_id=formulaire.id,
            old_value=old_statut,
            new_value=Statut.VALIDE,
        )
        db.session.commit()

    @classmethod
    def _sanitize_payload(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """Sanitise le payload table : en-tête + lignes.

        Payload JSON attendu :
        ``{"header": {...}, "lignes": [{...}, ...]}``
        (``header`` peut être omis si ``HEADER_SECTIONS`` est vide).
        """
        clean: dict[str, Any] = {}

        if cls.HEADER_SECTIONS and "header" in raw:
            allowed_header = {
                fspec.name
                for section in cls.HEADER_SECTIONS
                for fspec in section.fields
            }
            raw_header = raw.get("header", {})
            clean_header: dict[str, Any] = {}
            for k, v in raw_header.items():
                if k not in allowed_header or v is None or v == "":
                    continue
                clean_header[k] = v
            for section in cls.HEADER_SECTIONS:
                for fspec in section.fields:
                    if fspec.name not in clean_header:
                        continue
                    try:
                        clean_header[fspec.name] = _coerce_value(
                            clean_header[fspec.name], fspec.field_type
                        )
                    except (TypeError, ValueError):
                        del clean_header[fspec.name]
            clean["header"] = clean_header

        if cls.TABLE_SPEC and "lignes" in raw:
            cols_by_name = {col.name: col for col in cls.TABLE_SPEC.cols}
            clean_lignes: list[dict[str, Any]] = []
            for row in raw.get("lignes", []):
                if not isinstance(row, dict):
                    continue
                clean_row: dict[str, Any] = {}
                for k, v in row.items():
                    if k not in cols_by_name or v is None or v == "":
                        continue
                    col = cols_by_name[k]
                    try:
                        clean_row[k] = _coerce_value(v, col.col_type)
                    except (TypeError, ValueError):
                        pass
                if clean_row:
                    clean_lignes.append(clean_row)
            clean["lignes"] = clean_lignes

        return clean
