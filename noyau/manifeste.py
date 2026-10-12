"""Le manifeste : le contrat qu'un module signe pour se brancher sur le noyau.

Un module n'existe pour le noyau que par son manifeste (manifeste.toml). Le noyau le lit,
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

VERSION_NOYAU = "0.1.0"
API_NOYAU = "1.0"     # le contrat offert aux modules (ctx, manifeste). Sa version MAJEURE change quand on casse la compatibilité.

RISQUES = ("lecture", "faible", "moyen", "eleve")
PALIERS = ("raconter", "auto", "maitre")
ACTEURS = ("cassandra", "itare", "humain", "compte", "agent", "anonyme")
MODES_MOTEUR = ("periodique", "evenement", "demande")
ROLES_MENU = ("utilisateur", "admin")
GABARITS = ("tableau", "liste_detail", "libre")                  # comment l'interface compose un écran
ZONES = ("entete", "principal", "lateral")
TAILLES = ("s", "m", "l")
COMPOSANTS = ("nombre", "jauge", "liste", "etat", "serie", "texte")   # ce que l'interface sait dessiner pour une tuile
_COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")
_VALEUR_THEME = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([0-9., %]+\)|\d+(\.\d+)?(px|rem|em|%))$")
BADGES_MENU = ("", "constats", "moteurs")
# Les événements du noyau lui-même : un module peut les écouter sans qu'aucun module ne les « émette ».
EVENEMENTS_DU_NOYAU = ("noyau.", "module.", "capacite.", "constat.", "objet.", "moteur.", "savoir.", "humain.")
TYPES_RESERVES = ("noyau", "module", "capacite", "constat", "objet", "moteur", "savoir", "humain")
CONFIANCES = ("interne", "signe", "tiers", "local")

_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
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

    @property
    def ecrit(self) -> bool:
        return self.risque != "lecture"

    @property
    def ecrit_sans_preuve(self) -> bool:
        """Une capacité publique qui écrit doit porter sa preuve (elle l'a déjà : le manifeste l'exige) ; ici, jamais d'élévation du risque « eleve »."""
        return self.risque == "eleve"


@dataclass(frozen=True)
class Droit:
    """Un droit qu'un module déclare (comme les « rights » d'un module Dolibarr). Qualifié « module.droit » partout ailleurs.
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
    portee: str = "global"     # global | compte (une valeur propre à chaque compte)
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
    secrets: bool = False              # peut chiffrer/déchiffrer des secrets pour SA base (ctx.chiffrer / ctx.dechiffrer) : clés d'API de modèles, jetons...


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
    famille: str = ""          # regroupement dans le menu des modules (« securite », « reseau »...)
    objets: tuple = ()
    droits: tuple = ()         # les droits que ce module déclare ([[droits]])
    reglages: tuple = ()       # les réglages que ce module déclare ([[reglages]])
    emet: tuple = ()
    ecoute: tuple = ()
    capacites: tuple = ()
    detecteurs: tuple = ()
    moteurs: tuple = ()
    menus: tuple = ()
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
    for champ in ("espace_utilisateur", "introspection", "lectures"):
        if champ in perm and not isinstance(perm[champ], bool):
            e.append("permissions.%s : vrai ou faux" % champ)
    for chemin in perm.get("ecritures", []) if isinstance(perm.get("ecritures"), list) else []:
        if not str(chemin).startswith("/") or ".." in str(chemin).split("/"):
            e.append("permissions.ecritures : « %s » doit être un chemin absolu sans « .. »" % chemin)
    if "essentiel" in m and not isinstance(m["essentiel"], bool):
        e.append("module.essentiel : vrai ou faux")
    if "famille" in m and (not isinstance(m["famille"], str) or len(m["famille"]) > 40):
        e.append("module.famille : un texte de 40 caractères au plus")
    requiert = _liste_de_textes(m.get("requiert"), "module.requiert", e, _ID)
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
        if r.get("portee", "global") not in ("global", "compte"):
            e.append("%s.portee : global | compte" % nom)
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
                if x not in ecoute:
                    e.append("%s.sur : « %s » doit figurer dans evenements.ecoute (un moteur n'écoute que ce que son module a déclaré)" % (nom, x))
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
        droit=_qualifier(m["id"], c.get("droit")), masque=tuple(c.get("masque", ())),
    ) for c in brut.get("capacites", []) or [])
    return Manifeste(
        id=m["id"], nom=m["nom"], version=m["version"], noyau_min=m["noyau_min"], description=m["description"].strip(),
        confiance=m.get("confiance", "interne"), requiert=tuple(m.get("requiert", ())),
        essentiel=bool(m.get("essentiel", False)), famille=str(m.get("famille", "")),
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
                                bool((brut.get("permissions") or {}).get("secrets", False))),
        droits=tuple(Droit(d["id"], d["libelle"], bool(d.get("defaut", False)), bool(d.get("sensible", False))) for d in brut.get("droits", []) or []),
        reglages=tuple(Reglage(r["id"], r["libelle"], r.get("type", "texte"),
                               r.get("defaut", False if r.get("type") == "booleen" else (0 if r.get("type") == "entier" else "")),
                               tuple(r.get("choix", ())), r.get("portee", "global"), r.get("minimum"), r.get("maximum"), str(r.get("aide", "")))
                       for r in brut.get("reglages", []) or []),
        objets=tuple(Objet(o["type"], o["libelle"]) for o in brut.get("objets", []) or []),
        emet=tuple(ev.get("emet", ())), ecoute=tuple(ev.get("ecoute", ())), capacites=caps,
        detecteurs=tuple(Detecteur(d["id"], d.get("libelle", d["id"]), d["frequence_s"], d.get("capacite", "")) for d in brut.get("detecteurs", []) or []),
        moteurs=tuple(Moteur(m["id"], m["libelle"], m["mode"], m.get("toutes_les_s", 0),
                             tuple([m["sur"]] if isinstance(m.get("sur"), str) else (m.get("sur") or ())), m.get("duree_max_s", 60))
                      for m in brut.get("moteurs", []) or []),
        menus=tuple(Menu(x["id"], x["libelle"], x.get("ecran", ""), x.get("parent", ""), x.get("ordre", 100), x.get("role", "utilisateur"),
                         x.get("icone", ""), x.get("badge", ""), _qualifier(m["id"], x.get("droit"))) for x in brut.get("menus", []) or []),
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
    """Charge tous les modules/<id>/manifeste.toml. Un manifeste invalide est signalé, jamais ignoré."""
    base = Path(dossier_modules)
    sortie, erreurs = [], []
    for p in sorted(base.glob("*/manifeste.toml")):
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
    for m in manifestes:
        for r in m.requiert:
            if r not in par_id:
                e.append("« %s » requiert « %s », qui n'est pas installé" % (m.id, r))
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
    voulus, pile = set(), list(ids)
    while pile:
        i = pile.pop()
        if i in voulus:
            continue
        voulus.add(i)
        pile.extend(par_id[i].requiert)
    return ordre_installation([m for m in manifestes if m.id in voulus])


def ordre_installation(manifestes) -> list:
    """Ordre d'installation par dépendances (les requis d'abord), déterministe. Refuse un cycle."""
    par_id = {m.id: m for m in manifestes}
    manque = sorted({"%s→%s" % (m.id, r) for m in manifestes for r in m.requiert if r not in par_id})
    if manque:
        raise ManifesteInvalide(["dépendance absente : " + x for x in manque])
    restant = {m.id: set(m.requiert) for m in manifestes}
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
