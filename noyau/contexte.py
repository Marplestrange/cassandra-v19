"""Le contexte : tout ce qu'un module voit du noyau, et RIEN d'autre.

Un module ne reçoit qu'un `ctx` à son branchement. Il ne peut ni importer un autre module, ni écrire
un type d'objet qu'il ne possède pas, ni émettre un événement qu'il n'a pas déclaré. Ces limites sont
celles de son manifeste, appliquées ici.

Le compte pour lequel le module travaille (`ctx.compte`) est PAR FIL, jamais global : il est posé par
l'exécuteur le temps d'une capacité. Une lecture exige toujours une portée explicite.
"""
from __future__ import annotations

import logging
import threading


class _Fil(threading.local):
    valeur = None


class _Compte(threading.local):
    valeur = ""


class Contexte:
    def __init__(self, manifeste, bus, registre, catalogue, detecteurs, config=None):
        self.manifeste = manifeste
        self.module = manifeste.id
        self.config = dict(config or {})
        self.log = logging.getLogger("module.%s" % manifeste.id)
        self._bus, self._registre, self._catalogue, self._detecteurs = bus, registre, catalogue, detecteurs
        self._cause = _Fil()
        self._compte = _Compte()

    @property
    def compte(self) -> str:
        """Le compte au nom duquel la capacité en cours s'exécute ('' = commun / infrastructure)."""
        return self._compte.valeur

    # ---- événements ----
    def emettre(self, type: str, objet=None, donnees=None, cause=None, acteur: str = "module", compte=None) -> int:
        if type not in self.manifeste.emet:
            raise PermissionError("le module « %s » n'a pas déclaré l'événement « %s » (evenements.emet)" % (self.module, type))
        return self._bus.emettre(type, source=self.module, acteur=acteur, objet=objet, donnees=donnees,
                                 cause=cause if cause is not None else self._cause.valeur,
                                 compte=self.compte if compte is None else compte)

    def ecouter(self, type: str, fonction) -> None:
        if type not in self.manifeste.ecoute:
            raise PermissionError("le module « %s » n'a pas déclaré l'écoute de « %s » (evenements.ecoute)" % (self.module, type))
        self._bus.ecouter(type, fonction, self.module)

    # ---- objets ----
    def poser(self, type: str, id: str, libelle: str, etat: str = "", donnees=None, compte=None) -> bool:
        return self._registre.poser(self.module, type, id, libelle, etat, donnees, cause=self._cause.valeur,
                                    compte=self.compte if compte is None else compte)

    def retirer(self, type: str, id: str) -> bool:
        return self._registre.retirer(self.module, type, id, cause=self._cause.valeur)

    def lire(self, type: str, id: str, *, portee):
        return self._registre.lire(type, id, portee=portee)

    def lister(self, *, portee, type: str = "", etat: str = "") -> list:
        return self._registre.lister(portee=portee, type=type, etat=etat)

    # ---- capacités et détecteurs ----
    def implementer(self, cid: str, faire, prouver=None, defaire=None, simuler=None) -> None:
        self._catalogue.implementer(self.module, cid, faire, prouver, defaire, simuler)

    def detecteur(self, did: str, fonction) -> None:
        d = next((x for x in self.manifeste.detecteurs if x.id == did), None)
        if d is None:
            raise KeyError("le module « %s » n'a pas déclaré le détecteur « %s »" % (self.module, did))
        self._detecteurs.append((self.module, d, fonction))
