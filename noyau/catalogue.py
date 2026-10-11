"""Le catalogue unifié des capacités, et le savoir-faire qui grandit avec elles.

Une capacité est décrite UNE fois (dans un manifeste). Ses « portes » (outil d'agent, geste, tâche,
détecteur) en dérivent. Ici vit aussi l'apprentissage : chaque capacité a un palier d'autonomie qui
monte avec les réussites et redescend avec les échecs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

# Hérités de la V18 (_PF_SEUIL_PROMO, _PF_SEUIL_RETRO)
SEUIL_PROMO = 10     # réussites pour passer de « raconter » à « auto »
SEUIL_MAITRE = 30    # réussites pour passer de « auto » à « maitre » (jamais pour un risque élevé)
SEUIL_RETRO = 2      # échecs de suite avant de redescendre d'un palier
ORDRE = ("raconter", "auto", "maitre")


@dataclass
class Entree:
    cle: str                   # « module.capacite »
    module: str
    capacite: object           # noyau.manifeste.Capacite
    faire: object = None
    prouver: object = None
    defaire: object = None
    simuler: object = None
    actif: bool = True         # faux quand le module est désactivé : ses capacités ne répondent plus

    @property
    def implementee(self) -> bool:
        return self.faire is not None


class Catalogue:
    def __init__(self, base):
        self.base = base
        self._entrees = {}

    def inscrire(self, manifeste) -> None:
        for c in manifeste.capacites:
            cle = "%s.%s" % (manifeste.id, c.id)
            self._entrees[cle] = Entree(cle, manifeste.id, c)
            if self.base.lire("SELECT 1 FROM savoir WHERE capacite=?", (cle,)) == []:
                self.base.ecrire("INSERT INTO savoir(capacite, palier, maj) VALUES (?,?,?)", (cle, c.paliers[0], time.time()))

    def desactiver_module(self, module: str) -> int:
        n = 0
        for e in self._entrees.values():
            if e.module == module and e.actif:
                e.actif, n = False, n + 1
        return n

    def implementer(self, module: str, cid: str, faire, prouver=None, defaire=None, simuler=None) -> None:
        e = self._entrees.get("%s.%s" % (module, cid))
        if not e:
            raise KeyError("le module « %s » n'a pas déclaré la capacité « %s »" % (module, cid))
        if e.capacite.ecrit and (prouver is None or defaire is None):
            raise ValueError("« %s » écrit : son implémentation doit fournir `prouver` ET `defaire` (la sûreté vient de la réversibilité)" % e.cle)
        e.faire, e.prouver, e.defaire, e.simuler = faire, prouver, defaire, simuler

    def get(self, cle: str):
        return self._entrees.get(cle)

    def lister(self) -> list:
        return sorted(self._entrees.values(), key=lambda e: e.cle)

    def savoir(self, cle: str) -> dict:
        r = self.base.lire("SELECT * FROM savoir WHERE capacite=?", (cle,))
        return r[0] if r else {"capacite": cle, "palier": "raconter", "reussites": 0, "echecs_de_suite": 0}

    def regler_palier(self, cle: str, palier: str) -> None:
        """Voie parallèle : un humain peut fixer un palier. Le noyau n'attend jamais qu'il le fasse."""
        if palier not in ORDRE:
            raise ValueError("palier inconnu : %s" % palier)
        e = self._entrees.get(cle)
        if e is None or palier not in e.capacite.paliers:
            raise ValueError("« %s » n'autorise pas le palier « %s »" % (cle, palier))
        self.base.ecrire("UPDATE savoir SET palier=?, echecs_de_suite=0, maj=? WHERE capacite=?", (palier, time.time(), cle))

    def apprendre(self, cle: str, succes: bool, compte_echec: bool = True):
        """Enregistre un résultat. Rend (ancien, nouveau) si le palier a bougé, sinon None.
        Un geste humain réussi compte (apprendre du maître) ; un échec humain ne rétrograde pas la capacité."""
        e = self._entrees[cle]
        s = self.savoir(cle)
        reussites, echecs, palier = s["reussites"], s["echecs_de_suite"], s["palier"]
        if succes:
            reussites, echecs = reussites + 1, 0
            if palier == "raconter" and "auto" in e.capacite.paliers and reussites >= SEUIL_PROMO:
                palier = "auto"
            elif palier == "auto" and "maitre" in e.capacite.paliers and e.capacite.risque != "eleve" and reussites >= SEUIL_MAITRE:
                palier = "maitre"
        elif compte_echec:
            echecs += 1
            if echecs >= SEUIL_RETRO and palier != "raconter":
                palier, echecs = ORDRE[ORDRE.index(palier) - 1], 0
        self.base.ecrire("UPDATE savoir SET palier=?, reussites=?, echecs_de_suite=?, maj=? WHERE capacite=?",
                         (palier, reussites, echecs, time.time(), cle))
        return (s["palier"], palier) if palier != s["palier"] else None
