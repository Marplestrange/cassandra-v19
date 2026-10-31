# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le Relecteur et la sentinelle anti-fuite
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.4.0  #74d96c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le Relecteur : relit une réponse avant qu'elle parte et la retient si elle laisse échapper un secret connu (par son empreinte) ou porte un ordre caché.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.0 empreinte=74d96c ▼▼▼
"""Le Relecteur (un service agentique : ni mémoire propre, ni initiative) relit une réponse avant qu'elle parte.

La sentinelle anti-fuite compare chaque réponse aux EMPREINTES des secrets connus — jamais à leurs valeurs : le module ne garde que HMAC-SHA256(clé de l'instance, valeur) et la longueur.
Une empreinte ne permet pas de retrouver le secret ; elle permet seulement de reconnaître, dans un texte, un morceau qui est exactement ce secret.
Fonctions pures : la base et le tour de conversation les appellent, rien ici ne touche au disque.
"""
from __future__ import annotations

import hashlib
import hmac
import re

LONGUEUR_MIN = 8                                               # en dessous, un « secret » est un mot courant : l'empreinte ne distinguerait plus rien
SEPARATEURS = re.compile(r"""[\s"'`<>()\[\]{}|,;*]+""")
APRES_SIGNE = re.compile(r"[=:]")
ORDRES_CACHES = (
    re.compile(r"ignore[rz]?\s+(?:tes|toutes?\s+(?:tes|les)|les|vos)\s+(?:r[eè]gles|instructions|consignes)", re.I),
    re.compile(r"ignore\s+(?:all\s+|the\s+|your\s+)?(?:previous\s+|prior\s+)?(?:rules|instructions)", re.I),
    re.compile(r"oublie\s+(?:tout|tes\s+(?:r[eè]gles|instructions))", re.I),
    re.compile(r"(?:nouvelle|new)\s+(?:consigne|instruction)s?\s*(?:syst[eè]me|system)\s*:", re.I),
    re.compile(r"\bsystem\s*prompt\b.{0,40}\b(?:r[eé]v[eè]le|affiche|donne|print|reveal)", re.I),
)


def empreinte(cle: str, valeur: str) -> str:
    """L'empreinte d'un secret : HMAC-SHA256 sous la clé de l'instance. À sens unique."""
    return hmac.new(str(cle).encode("utf-8"), str(valeur).encode("utf-8"), hashlib.sha256).hexdigest()


def candidats(texte: str, longueurs) -> set:
    """Les morceaux d'un texte qui pourraient être un secret de l'une des `longueurs` connues : les mots entiers, ce qui suit un « = » ou un « : »,
    et les fenêtres de la bonne taille à l'intérieur d'un mot long (un secret collé à du texte). Rien d'autre n'est jamais calculé."""
    longueurs = {int(n) for n in longueurs if int(n) >= LONGUEUR_MIN}
    if not longueurs:
        return set()
    sortie = set()
    for mot in SEPARATEURS.split(str(texte or "")):
        mot = mot.strip(".!?")
        if len(mot) < LONGUEUR_MIN:
            continue
        morceaux = {mot} | {m for m in APRES_SIGNE.split(mot) if len(m) >= LONGUEUR_MIN}
        for m in morceaux:
            if len(m) in longueurs:
                sortie.add(m)
            for n in longueurs:
                if len(m) > n:
                    sortie.update(m[i:i + n] for i in range(len(m) - n + 1))
    return sortie


def index(lignes) -> dict:
    """Prépare la comparaison : `lignes` = [{empreinte, longueur, etiquette}] -> {'empreintes': {empreinte: étiquette}, 'longueurs': {longueurs}}."""
    return {"empreintes": {l["empreinte"]: l["etiquette"] for l in lignes}, "longueurs": {int(l["longueur"]) for l in lignes}}


def fuites(texte: str, cle: str, connus: dict) -> list:
    """Les ÉTIQUETTES des secrets connus (`connus` : le résultat de `index`) dont la valeur se trouve dans le texte. Ni valeur ni position ne sont rendues."""
    if not connus or not connus.get("empreintes"):
        return []
    trouves = set()
    for morceau in candidats(texte, connus["longueurs"]):
        e = empreinte(cle, morceau)
        if e in connus["empreintes"]:
            trouves.add(connus["empreintes"][e])
    return sorted(trouves)


def relire(texte: str, cle: str, connus: dict, regles: dict | None = None) -> dict:
    """Le verdict du Relecteur sur une réponse : {verdict: 'passe'|'retenue', motifs: [...], remarques: [...]}.
    Retenue : un secret connu s'y trouve (motif `secret:<étiquette>`) ou un ordre caché y est écrit (`ordre_cache`). Une remarque ne retient rien (`sans_source`)."""
    motifs, remarques = [], []
    for e in fuites(texte, cle, connus):
        motifs.append("secret:" + e)
    if any(p.search(texte or "") for p in ORDRES_CACHES):
        motifs.append("ordre_cache")
    regles = regles or {}
    for motif in regles.get("sans_source", ()):
        if re.search(motif, texte or "", re.I) and not re.search(r"\[M:\d+\]", texte or ""):
            remarques.append("sans_source")
            break
    return {"verdict": "retenue" if motifs else "passe", "motifs": motifs, "remarques": remarques}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : empreinte, candidats, fuites, index, relire
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
