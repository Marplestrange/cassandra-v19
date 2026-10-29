# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le manifeste
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #fc82cf
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le manifeste : le contrat qu'un module signe pour se brancher sur le noyau.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=fc82cf ▼▼▼
"""Le manifeste : le contrat qu'un module signe pour se brancher sur le noyau.

Un module n'existe pour le noyau que par son manifeste (CN_manifeste.toml). Le noyau le lit,
le valide, calcule l'ordre d'installation, inscrit les objets, les événements et les
capacités, et ouvre les écrans. Le module n'a que son métier à écrire.

Règle de souveraineté inscrite dans le contrat : la sûreté vient de la RÉVERSIBILITÉ, jamais
d'une permission humaine. Toute capacité qui écrit doit donc déclarer son périmètre, sa
preuve et son retour arrière ; sans cela le manifeste est refusé.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .CN_sections import Section, ID as SECTION_ID, ICONE as SECTION_ICONE

VERSION_NOYAU = "0.1.0"
API_NOYAU = "1.0"     # le contrat offert aux modules (ctx, manifeste). Sa version MAJEURE change quand on casse la compatibilité.

RISQUES = ("lecture", "faible", "moyen", "eleve")
PALIERS = ("raconter", "auto", "maitre")
ACTEURS = ("cassandra", "itare", "humain", "compte", "agent", "anonyme")
MODES_MOTEUR = ("periodique", "evenement", "demande")
ROLES_MENU = ("utilisateur", "admin")
BASES_HABILLAGE = ("clair", "creme", "sombre")
GABARITS = ("tableau", "liste_detail", "libre")                  # comment l'interface compose un écran
ZONES = ("entete", "principal", "lateral")
TAILLES = ("s", "m", "l")
COMPOSANTS = ("nombre", "jauge", "liste", "etat", "serie", "texte")   # ce que l'interface sait dessiner pour une tuile
_COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")
_VALEUR_THEME = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([0-9., %]+\)|\d+(\.\d+)?(px|rem|em|%))$")
BADGES_MENU = ("", "constats", "moteurs")
ZONES_MENU = ("principal", "avatar")
# Les événements du noyau lui-même : un module peut les écouter sans qu'aucun module ne les « émette ».
EVENEMENTS_DU_NOYAU = ("noyau.", "module.", "capacite.", "constat.", "objet.", "moteur.", "savoir.", "humain.")
IMPORTANCES = ("vital", "important", "optionnel")
TYPES_RESERVES = ("noyau", "module", "capacite", "constat", "objet", "moteur", "savoir", "humain")
CONFIANCES = ("interne", "signe", "tiers", "local")

_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
# Une icône qu'un module APPORTE : le tracé d'un <path> (24 x 24, trait), rien d'autre. Seules les commandes de tracé, les nombres et leurs séparateurs : pas de balise, pas de guillemet, pas de lien.
# Un SVG libre dans un manifeste d'éditeur tiers serait un script en puissance ; un tracé n'en peut pas être un.
_TRACE = re.compile(r"^[Mm][MmLlHhVvCcSsQqTtAaZz0-9 .,\-]{3,799}$")


def trace_valide(t) -> bool:
    return isinstance(t, str) and bool(_TRACE.match(t))
# une dépendance : « dns », ou « dns >=0.2, <1 » (opérateurs >= <= == > <, versions à points)
_REQ = re.compile(r"^([a-z][a-z0-9_]{1,40})\s*((?:(?:>=|<=|==|>|<)\s*\d+(?:\.\d+){0,3}\s*,?\s*)*)$")
_CLAUSE = re.compile(r"(>=|<=|==|>|<)\s*(\d+(?:\.\d+){0,3})")


def version_de(texte) -> tuple:
    """« 0.2.1 » donne (0, 2, 1) ; ce qui n'est pas numérique (suffixe, build) est ignoré."""
    nombres = []
    for x in str(texte or "").split("+")[0].split("-")[0].split("."):
        if not x.isdigit():
            break
        nombres.append(int(x))
    return tuple(nombres) or (0,)


def satisfait(version, contrainte: str) -> bool:
    """La version répond-elle à « >=0.2, <1 » ? Une contrainte vide est toujours satisfaite ; les versions se comparent chiffre à chiffre."""
    v = version_de(version)
    for op, ref in _CLAUSE.findall(contrainte or ""):
        r = version_de(ref)
        n = max(len(v), len(r))
        a, b = v + (0,) * (n - len(v)), r + (0,) * (n - len(r))
        if not {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b}[op]:
            return False
    return True


def lire_requis(texte):
    """(id, contrainte) d'une dépendance écrite, ou None si elle est mal écrite."""
    m = _REQ.match(str(texte or "").strip())
    return (m.group(1), m.group(2).strip().rstrip(",").strip()) if m else None
_ID_POINT = re.compile(r"^[a-z][a-z0-9_]{1,40}(\.[a-z][a-z0-9_]{1,40})?$")      # un point d'évolution : « verdict.composer »
_CONTRAT = re.compile(r"^\d+\.\d+$")                                           # la version d'un contrat : majeure.mineure
_EVT = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_VER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class ManifesteInvalide(ValueError):
    """Un ou plusieurs défauts. `erreurs` les liste tous : on corrige en une passe."""

    def __init__(self, erreurs, source=""):
        self.erreurs = list(erreurs)
        self.source = str(source)
        tete = "manifeste invalide" + (" (%s)" % self.source if self.source else "")
        super().__init__(tete + " :\n  - " + "\n  - ".join(self.erreurs))


@dataclass(frozen=True)
class Objet:
    type: str
    libelle: str


@dataclass(frozen=True)
class Capacite:
    id: str
    libelle: str
    risque: str
    perimetre: tuple = ()
    preuve: str = ""
    retour: str = ""
    paliers: tuple = ("raconter",)
    qui: tuple = ("cassandra", "itare", "humain", "agent")      # « agent » : un agent invité (jeton) ; ses droits restent ceux de son invitant
    droit: str = ""            # le droit qu'un COMPTE doit détenir pour l'utiliser (voir [[droits]]) ; vide : aucun droit particulier
    masque: tuple = ()         # noms d'arguments et de résultats qui ne vont JAMAIS au journal (mot de passe, jeton de session...)
    externe: bool = False      # ce qu'elle lit vient de l'EXTÉRIEUR (un message reçu, une page web) : du texte étranger entre dans le tour, et l'agent ne le tient pas pour des instructions
    sortant: bool = False      # ce qu'elle fait SORT de la maison (un message envoyé, un lien public) : après une lecture externe dans le même tour, elle ne part pas toute seule

    @property
    def ecrit(self) -> bool:
        return self.risque != "lecture"

    @property
    def ecrit_sans_preuve(self) -> bool:
        """Une capacité publique qui écrit doit porter sa preuve (elle l'a déjà : le manifeste l'exige) ; ici, jamais d'élévation du risque « eleve »."""
        return self.risque == "eleve"


@dataclass(frozen=True)
class Droit:
    """Un droit qu'un module déclare. Qualifié « module.droit » partout ailleurs.
    Le module des droits l'attribue à des comptes et à des groupes ; l'exécuteur le vérifie, en un seul endroit."""
    id: str
    libelle: str
    defaut: bool = False       # accordé d'office à tout compte connu (sinon : à attribuer)
    sensible: bool = False     # signalé comme tel à celui qui l'attribue (gestion des comptes, des secrets...)


@dataclass(frozen=True)
class Reglage:
    """Un réglage qu'un module déclare (la V18 les gardait dans un config.json réécrit en entier). Qualifié « module.reglage »."""
    id: str
    libelle: str
    type: str = "texte"        # texte | entier | booleen | choix | secret
    defaut: object = ""
    choix: tuple = ()          # pour le type « choix »
    portee: str = "global"     # global | compte (une valeur propre à chaque compte) | societe (une valeur propre à chaque société, repli sur la globale)
    minimum: object = None
    maximum: object = None
    aide: str = ""


@dataclass(frozen=True)
class Detecteur:
    id: str
    libelle: str
    frequence_s: int
    capacite: str = ""


@dataclass(frozen=True)
class Moteur:
    """Une boucle ou une passe qui tourne seule. Le noyau l'ordonnance : le module n'ouvre jamais de thread."""
    id: str
    libelle: str
    mode: str                  # periodique | evenement | demande
    toutes_les_s: int = 0      # mode periodique
    sur: tuple = ()            # mode evenement : le ou les types d'événement qui le réveillent (dans evenements.ecoute)
    duree_max_s: int = 60      # au-delà, le moteur est tenu pour figé et ne s'empile pas
    asynchrone: bool = False   # mode evenement : l'événement est mis en FILE et traité à part, un à la fois, sans retenir celui qui l'a émis (un tour d'agent dure des secondes : le message qui le réveille ne doit pas l'attendre)


