# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'état des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #1419e4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'état des modules : disponible, installé, actif. Le menu des modules s'appuie là-dessus.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1419e4 ▼▼▼
"""L'état des modules : disponible, installé, actif. Le menu des modules s'appuie là-dessus.

  disponible  le manifeste est là, rien n'a été posé
  installé    son installation (scripts, fichiers système) est faite et prouvée
  actif       le noyau l'a branché : ses moteurs, détecteurs et capacités répondent

Désactiver n'efface rien : les données du module (objets, événements, savoir-faire) restent, comme dans Dolibarr.
Un humain ou un agent change l'état ; chaque changement est un événement avec son auteur, donc Cassandra sait.
"""
from __future__ import annotations

import time


class Modules:
    def __init__(self, base):
        self.base = base

    def tous(self) -> dict:
        return {r["id"]: r for r in self.base.lire("SELECT * FROM modules_etat")}

    def get(self, mid: str):
        r = self.base.lire("SELECT * FROM modules_etat WHERE id=?", (mid,))
        return r[0] if r else None

    def actifs(self) -> list:
        return [r["id"] for r in self.base.lire("SELECT id FROM modules_etat WHERE actif=1 ORDER BY id")]

    def poser(self, mid: str, installe=None, actif=None, par: str = "", raison: str = "") -> None:
        avant = self.get(mid) or {"installe": 0, "actif": 0}
        i = avant["installe"] if installe is None else int(bool(installe))
        a = avant["actif"] if actif is None else int(bool(actif))
        self.base.ecrire(
            "INSERT INTO modules_etat(id, installe, actif, maj, par, raison) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET installe=excluded.installe, actif=excluded.actif, maj=excluded.maj, par=excluded.par, raison=excluded.raison",
            (mid, i, a, time.time(), par, raison))

    def oublier(self, mid: str) -> None:
        self.base.ecrire("DELETE FROM modules_etat WHERE id=?", (mid,))

    def signature(self) -> tuple:
        """Change dès qu'un état change : le noyau en marche s'en aperçoit sans redémarrer."""
        return tuple((r["id"], r["installe"], r["actif"], r["maj"]) for r in self.base.lire("SELECT * FROM modules_etat ORDER BY id"))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Modules
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
