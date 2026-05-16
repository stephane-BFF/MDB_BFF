"""Registre des services de formulaire — mappe code → classe service.

Chaque code de formulaire est associé à une classe qui expose l'interface
standard : ``get_or_none``, ``prefill_from_parametrage``, ``save_brouillon``,
``valider``, ``signer``, plus les attributs de classe ``CODE``, ``CHAPITRE``,
``TITLE``, ``TITLE_EN``, ``SECTIONS``, ``REQUIRED_FOR_VALIDATION``,
``CUSTOM_TEMPLATE``.
"""
from __future__ import annotations

from typing import Any

from app.services.formulaires.airsav import AirSavService
from app.services.formulaires.attdecr import AttDecrService
from app.services.formulaires.attrep import AttRepService
from app.services.formulaires.azote import AzoteService
from app.services.formulaires.base import SimpleFormulaireService
from app.services.formulaires.bim import BimService
from app.services.formulaires.bimsoud import BimSoudService
from app.services.formulaires.confcom import ConfComService
from app.services.formulaires.dim import DimService
from app.services.formulaires.durete import DureteService
from app.services.formulaires.etatdesc import EtatDescService
from app.services.formulaires.ferrite import FeriteService
from app.services.formulaires.hydr import HydrService
from app.services.formulaires.listcnd import ListCndService
from app.services.formulaires.listsoud import ListSoudService
from app.services.formulaires.nde_map import NdeMapService
from app.services.formulaires.pesage import PesageService
from app.services.formulaires.pmi import PmiService
from app.services.formulaires.proprete import PropreteService
from app.services.formulaires.recordhydro import RecordHydroService
from app.services.formulaires.rolling import RollingService
from app.services.formulaires.sechage import SechageService
from app.services.formulaires.tth import TTH1Service, TTH2Service
from app.services.formulaires.ut0 import (
    UT0FaisService,
    UT0RetService,
    UT0ShellService,
    UT0UbendService,
)
from app.services.formulaires.ped import PedModService
from app.services.formulaires.visufinal import VisuFinalService

# HydrService est un wrapper duck-typé (non-sous-classe de SimpleFormulaireService).
_REGISTRY: dict[str, type[Any]] = {
    "HYDR": HydrService,
    "VISUFINAL": VisuFinalService,
    "PROPRETE": PropreteService,
    "SECHAGE": SechageService,
    "PESAGE": PesageService,
    "CONFCOM": ConfComService,
    "ATTDECR": AttDecrService,
    "ATTREP": AttRepService,
    "ETATDESC": EtatDescService,
    "AIRSAV": AirSavService,
    "RECORDHYDRO": RecordHydroService,
    "AZOTE": AzoteService,
    "TTH1": TTH1Service,
    "TTH2": TTH2Service,
    "BIM": BimService,
    "BIMSOUD": BimSoudService,
    "PMI": PmiService,
    "LISTSOUD": ListSoudService,
    "ROLLING": RollingService,
    "DIM": DimService,
    "LISTCND": ListCndService,
    "NDEMAP": NdeMapService,
    "DURETE": DureteService,
    "FERRITE": FeriteService,
    "UT0FAIS": UT0FaisService,
    "UT0SHELL": UT0ShellService,
    "UT0RET": UT0RetService,
    "UT0UBEND": UT0UbendService,
    "PEDMOD": PedModService,
}


def get_service(code: str) -> type[SimpleFormulaireService] | type[Any] | None:
    """Retourne la classe service pour un code de formulaire, ou None si inconnu."""
    return _REGISTRY.get(code.upper())
