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

from . import chemins


class _Fil(threading.local):
    valeur = None


class _Compte(threading.local):
    valeur = ""


class Contexte:
    def __init__(self, manifeste, bus, registre, catalogue, detecteurs, config=None, moteurs=None, introspection=None):
        self.manifeste = manifeste
        self.module = manifeste.id
        self.config = dict(config or {})
        self.log = logging.getLogger("module.%s" % manifeste.id)
        self._bus, self._registre, self._catalogue, self._detecteurs = bus, registre, catalogue, detecteurs
        self._moteurs = moteurs if moteurs is not None else []
        self._intro = introspection or {}
        self._cause = _Fil()
        self._compte = _Compte()

    TOUT = "*"   # la portée des agents (voir bus.py) : un module la passe explicitement, jamais par défaut

    @property
    def compte(self) -> str:
        """Le compte au nom duquel la capacité en cours s'exécute ('' = commun / infrastructure)."""
        return self._compte.valeur

    # ---- ce que le noyau sait de lui-même (module de menus, de supervision) ----
    def _exiger_introspection(self) -> None:
        if not self.manifeste.permissions.introspection:
            raise PermissionError("le module « %s » n'a pas demandé l'introspection ([permissions] introspection)" % self.module)

    def manifestes_actifs(self) -> list:
        """Les manifestes des modules branchés, en lecture seule. C'est ainsi que le module de menus assemble l'arbre."""
        self._exiger_introspection()
        return self._intro["manifestes"]()

    def executer_lecture(self, capacite: str, **args):
        """Appelle une capacité de LECTURE d'un autre module (« module.capacite ») et rend son résultat (None si elle échoue).
        Réservé aux modules qui l'ont demandé ([permissions] lectures) ; jamais une écriture."""
        if not self.manifeste.permissions.lectures:
            raise PermissionError("le module « %s » n'a pas demandé d'appeler les lectures des autres ([permissions] lectures)" % self.module)
        return self._intro["lecture"](capacite, args)

    def droits(self):
        """Le service des droits des comptes, pour le module qui les administre ([permissions] droits). Les autres n'en ont pas besoin :
        l'exécuteur vérifie le droit d'une capacité avant même de l'appeler."""
        if not self.manifeste.permissions.droits:
            raise PermissionError("le module « %s » n'a pas demandé l'administration des droits ([permissions] droits)" % self.module)
        return self._intro["droits"]

    def identite(self):
        """Le service d'identité des comptes (mots de passe, sessions), pour le module qui les administre ([permissions] identite)."""
        if not self.manifeste.permissions.identite:
            raise PermissionError("le module « %s » n'a pas demandé l'identité des comptes ([permissions] identite)" % self.module)
        return self._intro["identite"]

    def second_facteur(self, facteur) -> None:
        """Branche un second facteur de connexion ([permissions] identite) : `exige(compte)`, `invite(compte)`, `verifier(compte, preuve, ip)`."""
        self.identite().enregistrer_facteur(self.module, facteur)

    @property
    def stockage(self):
        """La base de CE module (donnees/modules/<id>.db), migrations appliquées. Personne d'autre n'y touche ([permissions] stockage = true)."""
        if not self.manifeste.permissions.stockage:
            raise PermissionError("le module « %s » n'a pas demandé de stockage ([permissions] stockage)" % self.module)
        return self._intro["stockage"](self.module)

    def reglage(self, nom: str, compte=None):
        """La valeur EFFECTIVE d'un réglage que CE module a déclaré (« nom » sans le préfixe du module). Pour un réglage de portée compte,
        celle du compte au nom duquel on agit (ou `compte`). Le module qui déclare un secret est le seul à le lire en clair."""
        return self._intro["reglages"].valeur("%s.%s" % (self.module, nom), self.compte if compte is None else compte)

    def service_reglages(self):
        """Le service des réglages, pour le module qui les administre ([permissions] reglages)."""
        if not self.manifeste.permissions.reglages:
            raise PermissionError("le module « %s » n'a pas demandé l'administration des réglages ([permissions] reglages)" % self.module)
        return self._intro["reglages"]

    def evenements(self, type_prefixe: str = "", limite: int = 200) -> list:
        """Les événements récents (tous comptes), pour un module de surveillance ([permissions] introspection)."""
        self._exiger_introspection()
        return self._intro["evenements"](type_prefixe, limite)

    def compteurs(self, module: str) -> dict:
        """{'constats': ouverts du module, 'moteurs': ceux à surveiller} : de quoi afficher un badge."""
        self._exiger_introspection()
        return self._intro["compteurs"](module)

    # ---- disque ----
    def espace(self, utilisateur: str, creer: bool = True):
        """L'espace de ce module chez un utilisateur : /var/www/<utilisateur>/data/cassandra/<module>. Rien ne sort de là.
        Réservé aux modules qui l'ont demandé ([permissions] espace_utilisateur = true) : on le sait avant de les installer."""
        if not self.manifeste.permissions.espace_utilisateur:
            raise PermissionError("le module « %s » n'a pas demandé l'espace des utilisateurs ([permissions] espace_utilisateur)" % self.module)
        return chemins.espace_utilisateur(utilisateur, self.module, creer=creer)

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

    def moteur(self, mid: str, fonction) -> None:
        """Inscrit un moteur déclaré au manifeste. `fonction(ctx)` pour un moteur périodique ou à la demande,
        `fonction(ctx, evenement)` pour un moteur sur événement. Le module n'ouvre jamais de thread : le noyau
        l'ordonnance, mesure sa durée, l'empêche de s'empiler et le suspend s'il échoue trop."""
        mo = next((x for x in self.manifeste.moteurs if x.id == mid), None)
        if mo is None:
            raise KeyError("le module « %s » n'a pas déclaré le moteur « %s » ([[moteurs]])" % (self.module, mid))
        self._moteurs.append((self.module, mo, fonction))

    def detecteur(self, did: str, fonction) -> None:
        d = next((x for x in self.manifeste.detecteurs if x.id == did), None)
        if d is None:
            raise KeyError("le module « %s » n'a pas déclaré le détecteur « %s »" % (self.module, did))
        self._detecteurs.append((self.module, d, fonction))
