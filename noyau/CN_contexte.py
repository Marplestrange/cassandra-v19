# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le contexte
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #4fed7e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le contexte : tout ce qu'un module voit du noyau, et RIEN d'autre.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=4fed7e ▼▼▼
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

from . import CN_chemins as chemins


class _Fil(threading.local):
    valeur = None


class _Compte(threading.local):
    valeur = ""


class _Acteur(threading.local):
    valeur = ""


from .CN_stockage import StockageParSociete


class _Societe(threading.local):
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
        self._acteur = _Acteur()
        self._societe = _Societe()

    TOUT = "*"   # la portée des agents (voir CN_bus.py) : un module la passe explicitement, jamais par défaut

    @property
    def societe(self) -> str:
        """La société dans laquelle la capacité en cours s'exécute : celle du compte, ou celle qu'il a choisie parmi les siennes ('' = infrastructure).
        PAR FIL, comme le compte : jamais un global."""
        return self._societe.valeur

    def societe_de(self, compte: str) -> str:
        """La société de rattachement d'un compte (la principale si on ne la connaît pas). Une métadonnée : aucune permission à demander."""
        f = self._intro.get("societe_de")
        return (f(compte) if f else "") or "1"

    def dans_ma_societe(self, compte: str) -> bool:
        """Ce compte a-t-il accès à la société dans laquelle on agit (la sienne, ou une fonction dans celle-ci) ? C'est la règle de tout partage : on n'invite, on ne
        partage et on n'écrit qu'à quelqu'un de sa société. Hors société (infrastructure), tout est permis."""
        f = self._intro.get("acces_societe")
        if not f or not self.societe:
            return True
        return bool(f(str(compte or "").strip().lower(), self.societe))

    def societes(self) -> list:
        """Les identifiants des sociétés de l'instance (archivées comprises)."""
        f = self._intro.get("societes")
        return list(f()) if f else ["1"]

    @property
    def compte(self) -> str:
        """Le compte au nom duquel la capacité en cours s'exécute ('' = commun / infrastructure)."""
        return self._compte.valeur

    @property
    def acteur(self) -> str:
        """Qui agit (humain, compte, agent, itare, cassandra, anonyme) le temps de la capacité en cours : un module s'en sert pour ce qu'il montre à un modèle."""
        return self._acteur.valeur

    # ---- ce que le noyau sait de lui-même (module de menus, de supervision) ----
    def _exiger_introspection(self) -> None:
        if not self.manifeste.permissions.introspection:
            raise PermissionError("le module « %s » n'a pas demandé l'introspection ([permissions] introspection)" % self.module)

    def manifestes_actifs(self, toutes: bool = False) -> list:
        """Les manifestes des modules branchés, en lecture seule. C'est ainsi que le module de menus assemble l'arbre.
        Ceux de la société dans laquelle on agit seulement (un module peut être fermé pour une société) ; `toutes` : ceux de l'instance entière."""
        self._exiger_introspection()
        ms = self._intro["manifestes"]()
        f = self._intro.get("module_ouvert")
        if toutes or not f or not self.societe:
            return ms
        return [m for m in ms if f(self.societe, m)]

    def gestion_modules(self):
        """Le catalogue des modules et l'état qu'on peut leur donner (.catalogue(), .activer(id, ...), .desactiver(id, ...)), pour le module « modules »
        ([permissions] modules). Aucun autre module n'en a besoin : activer ou désactiver passe par ses capacités, donc par les droits, la preuve et le journal."""
        if not self.manifeste.permissions.modules:
            raise PermissionError("le module « %s » n'a pas demandé la gestion des modules ([permissions] modules)" % self.module)
        return self._intro["gestion_modules"]

    def evolution(self):
        """Le service d'évolution du noyau (cibles, proposer, tick, visiter, retour, chaîne), pour le module « evolution » ([permissions] evolution)."""
        if not self.manifeste.permissions.evolution:
            raise PermissionError("le module « %s » n'a pas demandé l'évolution ([permissions] evolution)" % self.module)
        return self._intro["evolution"]

    def urgence(self):
        """Les freins du noyau (.freins(), .freiner(nom, actif, raison, acteur)) et la crise, pour le module des gestes d'urgence ([permissions] urgence).
        Un frein ne se pose que par ses capacités : droit, journal, retour."""
        if not self.manifeste.permissions.urgence:
            raise PermissionError("le module « %s » n'a pas demandé les gestes d'urgence ([permissions] urgence)" % self.module)
        return self._intro["urgence"]

    def executer_lecture(self, capacite: str, **args):
        """Appelle une capacité de LECTURE d'un autre module (« module.capacite ») et rend son résultat (None si elle échoue).
        Réservé aux modules qui l'ont demandé ([permissions] lectures) ; jamais une écriture."""
        if not self.manifeste.permissions.lectures:
            raise PermissionError("le module « %s » n'a pas demandé d'appeler les lectures des autres ([permissions] lectures)" % self.module)
        return self._intro["lecture"](capacite, args, self.compte, self.societe)       # pour le compte au nom duquel on travaille : un module ne lit jamais plus que lui

    def point(self, point: str, entree):
        """Appelle un point d'évolution de CE module ([[points_evolution]]) : des DONNÉES en entrée, des DONNÉES en sortie, quel que soit le langage de l'EC qui le sert
        (docs/CN_NEXUS.md). Rend la sortie, conforme au contrat : si une EC faillit, la référence du dépôt répond dans le même appel."""
        return self._intro["point"](self.module, point, entree)

    def droits(self):
        """Le service des droits des comptes, pour le module qui les administre ([permissions] droits). Les autres n'en ont pas besoin :
        l'exécuteur vérifie le droit d'une capacité avant même de l'appeler."""
        if not self.manifeste.permissions.droits:
            raise PermissionError("le module « %s » n'a pas demandé l'administration des droits ([permissions] droits)" % self.module)
        return self._intro["droits"]

    def racine(self, commande: str, args=(), stdin=None, delai: int = 30) -> dict:
        """Demande au courtier (root) une commande que CE module a déclarée ([[racine]]) : -> {ok, code, sortie, erreur}. Le courtier ne lance que le programme
        /usr/libexec/cassandra/<module>/<commande> posé en root par l'installation du module ; sans lui, « commande absente »."""
        if not self.manifeste.permissions.racine:
            raise PermissionError("le module « %s » n'a pas demandé la racine ([permissions] racine)" % self.module)
        if not any(c.id == commande for c in self.manifeste.racine):
            raise PermissionError("le module « %s » n'a pas déclaré la commande racine « %s » ([[racine]])" % (self.module, commande))
        return self._intro["racine"].demander(self.module, commande, args, stdin, delai)

    def est_admin(self, compte: str) -> bool:
        """Ce compte est-il administrateur ? Une question d'étendue (qui voit le partagé), jamais un droit : aucune permission à demander."""
        d = self._intro["droits"]
        return bool(compte) and compte not in ("cassandra", "itare", "noyau", "operateur") and bool(d.est_admin(compte))

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
        if self.manifeste.permissions.stockage_par_societe:
            return StockageParSociete(lambda soc: self._intro["stockage"](self.module, soc), lambda: self._societe.valeur)
        return self._intro["stockage"](self.module)

    def frein_actif(self, nom: str) -> bool:
        """Un frein d'urgence est-il posé (« gel », « envois ») ? Lecture seule, sans permission : un moteur n'a pas de compte, l'exécuteur ne peut donc pas lui appliquer
        le frein « envois » ; c'est à lui de le consulter avant de faire sortir quoi que ce soit de la maison."""
        f = self._intro.get("frein_actif")
        return bool(f and f(str(nom)))

    def stockage_partage(self, source: str, type: str):
        """La base de CE module dans la société `source`, à LIRE seulement : permis quand `source` partage ce `type` avec la société de l'acte (ou si c'est la même).
        [permissions] stockage_par_societe. Le module n'y écrit jamais."""
        if not self.manifeste.permissions.stockage_par_societe:
            raise PermissionError("le module « %s » n'a pas de base par société ([permissions] stockage_par_societe)" % self.module)
        dest = self._societe.valeur or "1"
        if source != dest and not self._intro["partage_actif"](source, dest, type):
            raise PermissionError("cette société ne partage pas cela avec la vôtre")
        return self._intro["stockage"](self.module, source)

    def stockage_lecture(self, module: str):
        """La base d'un AUTRE module, en lecture seule — pour le module du journal, qui lit les journaux des autres
        ([permissions] stockage_lecture = true). Un module ne s'en sert jamais pour écrire chez un autre."""
        if not self.manifeste.permissions.stockage_lecture:
            raise PermissionError("le module « %s » n'a pas demandé de lire la base des autres ([permissions] stockage_lecture)" % self.module)
        return self._intro["stockage_lecture"](module)

    ACTEURS_AGENTS = ("itare", "cassandra", "agent")

    def agir(self, capacite: str, args=None, acteur: str = "itare", cause=None, essai: bool = False) -> dict:
        """Agit comme un agent, AU NOM du compte en cours : la capacité passe par l'exécuteur comme n'importe quel acte (droits du compte, acteurs permis, palier, preuve, retour, journal).
        Le module ne peut se faire passer que pour un agent — jamais pour un humain ni pour le noyau ([permissions] agir)."""
        if not self.manifeste.permissions.agir:
            raise PermissionError("le module « %s » n'a pas demandé d'agir comme un agent ([permissions] agir)" % self.module)
        if acteur not in self.ACTEURS_AGENTS:
            raise PermissionError("un module n'agit que comme un agent (%s), jamais comme « %s »" % (", ".join(self.ACTEURS_AGENTS), acteur))
        return self._intro["agir"](capacite, dict(args or {}), self.compte, acteur, cause, essai)

    def outils(self, acteur: str = "itare") -> list:
        """Les outils d'un agent pour le compte en cours : chaque capacité que cet acteur peut utiliser et que ce compte a le droit d'utiliser, avec ses arguments, son risque et son palier."""
        if not self.manifeste.permissions.agir:
            raise PermissionError("le module « %s » n'a pas demandé d'agir comme un agent ([permissions] agir)" % self.module)
        return self._intro["outils"](self.compte, acteur)

    def chiffrer(self, valeur, etiquette: str, compte: str = "") -> str:
        """Chiffre un secret pour la base de CE module (AES-256-GCM, clé du serveur). L'étiquette et le module sont liés au chiffré : copié ailleurs, il ne se lit plus."""
        if not self.manifeste.permissions.secrets:
            raise PermissionError("le module « %s » n'a pas demandé les secrets ([permissions] secrets)" % self.module)
        return self._intro["reglages"].chiffrer(valeur, "%s:%s" % (self.module, etiquette), compte)

    def dechiffrer(self, chiffre: str, etiquette: str, compte: str = "") -> str:
        if not self.manifeste.permissions.secrets:
            raise PermissionError("le module « %s » n'a pas demandé les secrets ([permissions] secrets)" % self.module)
        return self._intro["reglages"].dechiffrer(chiffre, "%s:%s" % (self.module, etiquette), compte)

    def reglage(self, nom: str, compte=None):
        """La valeur EFFECTIVE d'un réglage que CE module a déclaré (« nom » sans le préfixe du module). Pour un réglage de portée compte,
        celle du compte au nom duquel on agit (ou `compte`). Le module qui déclare un secret est le seul à le lire en clair."""
        return self._intro["reglages"].valeur("%s.%s" % (self.module, nom), self.compte if compte is None else compte, self.societe)

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

    def espace_societe(self, societe: str = "", creer: bool = True):
        """Ce que toute une société partage pour ce module : <sociétés>/<société>/commun/<module> (par défaut, la société active)."""
        if not self.manifeste.permissions.espace_utilisateur:
            raise PermissionError("le module « %s » n'a pas demandé l'espace des utilisateurs ([permissions] espace_utilisateur)" % self.module)
        return chemins.espace_societe(societe or self.societe or "1", self.module, creer=creer)

    def espace_compte(self, compte: str = "", creer: bool = True):
        """L'espace d'un utilisateur POUR CE MODULE, dans le grand répertoire de sa société : <sociétés>/<société>/utilisateurs/<compte>/<module>.
        Tout utilisateur a une société : ses répertoires et ses documents ne vivent jamais hors d'elle."""
        if not self.manifeste.permissions.espace_utilisateur:
            raise PermissionError("le module « %s » n'a pas demandé l'espace des utilisateurs ([permissions] espace_utilisateur)" % self.module)
        c = (compte or self.compte or "").strip()
        if not c:
            raise ValueError("aucun compte : un espace est toujours celui de quelqu'un")
        soc = self._intro["societe_de"](c) if "societe_de" in self._intro else (self.societe or "1")
        return chemins.espace_compte(soc, c, self.module, creer=creer)

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
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _Fil, _Compte, _Acteur, Contexte
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
