"""Formulaire de la fiche technique de l'item (V1.2 Lot 2).

Regroupe, après création du dossier, les caractéristiques techniques
anciennement saisies dans le wizard (ex-Q4→Q7) plus la réglementation
(reprise éditable de l'étape Q3 du wizard). Les données restent stockées
dans ``ParametrageAffaire.reponses`` sous les clés historiques ``q4_*`` à
``q7_*`` (décision D2) — voir ``affaire_svc.save_fiche_technique``.

Demandes n°7/n°8 de la stratégie V1.2 : procédés de soudage, méthodes CND
et tests de pression sont des **cases à cocher** ; les tests de pression
passent en multi-choix (``q7_test_pressions``, liste — l'ancienne clé
``q7_test_pression`` reste lue en repli, décision D3).
"""
from __future__ import annotations

from flask_babel import lazy_gettext as _l
from wtforms import (
    BooleanField,
    FloatField,
    SelectField,
    SelectMultipleField,
    StringField,
)
from wtforms.validators import Length, NumberRange, Optional
from wtforms.widgets import CheckboxInput, ListWidget

from app.forms.wizard import WizardQ3Form


class MultiCheckboxField(SelectMultipleField):
    """``SelectMultipleField`` rendu en liste de cases à cocher Bootstrap."""

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class FicheTechniqueForm(WizardQ3Form):  # type: ignore[misc]
    """Fiche technique complète de l'item.

    Hérite de la section Réglementation du wizard (``desp``, ``stamp_u``,
    ``categorie_ped``, ``module_ped`` — mêmes validateurs conditionnels) et
    ajoute les caractéristiques techniques. Tous les champs techniques sont
    facultatifs : la fiche se complète progressivement après la création.
    """

    # ── Caractéristiques du fluide (clés q4_*) ───────────────────────────
    fluide_etat = SelectField(
        _l("État du fluide"),
        choices=[
            ("", _l("— Sélectionner —")),
            ("gaz", _l("Gaz")),
            ("liquide", _l("Liquide")),
        ],
        validators=[Optional()],
        description=_l(
            "État physique du fluide contenu — conditionne la catégorie PED."
        ),
    )
    fluide_groupe = SelectField(
        _l("Dangerosité du fluide"),
        choices=[
            ("", _l("— Sélectionner —")),
            ("1", _l("Groupe 1 — Fluide dangereux")),
            ("2", _l("Groupe 2 — Fluide non dangereux")),
        ],
        validators=[Optional()],
    )
    fluide_nom = StringField(
        _l("Nom du fluide principal"),
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": _l("Eau, huile, vapeur, azote…")},
    )

    # ── Conditions de service (clés q5_*) ────────────────────────────────
    ps_bar = FloatField(
        _l("Pression de service PS (bar)"),
        validators=[Optional(), NumberRange(min=0, max=1000)],
        render_kw={"step": "0.1"},
        description=_l(
            "Pression de calcul ; la pression d'épreuve PT = PS × 1.43 sera dérivée."
        ),
    )
    temperature_min_c = FloatField(
        _l("Température minimale (°C)"),
        validators=[Optional(), NumberRange(min=-273, max=2000)],
        render_kw={"step": "1"},
    )
    temperature_max_c = FloatField(
        _l("Température maximale (°C)"),
        validators=[Optional(), NumberRange(min=-273, max=2000)],
        render_kw={"step": "1"},
    )
    volume_l = FloatField(
        _l("Volume (litres)"),
        validators=[Optional(), NumberRange(min=0, max=1_000_000)],
        render_kw={"step": "0.1"},
        description=_l("Requis pour vérifier la catégorie de risque (PS·V)."),
    )

    # ── Procédés de fabrication (clés q6_*) ──────────────────────────────
    procedes_soudage = MultiCheckboxField(
        _l("Procédés de soudage utilisés"),
        choices=[
            ("141", _l("141 — TIG")),
            ("111", _l("111 — Électrode enrobée (manuel)")),
            ("136", _l("136 — MAG fil fourré")),
            ("121", _l("121 — Sous-flux")),
            ("131", _l("131 — MIG")),
        ],
        validators=[Optional()],
    )
    tubes_soudes = BooleanField(
        _l("Présence de tubes soudés à la calandre"),
    )
    tth_required = BooleanField(
        _l("Traitement thermique après soudage (TTH) requis"),
        description=_l("Détendage / recuit normalisé selon ASME ou EN."),
    )

    # ── Contrôles et essais (clés q7_*) ──────────────────────────────────
    cnd_methodes = MultiCheckboxField(
        _l("Méthodes de CND requises"),
        choices=[
            ("RT", _l("RT — Radiographie")),
            ("UT", _l("UT — Ultrasons")),
            ("PT", _l("PT — Ressuage")),
            ("MT", _l("MT — Magnétoscopie")),
            ("VT", _l("VT — Examen visuel")),
        ],
        validators=[Optional()],
    )
    test_pressions = MultiCheckboxField(
        _l("Tests de pression à réaliser"),
        choices=[
            ("hydrostatique", _l("Hydrostatique (HYDR)")),
            ("pneumatique", _l("Pneumatique (AirSav)")),
            ("azote", _l("Étanchéité azote (Azote)")),
        ],
        validators=[Optional()],
        description=_l("Plusieurs tests possibles sur un même item."),
    )
    inspection_client = BooleanField(
        _l("Inspection client / TPI prévue"),
        description=_l("Tierce Partie Indépendante ou inspecteur client présent."),
    )
