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

RISQUES = ("lecture", "faible", "moyen", "eleve")
PALIERS = ("raconter", "auto", "maitre")
ACTEURS = ("cassandra", "itare", "humain", "compte")
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
    qui: tuple = ("cassandra", "itare", "humain")

    @property
    def ecrit(self) -> bool:
        return self.risque != "lecture"


@dataclass(frozen=True)
class Detecteur:
    id: str
    libelle: str
    frequence_s: int
    capacite: str = ""


@dataclass(frozen=True)
class Ecran:
    id: str
    libelle: str
    domaine: str = ""


@dataclass(frozen=True)
class Installation:
    script: str = ""
    verification: str = ""
    retrait: str = ""
    migrations: str = ""


@dataclass(frozen=True)
class Manifeste:
    id: str
    nom: str
    version: str
    noyau_min: str
    description: str
    confiance: str
    requiert: tuple = ()
    objets: tuple = ()
    emet: tuple = ()
    ecoute: tuple = ()
    capacites: tuple = ()
    detecteurs: tuple = ()
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

    for i, s in enumerate(brut.get("ecrans", []) or []):
        if not isinstance(s, dict) or not _ID.match(str(s.get("id", ""))) or not str(s.get("libelle", "")).strip():
            e.append("ecrans[%d] : « id » et « libelle » obligatoires" % i)

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
        paliers=tuple(c.get("paliers", ("raconter",))), qui=tuple(c.get("qui", ("cassandra", "itare", "humain"))),
    ) for c in brut.get("capacites", []) or [])
    return Manifeste(
        id=m["id"], nom=m["nom"], version=m["version"], noyau_min=m["noyau_min"], description=m["description"].strip(),
        confiance=m.get("confiance", "interne"), requiert=tuple(m.get("requiert", ())),
        objets=tuple(Objet(o["type"], o["libelle"]) for o in brut.get("objets", []) or []),
        emet=tuple(ev.get("emet", ())), ecoute=tuple(ev.get("ecoute", ())), capacites=caps,
        detecteurs=tuple(Detecteur(d["id"], d.get("libelle", d["id"]), d["frequence_s"], d.get("capacite", "")) for d in brut.get("detecteurs", []) or []),
        ecrans=tuple(Ecran(s["id"], s["libelle"], s.get("domaine", "")) for s in brut.get("ecrans", []) or []),
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
            if x not in emis:
                e.append("« %s » écoute « %s », qu'aucun module n'émet" % (m.id, x))
    return e


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
