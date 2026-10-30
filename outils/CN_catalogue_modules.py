# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le catalogue des modules (docs/CN_MODULES
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #91d768
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le catalogue des modules (docs/CN_MODULES.md), généré depuis leurs manifestes : un module de plus, une description changée, et le banc `CN_test_catalogue_modules` dit de relancer ce script. Usage : python outils/CN_catalogue_modules.py [--v
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=91d768 ▼▼▼
"""Le catalogue des modules (docs/CN_MODULES.md), généré depuis leurs manifestes : un module de plus, une description changée, et le banc
`CN_test_catalogue_modules` dit de relancer ce script. Usage : python outils/CN_catalogue_modules.py [--verifier]"""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_manifeste as manifeste  # noqa: E402

CIBLE = RACINE / "docs" / "CN_MODULES.md"
DEBUT, FIN = "▼▼▼ BORNE CN", "▲▲▲ FIN BORNE CN"
IMPORTANCE = {"vital": 0, "important": 1, "optionnel": 2}
FAMILLES = {"socle": "Socle", "securite": "Sécurité", "supervision": "Supervision", "hebergement": "Hébergement", "reseau": "Réseau", "systeme": "Système", "agents": "Agents",
            "communication": "Communication", "canaux": "Canaux", "echanges": "Échanges", "gestion": "Gestion", "finance": "Finance", "evolution": "Évolution"}
ORDRE = list(FAMILLES)                                         # l'ordre de lecture : le socle, la protection, le parc, les agents, le travail, l'argent, l'évolution


def premiere_phrase(texte, limite=170):
    t = " ".join(str(texte or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    p = m.group(1) if m else t
    if len(p) > limite:
        p = p[:limite].rsplit(" ", 1)[0] + "…"
    return p.replace("|", "/")


def modules():
    out = []
    for p in sorted((RACINE / "modules").glob("*/CN_manifeste.toml")):
        out.append(manifeste.charger(p))
    return out


def corps():
    ms = modules()
    lignes = ["# Les modules", "",
              "Ce catalogue est **généré** depuis les manifestes (`python outils/CN_catalogue_modules.py`) ; un banc vérifie qu'il est à jour. Chaque module est un dossier",
              "indépendant de `modules/` : son manifeste déclare ses droits, ses capacités, ses menus et ses permissions.", "",
              "- **vital** : ouvert dans toutes les sociétés, jamais désactivable ; **important** et **optionnel** : ouverts société par société.",
              "- **instance** : n'existe que dans la société principale (sécurité, observabilité, sauvegardes, gestion des modules…).",
              "- **base par société** : les données du module sont séparées société par société.", "",
              "%d modules." % len(ms), ""]
    par = {}
    for m in ms:
        par.setdefault(m.famille or "autres", []).append(m)
    for fam in sorted(par, key=lambda f: (ORDRE.index(f) if f in ORDRE else len(ORDRE), f)):
        lignes += ["## " + FAMILLES.get(fam, fam.capitalize()), "", "| Module | Importance | Ce qu'il fait |", "|---|---|---|"]
        for m in sorted(par[fam], key=lambda m: (IMPORTANCE.get(m.importance or "optionnel", 3), m.id)):
            marques = []
            if m.instance:
                marques.append("instance")
            if m.permissions.stockage_par_societe:
                marques.append("base par société")
            imp = (m.importance or "optionnel") + ((" · " + " · ".join(marques)) if marques else "")
            lignes.append("| `%s` — %s | %s | %s |" % (m.id, m.nom, imp, premiere_phrase(m.description)))
        lignes.append("")
    return "\n".join(lignes).rstrip("\n") + "\n"


def lire_zone(texte):
    """Le texte entre la borne ouvrante et la borne fermante (sans ces deux lignes), ou None."""
    ls = texte.split("\n")
    i = next((k for k, l in enumerate(ls) if DEBUT in l), None)
    j = next((k for k, l in enumerate(ls) if FIN in l), None)
    if i is None or j is None or j < i:
        return None
    return "\n".join(ls[i + 1:j]).strip("\n") + "\n"


def ecrire():
    neuf = corps()
    if CIBLE.exists():
        t = CIBLE.read_text(encoding="utf-8").replace("\r\n", "\n")
        ls = t.split("\n")
        i = next((k for k, l in enumerate(ls) if DEBUT in l), None)
        j = next((k for k, l in enumerate(ls) if FIN in l), None)
        if i is not None and j is not None:
            CIBLE.write_text("\n".join(ls[:i + 1] + neuf.rstrip("\n").split("\n") + ls[j:]), encoding="utf-8", newline="\n")
            return
    CIBLE.write_text(neuf, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    if "--verifier" in sys.argv:
        t = CIBLE.read_text(encoding="utf-8").replace("\r\n", "\n") if CIBLE.exists() else ""
        zone = lire_zone(t)
        sys.exit(0 if (zone if zone is not None else t) == corps() else 1)
    ecrire()
    print("catalogue écrit :", CIBLE.relative_to(RACINE))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : premiere_phrase, modules, corps, lire_zone, ecrire
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
