# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'équipe des agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.2.0  #b578ea
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'équipe des agents : qui ils sont (des DONNÉES : CN_equipe.json), comment chacun est réglé, ce qu'il dépense, et le plafond qui le retient.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=b578ea ▼▼▼
"""L'équipe des agents : qui ils sont (des DONNÉES : CN_equipe.json), comment chacun est réglé, ce qu'il dépense, et le plafond qui le retient.

Règles tenues ici :
  - un compte ordinaire n'agit que sur SON Itare ; l'administrateur règle Cassandra, Amizo et les services, jamais le bureau d'un autre compte (administrer n'est pas voir) ;
  - une capacité de réglage n'est pas un outil d'agent (le module « agents » n'est pas dans leur catalogue) et refuse un agent pour acteur : un agent ne monte pas son propre palier ;
  - le coût du jour se compte par agent (et par compte pour Itare) ; le plafond le plus bas parmi ceux que la dépense dépasse s'applique, avec son action.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

DONNEES = json.loads((Path(__file__).resolve().parent / "CN_equipe.json").read_text(encoding="utf-8"))
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
CHAMPS_TEXTE = {"nom_affiche": 40, "ton": 2000, "modele": 80, "secours": 80}
MODELE_OK = re.compile(r"^[A-Za-z0-9_.:/\-]*$")
maintenant = time.time                       # un banc le remplace pour changer de jour


def jour() -> str:
    return time.strftime("%Y-%m-%d", time.localtime(maintenant()))


def cout_centimes(entrees: int, sorties: int, t_entree: int, t_sortie: int) -> float:
    """Centimes d'euro d'un échange : les tarifs sont en centimes par million de jetons."""
    return (int(entrees) * int(t_entree) + int(sorties) * int(t_sortie)) / 1_000_000.0


def euros(centimes) -> float:
    return round(float(centimes or 0) / 100.0, 6)


def verdict_plafond(plafonds: dict, depenses: dict, agent: str, aujourdhui: str):
    """`plafonds` : {portee: {centimes, action, accord_jour}} ; `depenses` : {'global': centimes du jour, <agent>: centimes du jour}.
    Parmi les plafonds que la dépense atteint (celui de l'agent, celui de la maison), le PLUS BAS donne l'action. Un accord donné aujourd'hui lève un plafond « accord ».
    Rend None (rien ne retient) ou {portee, centimes, action, depense}."""
    atteints = []
    for portee in (agent, "global"):
        p = plafonds.get(portee)
        if not p:
            continue
        dep = float(depenses.get(portee, 0) or 0)
        if dep < p["centimes"]:
            continue
        if p["action"] == "accord" and p.get("accord_jour") == aujourdhui:
            continue
        atteints.append({"portee": portee, "centimes": p["centimes"], "action": p["action"], "depense": dep})
    return min(atteints, key=lambda x: (x["centimes"], x["portee"] != agent)) if atteints else None
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : jour, cout_centimes, euros, verdict_plafond
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