@dataclass(frozen=True)
class Menu:
    """Une entrée de menu déclarée par un module. Le module de menus du noyau assemble tout, à chaud."""
    id: str
    libelle: str
    ecran: str = ""            # un écran du MÊME module (la page ouverte) ; vide : simple regroupement
    parent: str = ""           # vide : au premier niveau de la famille ; sinon un menu du module, ou « module:menu »
    ordre: int = 100
    role: str = "utilisateur"  # qui le voit : utilisateur | admin
    icone: str = ""
    badge: str = ""            # compteur affiché : constats (ouverts du module) | moteurs (à surveiller)
    droit: str = ""            # le droit qu'un compte doit détenir pour voir cette entrée
    groupe: str = ""           # le groupe d'affichage (barre du haut) où l'entrée se range : vide, le module d'affichage range selon la famille
    zone: str = "principal"    # principal : la barre et la colonne ; avatar : le menu de l'avatar (paramètres, compte, coffre…)


@dataclass(frozen=True)
class Widget:
    """Une tuile qu'un module propose d'afficher. Le module dit CE QU'IL MONTRE ; le module d'affichage du noyau décide où et comment."""
    id: str
    libelle: str
    ecran: str = "accueil"     # « accueil », ou un écran du module
    zone: str = "principal"    # entete | principal | lateral
    taille: str = "m"          # s | m | l
    ordre: int = 100
    role: str = "utilisateur"
    composant: str = "nombre"  # nombre | jauge | liste | etat | serie | texte
    source: str = ""           # une capacité de LECTURE du module qui fournit la donnée
    rafraichir_s: int = 0      # 0 : pas de rafraîchissement ; sinon au moins 5 secondes
    droit: str = ""            # le droit qu'un compte doit détenir pour voir cette tuile


@dataclass(frozen=True)
class Theme:
    """La touche de couleur d'un module. Il n'écrase jamais le thème du noyau : ses jetons s'appellent --mod-<module>-<nom>."""
    accent: str = ""
    tokens: tuple = ()         # ((nom, valeur), ...)


@dataclass(frozen=True)
class PointExtension:
    """Un endroit où D'AUTRES modules peuvent brancher quelque chose : une colonne dans une liste, une tuile dans une fiche, une règle dans un contrôle.
    Le module qui l'offre dit ce qu'il attend (`attend` : les clés des données d'une contribution) ; il lit les contributions des modules ACTIFS (`modules.contributions`) sans les connaître."""
    id: str
    libelle: str
    attend: tuple = ()         # les clés que chaque contribution doit porter dans `donnees`


@dataclass(frozen=True)
class Contribution:
    """Ce qu'un module branche sur le point d'extension d'un module (le sien ou un autre) : « module:point », un identifiant, un libellé et des données simples (texte, nombre, booléen)."""
    point: str                 # « module:point »
    id: str
    libelle: str
    donnees: tuple = ()        # ((clé, valeur), ...)


@dataclass(frozen=True)
class Onglet:
    """Un onglet qu'un module ajoute à la fiche d'un OBJET, que cet objet soit le sien ou celui d'un autre module.
    Le module de l'objet ne sait rien de l'onglet : l'interface demande « quels onglets pour cet objet ? » et ouvre l'écran du module qui l'a déclaré, avec la référence."""
    id: str
    libelle: str
    objet: str                 # le type d'objet visé : « note », ou « module:type » (un type déclaré par un autre module)
    ecran: str = ""            # un écran de CE module, qui reçoit la référence de l'objet
    ordre: int = 100
    role: str = "utilisateur"
    icone: str = ""
    droit: str = ""


@dataclass(frozen=True)
class Signal:
    """Ce qu'un module signale au bureau du jour : une capacité de LECTURE du module qui rend {"items": [...]} (ce qui brûle, ce qui est à regarder, ce qui tombe aujourd'hui).
    Le module « jour » les assemble pour un compte ; une source qui échoue devient une ligne de panne, jamais un silence."""
    id: str
    libelle: str
    capacite: str              # une capacité de lecture de CE module
    admin: bool = False        # vrai : lue seulement pour un administrateur (une source de la machine)
    cadence_s: int = 0         # une source lente n'est relue qu'après ce délai ; 0 : à chaque calcul


@dataclass(frozen=True)
class Mesure:
    """Une mesure que ce module expose à l'historique : une courbe (jauge) ou un décompte d'événements (compteur), rendue par une capacité de LECTURE du module
    qui répond {"series": [{"nom": ..., "points": [["AAAA-MM-JJ HH:MM:SS", valeur], ...]}]} (heure UTC). Le module « mesures » en tire sources, courbes,
    habitudes, écarts, tendance et verdict ; chaque module ne dit que ce qu'il sait : ses mesures, pas la façon de les lire."""
    id: str
    libelle: str
    capacite: str              # une capacité de lecture de CE module, appelée avec {mesure, depuis, jusqu_a}
    genre: str = "jauge"       # « jauge » (une valeur dans le temps) | « compteur » (des événements : chaque point en compte un, ou sa valeur)
    unite: str = ""
    famille: str = ""
    agregat: str = "moy"       # pour une jauge : moy | min | max | somme
    groupee: bool = False      # une courbe par élément (un site, une machine) : on ne garde que les pires
    pire: str = "haut"         # « haut » : plus c'est haut, pire c'est ; « bas » l'inverse (disponibilité, jours avant expiration)
    plafond: float = 0         # pour la tendance : la valeur de saturation (100 %) ; 0 : pas de prévision
    nature: str = "serie"      # « etat » : une photo (unités en échec), jamais comparée à une habitude
    fraicheur_s: int = 0       # au-delà de ce silence, une mesure qui écrivait est dite « muette » ; 0 : pas de seuil (relevés non périodiques)
    vide: str = ""             # ce que dit une source sans données : « rien_a_signaler » | « non_configuree » | « jamais_utilisee »
    description: str = ""


@dataclass(frozen=True)
class PointEvolution:
    """Un point d'évolution (docs/CN_NEXUS.md §3, docs/CN_FORMAT.md) : une fonction PURE que ce module déclare. Le dépôt en écrit la RÉFÉRENCE ; une EC peut la remplacer à l'exécution.
    Le module l'appelle par ctx.point(id, entrée) : des données en entrée, des données en sortie, quel que soit le langage de l'EC qui la sert."""
    id: str
    libelle: str
    contrat: str               # la version du contrat « majeure.mineure » : une EC prouvée sur 1.3 sert un nexus en 1.3 ou plus, jamais en 2.x
    reference: str             # chemin SANS extension, relatif au dossier du module : « points/EC_verdict_composer » (le noyau trouve le fichier, de n'importe quel format)
    fonction: str = ""         # le nom de la fonction ; par défaut le dernier segment de l'identifiant
    runtime: str = "python"    # l'environnement d'exécution de la référence
    mesure: str = ""           # une mesure déclarée de ce module (la fitness), facultative
    delai_ms: int = 2000       # au-delà, une EC qui répond est comptée en faute (le délai ne se coupe pas dans le processus)


@dataclass(frozen=True)
class CommandeRacine:
    """Une commande que ce module demande au courtier (root), nommée : le programme /usr/libexec/cassandra/<module>/<id>, posé en root par l'installation du module.
    Le noyau ne dit jamais quoi exécuter, seulement laquelle de ces commandes et avec quels arguments ; chaque programme valide ses propres arguments."""
    id: str
    libelle: str
    lecture: bool = False      # vrai : la commande ne modifie rien (un état à lire que le noyau ne peut pas lire sans privilège)


@dataclass(frozen=True)
class Habillage:
    """Un thème complet : un jeu de variables CSS qui remplace celui d'une base (clair, creme ou sombre). Un module peut en livrer plusieurs, l'interface
    les propose dans le sélecteur d'apparence. Le fichier ne contient QUE des variables (--nom: valeur;) : aucun sélecteur, aucune adresse, aucun script."""
    id: str
    libelle: str
    base: str = "clair"        # clair | creme | sombre : ce qu'il habille quand une variable manque
    fichier: str = ""          # relatif au dossier du module, ex. « themes/CN_ardoise.css »


@dataclass(frozen=True)
class Ecran:
    id: str
    libelle: str
    domaine: str = ""
    gabarit: str = "libre"     # tableau | liste_detail | libre
    titre: str = ""


@dataclass(frozen=True)
class Installation:
    script: str = ""
    verification: str = ""
    retrait: str = ""
    migrations: str = ""


