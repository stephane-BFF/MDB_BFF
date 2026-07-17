"""Données de référence des soudeurs BFF (identité).

Extrait du fichier source ``LISTE_AQ_EF_16_Dossier_Constructeur.xlsx``
(section « LIST SOUD »). Chaque entrée : ``(matricule, initiales, nom)``.

Seule l'identité du soudeur est connue de cette source ; le détail des
qualifications (procédés, positions, groupes de matériaux, validités par QS)
est saisi dans le formulaire LISTSOUD. Alimente le référentiel ``Soudeur``
via ``flask seed`` et la liste déroulante « Soudeur » du formulaire LISTSOUD.
"""
from __future__ import annotations

# (matricule, initiales, nom)
SOUDEURS: tuple[tuple[str, str, str], ...] = (
    ("129", "AS", "ANABI Samir"),
    ("163", "AG", "ANTAL Gabor"),
    ("108", "BI", "BAKUS Istvan"),
    ("95", "BL", "BARTHUS Laszlo"),
    ("149", "BA", "BENONE Andrei"),
    ("165", "BG", "BOGNAR Gyorgy"),
    ("159", "BD", "BOR David"),
    ("120", "AB", "BROU Allaly"),
    ("147", "CC", "CIHODARU Costel"),
    ("164", "CT", "COSTA Tom"),
    ("133", "DQ", "DALBIGOT Quentin"),
    ("97", "DL", "DUDAS Ladislav"),
    ("161", "FA", "FEKECS Adrian"),
    ("126", "GI", "GAAL Istvan"),
    ("167", "GZ", "GAAL Zoltan"),
    ("169", "GM", "GATON-HAVETTE Marius"),
    ("158", "GJ", "GORZSAS Josef"),
    ("166", "GJ", "GOURG Julian"),
    ("143", "IK", "INCZE Karoly"),
    ("162", "KA", "KONICS Attila"),
    ("151", "LL", "LANORD Lucas"),
    ("157", "LA", "LASNIER-SIRON Antoine"),
    ("168", "LS", "LOCHON Samuel"),
    ("153", "MD", "MISKOVICZ David"),
    ("116", "SM", "SZUCS Mihaly"),
    ("96", "SG", "SZUROMI Gabor"),
    ("155", "VJ", "VARGA Janos"),
    ("145", "VB", "VASILYEV Boris"),
)