@dataclass(frozen=True)
class Permissions:
    """Ce qu'un module DEMANDE, dit avant l'installation (comme un module store l'affichera).
    Appliqué par le noyau : espace_utilisateur. Déclaratif jusqu'à la cage par processus : reseau, ecritures, privileges."""
    espace_utilisateur: bool = False   # peut demander l'espace d'un utilisateur (/var/www/<u>/data/cassandra/<module>)
    reseau: tuple = ()                 # hôtes joints (« api.exemple.org »)
    ecritures: tuple = ()              # chemins système écrits (hors son espace)
    privileges: tuple = ()             # ce que ses scripts font en root (« installer »...)
    introspection: bool = False        # peut lire les manifestes des modules actifs et leurs compteurs (module de menus, de supervision)
    lectures: bool = False             # peut appeler les capacités de LECTURE des autres modules (module d'affichage)
    droits: bool = False               # peut administrer les droits des comptes (le module des droits)
    identite: bool = False             # peut administrer l'identité des comptes : mots de passe, sessions (le module des comptes)
    reglages: bool = False             # peut écrire les réglages des autres modules (le module des réglages)
    stockage: bool = False             # a SA base SQLite (donnees/modules/<id>.db) et ses migrations (migrations/NNN_nom.sql)
    stockage_lecture: bool = False     # peut lire, en lecture seule, la base d'un AUTRE module (le module du journal, pour son flux unifié) : ctx.stockage_lecture(mid)
    secrets: bool = False              # peut chiffrer/déchiffrer des secrets pour SA base (ctx.chiffrer / ctx.dechiffrer) : clés d'API de modèles, jetons...
    racine: bool = False               # peut demander au courtier (root) les commandes qu'il déclare ([[racine]]) : ctx.racine(...)
    agir: bool = False                 # peut agir comme un agent (ctx.agir) et lister les outils d'un agent (ctx.outils) : le module des agents. Les droits et les paliers s'appliquent comme à tout acte
    modules: bool = False              # peut lire le catalogue des modules et en changer l'état (activer, désactiver) : le module « modules ». Les droits et les paliers s'appliquent comme à tout acte
    urgence: bool = False              # peut poser et lever les freins du noyau (gel de l'autonomie, coupure des envois) : le module des gestes d'urgence
    evolution: bool = False            # peut piloter l'évolution du noyau (cibles, propositions, retour, visites) : le module « evolution ». Les droits et les paliers de ses capacités restent ceux de chaque geste.
    stockage_par_societe: bool = False  # sa base est UNE PAR SOCIÉTÉ (donnees/modules/<id>@<société>.db ; la société principale garde <id>.db) : le code du module ne change pas, `ctx.stockage` suit la société de l'acte, et ses moteurs tournent société par société


@dataclass(frozen=True)
class Manifeste:
    id: str
    nom: str
    version: str
    noyau_min: str
    description: str
    confiance: str
    requiert: tuple = ()
    auteur: str = ""
    licence: str = ""
    site: str = ""
    api: str = "1"             # la version MAJEURE de l'API du noyau que ce module vise
    permissions: Permissions = field(default_factory=Permissions)
    essentiel: bool = False    # un module essentiel ne se désactive pas (comptes, coffre, notifications...)
    instance: bool = False     # un module d'instance (hébergement, sécurité, flotte, sauvegardes…) n'existe que dans la société principale : elle seule décide du comportement de l'application
    famille: str = ""          # la SECTION où le module se range (« securite », « reseau »...) ; écrite section = "..." (famille, ancien nom, est lu aussi)
    sections: tuple = ()       # les sections NOUVELLES que ce module apporte ([[sections]]) : voir CN_sections
    contraintes: tuple = ()    # ((id, « >=0.2, <1 »), ...) : les versions que les dépendances doivent avoir
    conflits: tuple = ()       # des modules qui ne peuvent pas être actifs en même temps que celui-ci
    suggere: tuple = ()        # des modules qui lui servent sans être requis
    fournit: tuple = ()        # des noms de service que ce module rend : un autre module peut requérir « courrier » sans dire QUEL module le fournit
    famille_libelle: str = ""  # le nom lisible d'une famille NOUVELLE (celle du module n'existe pas encore au menu) : « Finance et ventes »
    icone_trace: str = ""      # l'icône du module lui-même : un tracé de <path> (voir trace_valide)
    famille_icone_trace: str = ""  # l'icône de sa famille nouvelle, de même forme
    famille_icone: str = ""    # l'icône (une clé de l'interface, en trait) de cette famille ; vide : l'icône générique
    importance: str = ""       # ce que la maison perd sans ce module : « vital » (elle ne tient plus), « important » (une fonction s'arrête), « optionnel » (on s'en passe) ; vide = non déclaré
    sans: str = ""             # une phrase : ce qui s'arrête, concrètement, quand ce module est désactivé
    objets: tuple = ()
    droits: tuple = ()         # les droits que ce module déclare ([[droits]])
    reglages: tuple = ()       # les réglages que ce module déclare ([[reglages]])
    emet: tuple = ()
    ecoute: tuple = ()
    capacites: tuple = ()
    detecteurs: tuple = ()
    moteurs: tuple = ()
    menus: tuple = ()
    points_extension: tuple = ()   # les points où d'autres modules branchent quelque chose
    contributions: tuple = ()      # ce que ce module branche chez d'autres (ou chez lui)
    onglets: tuple = ()
    habillages: tuple = ()
    signaux: tuple = ()
    mesures: tuple = ()
    points_evolution: tuple = ()
    racine: tuple = ()
    widgets: tuple = ()
    theme: Theme = field(default_factory=Theme)
    ecrans: tuple = ()
    installation: Installation = field(default_factory=Installation)
    source: str = ""

    def capacite(self, cid: str):
        return next((c for c in self.capacites if c.id == cid), None)


def _version(s: str):
    m = _VER.match(str(s))
    return tuple(int(x) for x in m.groups()) if m else None


def _liste_de_textes(valeur, nom, erreurs, motif=None):
    if valeur is None:
        return ()
    if not isinstance(valeur, list) or not all(isinstance(x, str) for x in valeur):
        erreurs.append("%s : une liste de textes est attendue" % nom)
        return ()
    if motif is not None:
        for x in valeur:
            if not motif.match(x):
                erreurs.append("%s : « %s » n'a pas la forme attendue" % (nom, x))
    return tuple(valeur)


def valider(brut: dict) -> list:
    """Rend la liste de TOUS les défauts d'un manifeste lu (vide = valide)."""
    e = []
    if not isinstance(brut, dict):
        return ["le manifeste doit être une table TOML"]
    m = brut.get("module")
    if not isinstance(m, dict):
        return ["la section [module] est absente"]

    mid = m.get("id", "")
    if not isinstance(mid, str) or not _ID.match(mid):
        e.append("module.id : minuscules, chiffres et _ (2 à 41 caractères, commence par une lettre)")
    for champ in ("nom", "description"):
        if not isinstance(m.get(champ), str) or not m.get(champ).strip():
            e.append("module.%s : texte obligatoire" % champ)
    if _version(m.get("version", "")) is None:
        e.append("module.version : forme X.Y.Z attendue")
    nm = _version(m.get("noyau_min", ""))
    if nm is None:
        e.append("module.noyau_min : forme X.Y.Z attendue")
    elif nm > _version(VERSION_NOYAU):
        e.append("module.noyau_min : le module exige le noyau %s, ce noyau est en %s" % (m.get("noyau_min"), VERSION_NOYAU))
    if m.get("confiance", "interne") not in CONFIANCES:
        e.append("module.confiance : %s" % " | ".join(CONFIANCES))
    for champ in ("auteur", "licence", "site"):
        if champ in m and (not isinstance(m[champ], str) or len(m[champ]) > 200):
            e.append("module.%s : un texte de 200 caractères au plus" % champ)
    api = str(m.get("api", "1"))
    if not re.match(r"^\d+$", api):
        e.append("module.api : la version majeure de l'API visée (par exemple « 1 »)")
    elif api != API_NOYAU.split(".")[0]:
        e.append("module.api : ce module vise l'API %s, ce noyau offre l'API %s" % (api, API_NOYAU))
    perm = brut.get("permissions", {}) or {}
    if not isinstance(perm, dict):
        e.append("permissions : une table est attendue")
        perm = {}
    for champ in ("reseau", "ecritures", "privileges"):
        _liste_de_textes(perm.get(champ), "permissions.%s" % champ, e)
    for champ in ("espace_utilisateur", "introspection", "lectures", "stockage_lecture", "modules", "urgence", "evolution", "stockage_par_societe"):
        if champ in perm and not isinstance(perm[champ], bool):
            e.append("permissions.%s : vrai ou faux" % champ)
    for chemin in perm.get("ecritures", []) if isinstance(perm.get("ecritures"), list) else []:
        if not str(chemin).startswith("/") or ".." in str(chemin).split("/"):
            e.append("permissions.ecritures : « %s » doit être un chemin absolu sans « .. »" % chemin)
    if "essentiel" in m and not isinstance(m["essentiel"], bool):
        e.append("module.essentiel : vrai ou faux")
    if "instance" in m and not isinstance(m["instance"], bool):
        e.append("module.instance : vrai ou faux")
    for champ in ("section", "famille"):
        if champ in m and (not isinstance(m[champ], str) or len(m[champ]) > 40):
            e.append("module.%s : un texte de 40 caractères au plus" % champ)
    e.extend(_valider_sections(brut.get("sections", [])))
    if "famille_libelle" in m and (not isinstance(m["famille_libelle"], str) or not m["famille_libelle"].strip() or len(m["famille_libelle"]) > 40):
        e.append("module.famille_libelle : un nom de 40 caractères au plus")
    if "famille_icone" in m and (not isinstance(m["famille_icone"], str) or not re.match(r"^[a-z][a-z0-9_]{1,30}$", m["famille_icone"])):
        e.append("module.famille_icone : une clé d'icône (lettres minuscules, chiffres, _)")
    for champ in ("icone_trace", "famille_icone_trace"):
        if champ in m and not trace_valide(m[champ]):
            e.append("module.%s : un tracé de path seulement (commandes M L H V C S Q T A Z, nombres, espaces, virgules ; 800 caractères au plus)" % champ)
    if "importance" in m and m["importance"] not in IMPORTANCES:
        e.append("module.importance : %s" % " ou ".join("« %s »" % x for x in IMPORTANCES))
    if "sans" in m and (not isinstance(m["sans"], str) or len(m["sans"]) > 300):
        e.append("module.sans : une phrase de 300 caractères au plus (ce qui s'arrête quand le module est désactivé)")
    if m.get("essentiel") is True and m.get("importance", "vital") != "vital":
        e.append("module.importance : un module essentiel est « vital »")
    requiert = []
    brut_req = m.get("requiert", [])
    if not isinstance(brut_req, list):
        e.append("module.requiert : une liste")
    else:
        for x in brut_req:
            lu = lire_requis(x)
            if lu is None:
                e.append("module.requiert : « %s » mal écrit (« dns » ou « dns >=0.2, <1 »)" % x)
            else:
                requiert.append(lu[0])
    for champ in ("conflits", "suggere", "fournit"):
        if champ in m:
            l = _liste_de_textes(m.get(champ), "module.%s" % champ, e, _ID)
            if mid in l and champ != "fournit":
                e.append("module.%s : un module ne peut pas se citer lui-même" % champ)
    if set(m.get("conflits", []) if isinstance(m.get("conflits"), list) else []) & set(requiert):
        e.append("module.conflits : un module ne peut pas à la fois requérir et refuser le même module")
    if mid in requiert:
        e.append("module.requiert : un module ne peut pas se requérir lui-même")

    # objets : le propriétaire d'un type est unique, et c'est lui qui nomme ses événements
    types = []
    for i, o in enumerate(brut.get("objets", []) or []):
        if not isinstance(o, dict) or not _ID.match(str(o.get("type", ""))) or not str(o.get("libelle", "")).strip():
            e.append("objets[%d] : « type » (identifiant) et « libelle » obligatoires" % i)
            continue
        if o["type"] in types:
            e.append("objets[%d] : le type « %s » est déclaré deux fois" % (i, o["type"]))
        if o["type"] in TYPES_RESERVES:
            e.append("objets[%d] : « %s » est réservé au noyau (ses événements s'appellent ainsi)" % (i, o["type"]))
        types.append(o["type"])

    ev = brut.get("evenements", {}) or {}
    emet = _liste_de_textes(ev.get("emet"), "evenements.emet", e, _EVT)
    ecoute = _liste_de_textes(ev.get("ecoute"), "evenements.ecoute", e, _EVT)
    for x in emet:
        if x.split(".")[0] not in types:
            e.append("evenements.emet : « %s » doit commencer par un type d'objet que ce module possède (%s)" % (x, ", ".join(types) or "aucun"))
    for x in ecoute:
        if x in emet:
            e.append("evenements.ecoute : « %s » est émis par le module lui-même" % x)

    # droits : déclarés par le module, qualifiés « module.droit » ailleurs
    droits_ids = []
    for i, d in enumerate(brut.get("droits", []) or []):
        nom = "droits[%d]" % i
        if not isinstance(d, dict) or not _ID.match(str(d.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if d["id"] in droits_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, d["id"]))
        droits_ids.append(d["id"])
        if not str(d.get("libelle", "")).strip():
            e.append("droit « %s » : libellé obligatoire" % d["id"])
        for champ in ("defaut", "sensible"):
            if champ in d and not isinstance(d[champ], bool):
                e.append("droit « %s ».%s : vrai ou faux" % (d["id"], champ))

    # tout module déclare ses droits : sans eux, on ne pourrait ni lui refuser un compte, ni le confier à un groupe
    if not droits_ids:
        e.append("droits : un module déclare au moins un droit ([[droits]]) ; sans lui, aucun compte ni groupe ne peut se voir accorder ou refuser ce module")

    # réglages : déclarés par le module, qualifiés « module.reglage » ailleurs
    reglages_ids = []
    for i, r in enumerate(brut.get("reglages", []) or []):
        nom = "reglages[%d]" % i
        if not isinstance(r, dict) or not _ID.match(str(r.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if r["id"] in reglages_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, r["id"]))
        reglages_ids.append(r["id"])
        nom = "réglage « %s »" % r["id"]
        if not str(r.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        t = r.get("type", "texte")
        if t not in ("texte", "entier", "booleen", "choix", "secret"):
            e.append("%s.type : texte | entier | booleen | choix | secret" % nom)
        if r.get("portee", "global") not in ("global", "compte", "societe"):
            e.append("%s.portee : global | compte | societe" % nom)
        if t == "choix":
            ch = r.get("choix")
            if not isinstance(ch, list) or not ch:
                e.append("%s.choix : une liste non vide est attendue pour le type « choix »" % nom)
            elif "defaut" in r and r["defaut"] not in ch:
                e.append("%s.defaut : doit figurer dans choix" % nom)
        if t == "secret" and r.get("defaut"):
            e.append("%s : un secret n'a pas de défaut écrit dans un manifeste" % nom)
        if t == "entier":
            for b in ("minimum", "maximum", "defaut"):
                if b in r and (isinstance(r[b], bool) or not isinstance(r[b], int)):
                    e.append("%s.%s : un entier est attendu" % (nom, b))
        if t == "booleen" and "defaut" in r and not isinstance(r["defaut"], bool):
            e.append("%s.defaut : vrai ou faux" % nom)

    def _droit_ok(valeur, nom):
        """Un droit cité : un droit de ce module (« lire »), ou celui d'un autre (« module.lire »)."""
        if valeur in (None, ""):
            return
        if not isinstance(valeur, str) or not (_ID.match(valeur) or re.match(r"^[a-z][a-z0-9_]{1,40}\.[a-z][a-z0-9_]{1,40}$", valeur)):
            e.append("%s.droit : « %s » n'a pas la forme attendue (un droit du module, ou « module.droit »)" % (nom, valeur))
        elif "." not in valeur and valeur not in droits_ids:
            e.append("%s.droit : « %s » n'est pas un droit de ce module ([[droits]])" % (nom, valeur))

    # capacités : une capacité qui écrit porte sa propre sûreté
    ids = []
    for i, c in enumerate(brut.get("capacites", []) or []):
        nom = "capacites[%d]" % i
        if not isinstance(c, dict):
            e.append("%s : table attendue" % nom)
            continue
        cid = c.get("id", "")
        if not isinstance(cid, str) or not _ID.match(cid):
            e.append("%s.id : identifiant invalide" % nom)
        elif cid in ids:
            e.append("%s.id : « %s » est déclarée deux fois" % (nom, cid))
        else:
            ids.append(cid)
        nom = "capacite « %s »" % (cid or i)
        if not str(c.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        risque = c.get("risque")
        if risque not in RISQUES:
            e.append("%s.risque : %s" % (nom, " | ".join(RISQUES)))
            continue
        paliers = _liste_de_textes(c.get("paliers"), nom + ".paliers", e)
        for p in paliers:
            if p not in PALIERS:
                e.append("%s.paliers : « %s » inconnu (%s)" % (nom, p, " | ".join(PALIERS)))
        for q in _liste_de_textes(c.get("qui"), nom + ".qui", e):
            if q not in ACTEURS:
                e.append("%s.qui : « %s » inconnu (%s)" % (nom, q, " | ".join(ACTEURS)))
        if risque != "lecture":
            if not _liste_de_textes(c.get("perimetre"), nom + ".perimetre", e):
                e.append("%s : une capacité qui écrit doit déclarer son périmètre" % nom)
            if not str(c.get("preuve", "")).strip():
                e.append("%s : une capacité qui écrit doit déclarer sa preuve (contrôle après coup)" % nom)
            if not str(c.get("retour", "")).strip():
                e.append("%s : une capacité qui écrit doit déclarer son retour arrière" % nom)
        _droit_ok(c.get("droit"), nom)
        _liste_de_textes(c.get("masque"), nom + ".masque", e)
        if risque == "eleve" and "maitre" in paliers:
            e.append("%s : une capacité de risque élevé ne peut pas atteindre le palier « maitre »" % nom)

    for i, d in enumerate(brut.get("detecteurs", []) or []):
        nom = "detecteurs[%d]" % i
        if not isinstance(d, dict) or not _ID.match(str(d.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if not isinstance(d.get("frequence_s"), int) or d["frequence_s"] < 10:
            e.append("%s.frequence_s : entier d'au moins 10 secondes" % nom)
        if d.get("capacite") and d["capacite"] not in ids:
            e.append("%s.capacite : « %s » n'est pas une capacité de ce module" % (nom, d["capacite"]))

    mids = []
    for i, mo in enumerate(brut.get("moteurs", []) or []):
        nom = "moteurs[%d]" % i
        if not isinstance(mo, dict) or not _ID.match(str(mo.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if "asynchrone" in mo and (not isinstance(mo["asynchrone"], bool) or mo.get("mode") != "evenement"):
            e.append("%s.asynchrone : vrai ou faux, et seulement pour un moteur sur événement" % nom)
        if mo["id"] in mids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, mo["id"]))
        mids.append(mo["id"])
        nom = "moteur « %s »" % mo["id"]
        if not str(mo.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        mode = mo.get("mode")
        if mode not in MODES_MOTEUR:
            e.append("%s.mode : %s" % (nom, " | ".join(MODES_MOTEUR)))
        elif mode == "periodique" and (not isinstance(mo.get("toutes_les_s"), int) or mo["toutes_les_s"] < 10):
            e.append("%s.toutes_les_s : entier d'au moins 10 secondes" % nom)
        elif mode == "evenement":
            sur = mo.get("sur")
            liste = [sur] if isinstance(sur, str) else (sur if isinstance(sur, list) else [])
            if not liste:
                e.append("%s.sur : un type d'événement, ou une liste, est attendu" % nom)
            for x in liste:
                if x not in ecoute and x not in emet:
                    e.append("%s.sur : « %s » doit figurer dans evenements.ecoute, ou être émis par ce module (un moteur n'écoute que ce que son module a déclaré)" % (nom, x))
        d = mo.get("duree_max_s", 60)
        if not isinstance(d, int) or not 1 <= d <= 3600:
            e.append("%s.duree_max_s : entier entre 1 et 3600" % nom)

    ecrans_ids = []
    for i, s in enumerate(brut.get("ecrans", []) or []):
        if not isinstance(s, dict) or not _ID.match(str(s.get("id", ""))) or not str(s.get("libelle", "")).strip():
            e.append("ecrans[%d] : « id » et « libelle » obligatoires" % i)
        else:
            ecrans_ids.append(s["id"])
            if s.get("gabarit", "libre") not in GABARITS:
                e.append("ecrans[%d].gabarit : %s" % (i, " | ".join(GABARITS)))

    lectures = [c.get("id") for c in (brut.get("capacites", []) or []) if isinstance(c, dict) and c.get("risque") == "lecture"]
    wids = []
    for i, w in enumerate(brut.get("widgets", []) or []):
        nom = "widgets[%d]" % i
        if not isinstance(w, dict) or not _ID.match(str(w.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if w["id"] in wids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, w["id"]))
        wids.append(w["id"])
        nom = "widget « %s »" % w["id"]
        _droit_ok(w.get("droit"), nom)
        if not str(w.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        if w.get("ecran", "accueil") != "accueil" and w.get("ecran") not in ecrans_ids:
            e.append("%s.ecran : « accueil » ou un écran de ce module ([[ecrans]])" % nom)
        for champ, valides in (("zone", ZONES), ("taille", TAILLES), ("composant", COMPOSANTS), ("role", ROLES_MENU)):
            if w.get(champ, valides[0] if champ != "zone" else "principal") not in valides and champ in w:
                e.append("%s.%s : %s" % (nom, champ, " | ".join(valides)))
        o = w.get("ordre", 100)
        if not isinstance(o, int) or isinstance(o, bool) or not 0 <= o <= 9999:
            e.append("%s.ordre : entier entre 0 et 9999" % nom)
        if w.get("source") and w["source"] not in lectures:
            e.append("%s.source : « %s » doit être une capacité de LECTURE de ce module" % (nom, w["source"]))
        r = w.get("rafraichir_s", 0)
        if not isinstance(r, int) or isinstance(r, bool) or not (r == 0 or 5 <= r <= 86400):
            e.append("%s.rafraichir_s : 0, ou entre 5 et 86400 secondes" % nom)
    th = brut.get("theme", {}) or {}
    if not isinstance(th, dict):
        e.append("theme : une table est attendue")
        th = {}
    if th.get("accent") and not _COULEUR.match(str(th["accent"])):
        e.append("theme.accent : une couleur #rrggbb")
    for k, v in (th.get("tokens", {}) or {}).items() if isinstance(th.get("tokens", {}), dict) else []:
        if not re.match(r"^[a-z][a-z0-9_-]{0,30}$", str(k)):
            e.append("theme.tokens : le nom « %s » n'est pas valide (minuscules, chiffres, - et _)" % k)
        if not _VALEUR_THEME.match(str(v)):
            e.append("theme.tokens.%s : « %s » n'est ni une couleur ni une dimension" % (k, v))

    menus = [x for x in (brut.get("menus", []) or []) if isinstance(x, dict)]
    menu_ids, parents = [], {}
    for i, mn in enumerate(brut.get("menus", []) or []):
        nom = "menus[%d]" % i
        if not isinstance(mn, dict) or not _ID.match(str(mn.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if mn["id"] in menu_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, mn["id"]))
        menu_ids.append(mn["id"])
        nom = "menu « %s »" % mn["id"]
        _droit_ok(mn.get("droit"), nom)
        if not str(mn.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        if mn.get("ecran") and mn["ecran"] not in ecrans_ids:
            e.append("%s.ecran : « %s » n'est pas un écran de ce module ([[ecrans]])" % (nom, mn["ecran"]))
        if mn.get("role", "utilisateur") not in ROLES_MENU:
            e.append("%s.role : %s" % (nom, " | ".join(ROLES_MENU)))
        if mn.get("badge", "") not in BADGES_MENU:
            e.append("%s.badge : %s" % (nom, " | ".join(x or "(aucun)" for x in BADGES_MENU)))
        o = mn.get("ordre", 100)
        if not isinstance(o, int) or isinstance(o, bool) or not 0 <= o <= 9999:
            e.append("%s.ordre : entier entre 0 et 9999" % nom)
        if mn.get("zone", "principal") not in ZONES_MENU:
            e.append("%s.zone : %s" % (nom, " | ".join(ZONES_MENU)))
        g = mn.get("groupe", "")
        if g and not re.match(r"^[a-z][a-z0-9_]*$", str(g)):
            e.append("%s.groupe : un identifiant (minuscules, chiffres, _), ou vide pour laisser l'affichage ranger" % nom)
        p = mn.get("parent", "")
        if p and not re.match(r"^[a-z][a-z0-9_]*(:[a-z][a-z0-9_]*)?$", str(p)):
            e.append("%s.parent : un menu de ce module, ou « module:menu »" % nom)
        parents[mn["id"]] = p
    for mid_, p in parents.items():
        if p and ":" not in p and p not in menu_ids:
            e.append("menu « %s ».parent : « %s » n'est pas un menu de ce module" % (mid_, p))
    for depart in menu_ids:                          # un menu ne peut pas être son propre ancêtre
        vu, cur = set(), depart
        while cur and ":" not in str(cur) and cur in parents:
            if cur in vu:
                e.append("menu « %s » : boucle de parents" % depart)
                break
            vu.add(cur)
            cur = parents[cur]

    pe_ids = []
    for i, px in enumerate(brut.get("points_extension", []) or []):
        nom = "points_extension[%d]" % i
        if not isinstance(px, dict) or not _ID.match(str(px.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if px["id"] in pe_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, px["id"]))
        pe_ids.append(px["id"])
        if not str(px.get("libelle", "")).strip():
            e.append("point d'extension « %s » : libellé obligatoire" % px["id"])
        _liste_de_textes(px.get("attend", []), "point d'extension « %s ».attend" % px["id"], e, _ID)
    contrib_ids = []
    for i, ct in enumerate(brut.get("contributions", []) or []):
        nom = "contributions[%d]" % i
        if not isinstance(ct, dict) or not _ID.match(str(ct.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        cle = (str(ct.get("point", "")), ct["id"])
        if cle in contrib_ids:
            e.append("%s : « %s » est déclarée deux fois sur « %s »" % (nom, ct["id"], cle[0]))
        contrib_ids.append(cle)
        if not re.match(r"^[a-z][a-z0-9_]{1,40}:[a-z][a-z0-9_]{1,40}$", cle[0]):
            e.append("%s.point : « module:point » attendu" % nom)
        if not str(ct.get("libelle", "")).strip():
            e.append("contribution « %s » : libellé obligatoire" % ct["id"])
        d = ct.get("donnees", {})
        if not isinstance(d, dict) or any(not isinstance(v, (str, int, float, bool)) for v in d.values()):
            e.append("contribution « %s ».donnees : des clés et des valeurs simples (texte, nombre, booléen)" % ct["id"])
    onglet_ids = []
    for i, og in enumerate(brut.get("onglets", []) or []):
        nom = "onglets[%d]" % i
        if not isinstance(og, dict) or not _ID.match(str(og.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if og["id"] in onglet_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, og["id"]))
        onglet_ids.append(og["id"])
        nom = "onglet « %s »" % og["id"]
        _droit_ok(og.get("droit"), nom)
        if not str(og.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        if not re.match(r"^[a-z][a-z0-9_]*(:[a-z][a-z0-9_]*)?$", str(og.get("objet", ""))):
            e.append("%s.objet : un type d'objet (« note »), ou « module:type »" % nom)
        if og.get("ecran") and og["ecran"] not in ecrans_ids:
            e.append("%s.ecran : « %s » n'est pas un écran de ce module ([[ecrans]])" % (nom, og["ecran"]))
        if og.get("role", "utilisateur") not in ROLES_MENU:
            e.append("%s.role : %s" % (nom, " | ".join(ROLES_MENU)))
        o = og.get("ordre", 100)
        if not isinstance(o, int) or isinstance(o, bool) or not 0 <= o <= 9999:
            e.append("%s.ordre : entier entre 0 et 9999" % nom)
    hab_ids = []
    for i, hb in enumerate(brut.get("habillages", []) or []):
        nom = "habillages[%d]" % i
        if not isinstance(hb, dict) or not _ID.match(str(hb.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if hb["id"] in hab_ids or hb["id"] in BASES_HABILLAGE:
            e.append("%s.id : « %s » est déjà pris (déclaré deux fois, ou thème de base)" % (nom, hb["id"]))
        hab_ids.append(hb["id"])
        nom = "habillage « %s »" % hb["id"]
        if not str(hb.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        if hb.get("base", "clair") not in BASES_HABILLAGE:
            e.append("%s.base : %s" % (nom, " | ".join(BASES_HABILLAGE)))
        f = hb.get("fichier", "")
        if not f or not isinstance(f, str) or f.startswith("/") or ".." in f.split("/") or not f.endswith(".css"):
            e.append("%s.fichier : un chemin relatif au dossier du module, en .css, sans « .. »" % nom)

    sig_ids = []
    for i, sg in enumerate(brut.get("signaux", []) or []):
        nom = "signaux[%d]" % i
        if not isinstance(sg, dict) or not _ID.match(str(sg.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if sg["id"] in sig_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, sg["id"]))
        sig_ids.append(sg["id"])
        nom = "signal « %s »" % sg["id"]
        if not str(sg.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        if sg.get("capacite") not in lectures:
            e.append("%s.capacite : « %s » doit être une capacité de LECTURE de ce module" % (nom, sg.get("capacite")))
        if not isinstance(sg.get("admin", False), bool):
            e.append("%s.admin : vrai ou faux" % nom)
        c = sg.get("cadence_s", 0)
        if not isinstance(c, int) or isinstance(c, bool) or not 0 <= c <= 86400:
            e.append("%s.cadence_s : entier entre 0 et 86400" % nom)

    mes_ids = []
    for i, ms in enumerate(brut.get("mesures", []) or []):
        nom = "mesures[%d]" % i
        if not isinstance(ms, dict) or not _ID.match(str(ms.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if ms["id"] in mes_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, ms["id"]))
        mes_ids.append(ms["id"])
        nom = "mesure « %s »" % ms["id"]
        if not str(ms.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        if ms.get("capacite") not in lectures:
            e.append("%s.capacite : « %s » doit être une capacité de LECTURE de ce module" % (nom, ms.get("capacite")))
        for champ, permis in (("genre", ("jauge", "compteur")), ("agregat", ("moy", "min", "max", "somme")), ("pire", ("haut", "bas")), ("nature", ("serie", "etat")),
                              ("vide", ("", "rien_a_signaler", "non_configuree", "jamais_utilisee"))):
            if ms.get(champ, permis[0]) not in permis:
                e.append("%s.%s : parmi %s" % (nom, champ, ", ".join(permis)))
        if not isinstance(ms.get("groupee", False), bool):
            e.append("%s.groupee : vrai ou faux" % nom)
        fr = ms.get("fraicheur_s", 0)
        if not isinstance(fr, int) or isinstance(fr, bool) or not 0 <= fr <= 604800:
            e.append("%s.fraicheur_s : entier entre 0 et 604800" % nom)
        pl = ms.get("plafond", 0)
        if not isinstance(pl, (int, float)) or isinstance(pl, bool) or pl < 0:
            e.append("%s.plafond : un nombre positif ou nul" % nom)

    pt_ids = []
    for i, pt in enumerate(brut.get("points_evolution", []) or []):
        nom = "points_evolution[%d]" % i
        if not isinstance(pt, dict) or not _ID_POINT.match(str(pt.get("id", ""))):
            e.append("%s.id : identifiant invalide (minuscules, éventuellement « module.point »)" % nom)
            continue
        if pt["id"] in pt_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, pt["id"]))
        pt_ids.append(pt["id"])
        nom = "point d'évolution « %s »" % pt["id"]
        if not str(pt.get("libelle", "")).strip():
            e.append("%s : libellé obligatoire" % nom)
        if not _CONTRAT.match(str(pt.get("contrat", ""))):
            e.append("%s.contrat : « majeure.mineure », ex. 1.0" % nom)
        ref = pt.get("reference", "")
        if not isinstance(ref, str) or not ref or ref.startswith("/") or ".." in ref.split("/"):
            e.append("%s.reference : chemin relatif au dossier du module, sans « .. », sans extension" % nom)
        if pt.get("fonction", "") and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(pt.get("fonction"))):
            e.append("%s.fonction : un nom de fonction" % nom)
        if not re.match(r"^[a-z][a-z0-9_]*$", str(pt.get("runtime", "python"))):
            e.append("%s.runtime : un nom d'environnement d'exécution (python, wasm, node, php…)" % nom)
        dl = pt.get("delai_ms", 2000)
        if not isinstance(dl, int) or isinstance(dl, bool) or not 1 <= dl <= 600000:
            e.append("%s.delai_ms : entier entre 1 et 600000" % nom)
        if pt.get("mesure") and pt["mesure"] not in mes_ids:
            e.append("%s.mesure : « %s » doit être une mesure déclarée par ce module ([[mesures]])" % (nom, pt["mesure"]))

    racine_ids = []
    for i, rc in enumerate(brut.get("racine", []) or []):
        nom = "racine[%d]" % i
        if not isinstance(rc, dict) or not _ID.match(str(rc.get("id", ""))):
            e.append("%s.id : identifiant invalide" % nom)
            continue
        if rc["id"] in racine_ids:
            e.append("%s.id : « %s » est déclaré deux fois" % (nom, rc["id"]))
        racine_ids.append(rc["id"])
        if not str(rc.get("libelle", "")).strip():
            e.append("racine « %s » : libellé obligatoire" % rc["id"])
        if not isinstance(rc.get("lecture", False), bool):
            e.append("racine « %s ».lecture : vrai ou faux" % rc["id"])
    if racine_ids and not (brut.get("permissions") or {}).get("racine"):
        e.append("racine : des commandes sont déclarées, mais [permissions] racine = true manque (un module dit qu'il demande du root)")
    if (brut.get("permissions") or {}).get("racine") and not racine_ids:
        e.append("permissions.racine : aucune commande n'est déclarée ([[racine]])")

    ins = brut.get("installation", {}) or {}
    for champ in ("script", "verification", "retrait", "migrations"):
        v = ins.get(champ, "")
        if v and (not isinstance(v, str) or v.startswith("/") or ".." in v.split("/")):
            e.append("installation.%s : chemin relatif au dossier du module, sans « .. »" % champ)
    if ins.get("script") and not ins.get("verification"):
        e.append("installation : un script d'installation exige une vérification (preuve que le module fonctionne)")
    if ins.get("script") and not ins.get("retrait"):
        e.append("installation : un script d'installation exige un script de retrait")
    return e


def _valider_sections(bruts) -> list:
    """Les [[sections]] qu'un module apporte : un identifiant, un nom lisible, une icône (clé ou tracé), un ordre."""
    if not bruts:
        return []
    if not isinstance(bruts, list):
        return ["sections : une liste de tables ([[sections]])"]
    e, vus = [], set()
    if len(bruts) > 5:
        e.append("sections : cinq au plus par module")
    for i, d in enumerate(bruts):
        nom = "sections[%d]" % i
        if not isinstance(d, dict):
            e.append("%s : une table" % nom)
            continue
        ident = d.get("id", "")
        if not isinstance(ident, str) or not SECTION_ID.match(ident):
            e.append("%s.id : minuscules, chiffres et _ (2 à 31 caractères, commence par une lettre)" % nom)
        elif ident in vus:
            e.append("%s.id : « %s » déclarée deux fois" % (nom, ident))
        vus.add(ident)
        if not isinstance(d.get("libelle"), str) or not d["libelle"].strip() or len(d["libelle"]) > 40:
            e.append("%s.libelle : un nom de 40 caractères au plus" % nom)
        if "icone" in d and (not isinstance(d["icone"], str) or not SECTION_ICONE.match(d["icone"])):
            e.append("%s.icone : une clé d'icône (lettres minuscules, chiffres, _)" % nom)
        if "icone_trace" in d and not trace_valide(d["icone_trace"]):
            e.append("%s.icone_trace : un tracé de path seulement (commandes M L H V C S Q T A Z, nombres, espaces, virgules ; 800 caractères au plus)" % nom)
        if "ordre" in d and (isinstance(d["ordre"], bool) or not isinstance(d["ordre"], int) or not 1 <= d["ordre"] <= 899):
            e.append("%s.ordre : un entier de 1 à 899" % nom)
        for k in d:
            if k not in ("id", "libelle", "icone", "icone_trace", "ordre"):
                e.append("%s : champ inconnu « %s »" % (nom, k))
    return e


def _qualifier(module: str, droit) -> str:
    """« lire » dans le module « dns » devient « dns.lire » ; « autre.lire » reste tel quel ; vide reste vide."""
    if not droit:
        return ""
    return droit if "." in droit else "%s.%s" % (module, droit)


def construire(brut: dict, source="") -> Manifeste:
    erreurs = valider(brut)
    if erreurs:
        raise ManifesteInvalide(erreurs, source)
    m = brut["module"]
    ev = brut.get("evenements", {}) or {}
    ins = brut.get("installation", {}) or {}
    caps = tuple(Capacite(
        id=c["id"], libelle=c["libelle"], risque=c["risque"],
        perimetre=tuple(c.get("perimetre", ())), preuve=str(c.get("preuve", "")).strip(), retour=str(c.get("retour", "")).strip(),
        paliers=tuple(c.get("paliers", ("raconter",))), qui=tuple(c.get("qui", ("cassandra", "itare", "humain", "agent"))),
        droit=_qualifier(m["id"], c.get("droit")), masque=tuple(c.get("masque", ())), externe=bool(c.get("externe", False)), sortant=bool(c.get("sortant", False)),
    ) for c in brut.get("capacites", []) or [])
    return Manifeste(
        id=m["id"], nom=m["nom"], version=m["version"], noyau_min=m["noyau_min"], description=m["description"].strip(),
        confiance=m.get("confiance", "interne"), requiert=tuple(lire_requis(x)[0] for x in m.get("requiert", ())),
        contraintes=tuple(lire_requis(x) for x in m.get("requiert", ()) if lire_requis(x)[1]),
        conflits=tuple(m.get("conflits", ())), suggere=tuple(m.get("suggere", ())), fournit=tuple(m.get("fournit", ())),
        essentiel=bool(m.get("essentiel", False)), instance=bool(m.get("instance", False)), famille=str(m.get("section") or m.get("famille", "")),
        sections=tuple(Section(d["id"], d["libelle"].strip(), str(d.get("icone", "")), str(d.get("icone_trace", "")), int(d.get("ordre", 500)), m["id"]) for d in (brut.get("sections") or [])),
        famille_libelle=str(m.get("famille_libelle", "")).strip(), famille_icone=str(m.get("famille_icone", "")),
        icone_trace=str(m.get("icone_trace", "")), famille_icone_trace=str(m.get("famille_icone_trace", "")),
        importance=str(m.get("importance", "vital" if m.get("essentiel") else "")), sans=str(m.get("sans", "")).strip(),
        auteur=str(m.get("auteur", "")), licence=str(m.get("licence", "")), site=str(m.get("site", "")), api=str(m.get("api", "1")),
        permissions=Permissions(bool((brut.get("permissions") or {}).get("espace_utilisateur", False)),
                                tuple((brut.get("permissions") or {}).get("reseau", ())),
                                tuple((brut.get("permissions") or {}).get("ecritures", ())),
                                tuple((brut.get("permissions") or {}).get("privileges", ())),
                                bool((brut.get("permissions") or {}).get("introspection", False)),
                                bool((brut.get("permissions") or {}).get("lectures", False)),
                                bool((brut.get("permissions") or {}).get("droits", False)),
                                bool((brut.get("permissions") or {}).get("identite", False)),
                                bool((brut.get("permissions") or {}).get("reglages", False)),
                                bool((brut.get("permissions") or {}).get("stockage", False)),
                                bool((brut.get("permissions") or {}).get("stockage_lecture", False)),
                                bool((brut.get("permissions") or {}).get("secrets", False)),
                                bool((brut.get("permissions") or {}).get("racine", False)),
                                bool((brut.get("permissions") or {}).get("agir", False)),
                                bool((brut.get("permissions") or {}).get("modules", False)),
                                bool((brut.get("permissions") or {}).get("urgence", False)),
                                bool((brut.get("permissions") or {}).get("evolution", False)),
                                bool((brut.get("permissions") or {}).get("stockage_par_societe", False))),
        droits=tuple(Droit(d["id"], d["libelle"], bool(d.get("defaut", False)), bool(d.get("sensible", False))) for d in brut.get("droits", []) or []),
        reglages=tuple(Reglage(r["id"], r["libelle"], r.get("type", "texte"),
                               r.get("defaut", False if r.get("type") == "booleen" else (0 if r.get("type") == "entier" else "")),
                               tuple(r.get("choix", ())), r.get("portee", "global"), r.get("minimum"), r.get("maximum"), str(r.get("aide", "")))
                       for r in brut.get("reglages", []) or []),
        objets=tuple(Objet(o["type"], o["libelle"]) for o in brut.get("objets", []) or []),
        emet=tuple(ev.get("emet", ())), ecoute=tuple(ev.get("ecoute", ())), capacites=caps,
        detecteurs=tuple(Detecteur(d["id"], d.get("libelle", d["id"]), d["frequence_s"], d.get("capacite", "")) for d in brut.get("detecteurs", []) or []),
        moteurs=tuple(Moteur(m["id"], m["libelle"], m["mode"], m.get("toutes_les_s", 0),
                             tuple([m["sur"]] if isinstance(m.get("sur"), str) else (m.get("sur") or ())), m.get("duree_max_s", 60), bool(m.get("asynchrone", False)))
                      for m in brut.get("moteurs", []) or []),
        menus=tuple(Menu(x["id"], x["libelle"], x.get("ecran", ""), x.get("parent", ""), x.get("ordre", 100), x.get("role", "utilisateur"),
                         x.get("icone", ""), x.get("badge", ""), _qualifier(m["id"], x.get("droit")),
                         x.get("groupe", ""), x.get("zone", "principal")) for x in brut.get("menus", []) or []),
        points_extension=tuple(PointExtension(x["id"], x["libelle"], tuple(x.get("attend", ()))) for x in brut.get("points_extension", []) or []),
        contributions=tuple(Contribution(x["point"], x["id"], x["libelle"], tuple(sorted((x.get("donnees") or {}).items()))) for x in brut.get("contributions", []) or []),
        onglets=tuple(Onglet(x["id"], x["libelle"], x["objet"], x.get("ecran", ""), x.get("ordre", 100), x.get("role", "utilisateur"), x.get("icone", ""), _qualifier(m["id"], x.get("droit")))
                      for x in brut.get("onglets", []) or []),
        mesures=tuple(Mesure(x["id"], x["libelle"], x["capacite"], x.get("genre", "jauge"), x.get("unite", ""), x.get("famille", ""), x.get("agregat", "moy"), bool(x.get("groupee", False)),
                             x.get("pire", "haut"), float(x.get("plafond", 0) or 0), x.get("nature", "serie"), int(x.get("fraicheur_s", 0) or 0), x.get("vide", ""), x.get("description", ""))
                      for x in brut.get("mesures", []) or []),
        points_evolution=tuple(PointEvolution(x["id"], x["libelle"], str(x["contrat"]), x["reference"], x.get("fonction", "") or x["id"].split(".")[-1], x.get("runtime", "python"),
                                              x.get("mesure", ""), int(x.get("delai_ms", 2000))) for x in brut.get("points_evolution", []) or []),
        signaux=tuple(Signal(x["id"], x["libelle"], x["capacite"], bool(x.get("admin", False)), x.get("cadence_s", 0)) for x in brut.get("signaux", []) or []),
        racine=tuple(CommandeRacine(x["id"], x["libelle"], bool(x.get("lecture", False))) for x in brut.get("racine", []) or []),
        habillages=tuple(Habillage(x["id"], x["libelle"], x.get("base", "clair"), x.get("fichier", "")) for x in brut.get("habillages", []) or []),
        widgets=tuple(Widget(w["id"], w["libelle"], w.get("ecran", "accueil"), w.get("zone", "principal"), w.get("taille", "m"), w.get("ordre", 100),
                             w.get("role", "utilisateur"), w.get("composant", "nombre"), w.get("source", ""), w.get("rafraichir_s", 0), _qualifier(m["id"], w.get("droit")))
                      for w in brut.get("widgets", []) or []),
        theme=Theme(str((brut.get("theme") or {}).get("accent", "")), tuple(sorted(((brut.get("theme") or {}).get("tokens") or {}).items()))),
        ecrans=tuple(Ecran(s["id"], s["libelle"], s.get("domaine", ""), s.get("gabarit", "libre"), s.get("titre", "")) for s in brut.get("ecrans", []) or []),
        installation=Installation(ins.get("script", ""), ins.get("verification", ""), ins.get("retrait", ""), ins.get("migrations", "")),
        source=str(source),
    )


def charger(chemin) -> Manifeste:
    p = Path(chemin)
    try:
        with open(p, "rb") as f:
            brut = tomllib.load(f)
    except tomllib.TOMLDecodeError as ex:
        raise ManifesteInvalide(["TOML illisible : %s" % ex], p) from ex
    return construire(brut, p)


def decouvrir(dossier_modules) -> list:
    """Charge tous les modules/<id>/CN_manifeste.toml. Un manifeste invalide est signalé, jamais ignoré."""
    base = Path(dossier_modules)
    sortie, erreurs = [], []
    for p in sorted(base.glob("*/CN_manifeste.toml")):
        try:
            m = charger(p)
        except ManifesteInvalide as ex:
            erreurs.append(str(ex))
            continue
        if m.id != p.parent.name:
            erreurs.append("%s : module.id « %s » différent du dossier « %s »" % (p, m.id, p.parent.name))
            continue
        absents = [f for f in (m.installation.script, m.installation.verification, m.installation.retrait, m.installation.migrations)
                   if f and not (p.parent / f).exists()]
        if absents:
            erreurs.append("%s : fichier(s) déclaré(s) mais absent(s) : %s" % (p, ", ".join(absents)))
            continue
        sortie.append(m)
    if erreurs:
        raise ManifesteInvalide(erreurs, base)
    return sortie


def fournisseurs(manifestes) -> dict:
    """{nom de service : [modules qui le fournissent]}, triés."""
    f = {}
    for m in manifestes:
        for nom in m.fournit:
            f.setdefault(nom, []).append(m.id)
    return {k: sorted(v) for k, v in f.items()}


def requis_reels(m, par_id, four=None) -> list:
    """Les modules CONCRETS dont `m` dépend : un requis qui est un id de module reste cet id ; sinon c'est un nom de service, rendu par le premier fournisseur (par ordre alphabétique) ;
    sans fournisseur, le nom reste tel quel (il sera dit absent)."""
    four = four if four is not None else {}
    return [r if r in par_id else (four.get(r) or [r])[0] for r in m.requiert]


def verifier_ensemble(manifestes) -> list:
    """Défauts qui ne se voient qu'à plusieurs : doublons, dépendances absentes, événements sans émetteur."""
    e = []
    par_id = {}
    for m in manifestes:
        if m.id in par_id:
            e.append("module « %s » présent deux fois" % m.id)
        par_id[m.id] = m
    proprietaire = {}
    for m in manifestes:
        for o in m.objets:
            if o.type in proprietaire and proprietaire[o.type] != m.id:
                e.append("le type d'objet « %s » est revendiqué par « %s » et « %s »" % (o.type, proprietaire[o.type], m.id))
            proprietaire[o.type] = m.id
    emis = {x for m in manifestes for x in m.emet}
    four = fournisseurs(manifestes)
    for m in manifestes:
        for ct in m.contributions:
            cible, _, point = ct.point.partition(":")
            if cible in par_id:
                px = next((x for x in par_id[cible].points_extension if x.id == point), None)
                if px is None:
                    e.append("« %s » contribue à « %s », qui n'offre pas ce point d'extension" % (m.id, ct.point))
                else:
                    cles = {k for k, _ in ct.donnees}
                    manque = [k for k in px.attend if k not in cles]
                    if manque:
                        e.append("« %s » : la contribution « %s » à « %s » doit porter : %s" % (m.id, ct.id, ct.point, ", ".join(manque)))
    for m in manifestes:
        for r in m.requiert:
            if r not in par_id and r not in four:
                e.append("« %s » requiert « %s », qui n'est pas installé" % (m.id, r))
        for r, contrainte in m.contraintes:
            if r in par_id and not satisfait(par_id[r].version, contrainte):
                e.append("« %s » requiert « %s %s » mais la version installée est %s" % (m.id, r, contrainte, par_id[r].version))
        for x in m.ecoute:
            if x not in emis and not x.startswith(EVENEMENTS_DU_NOYAU):
                e.append("« %s » écoute « %s », qu'aucun module n'émet" % (m.id, x))
    return e


def avec_dependances(manifestes, ids) -> list:
    """Les modules demandés ET tout ce dont ils dépendent, dans l'ordre d'installation."""
    par_id = {m.id: m for m in manifestes}
    inconnus = sorted(i for i in ids if i not in par_id)
    if inconnus:
        raise ManifesteInvalide(["module inconnu : " + ", ".join(inconnus)])
    four = fournisseurs(manifestes)
    voulus, pile = set(), list(ids)
    while pile:
        i = pile.pop()
        if i in voulus:
            continue
        voulus.add(i)
        pile.extend(x for x in requis_reels(par_id[i], par_id, four) if x in par_id)
    return ordre_installation([m for m in manifestes if m.id in voulus])


def ordre_installation(manifestes) -> list:
    """Ordre d'installation par dépendances (les requis d'abord), déterministe. Refuse un cycle."""
    par_id = {m.id: m for m in manifestes}
    four = fournisseurs(manifestes)
    reels = {m.id: requis_reels(m, par_id, four) for m in manifestes}
    manque = sorted({"%s→%s" % (m.id, r) for m in manifestes for r in reels[m.id] if r not in par_id})
    if manque:
        raise ManifesteInvalide(["dépendance absente : " + x for x in manque])
    restant = {m.id: set(reels[m.id]) for m in manifestes}
    ordre = []
    while restant:
        prets = sorted(i for i, d in restant.items() if not d)
        if not prets:
            raise ManifesteInvalide(["cycle de dépendances entre : " + ", ".join(sorted(restant))])
        for i in prets:
            ordre.append(i)
            del restant[i]
        for d in restant.values():
            d.difference_update(prets)
    return ordre
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : ManifesteInvalide, Objet, Capacite, Droit, Reglage, Detecteur, Moteur, Menu …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
