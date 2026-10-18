# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Notes : le graphe des notes (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notes
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #262ba8
# HÔTE CN    : CN_module.py · graphe @1.0
# RÔLE       : calcule en un balayage les liens entre les notes : ce que chaque note cite, qui la cite, et quels liens sont morts.
# MÉTHODE    : fonction pure : un lien se résout par le numéro de la note (« N-0002 ») ou par son titre sans égard à la casse ; un lien qui ne mène nulle part est dit mort ; les liens vers autre chose qu'une note sont ignorés.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=graphe contrat=@1.0 version=EC0 empreinte=262ba8 ▼▼▼
import re

RE_LIEN = re.compile(r"!?\[\[([^\]|]{1,160})(?:\|[^\]]*)?\]\]")

RE_NUM = re.compile(r"^N-?0*(\d+)$", re.I)

def liens_de(corps):
    """`[[N-0011]]` vers une note, `[[projet:12]]` vers un projet ; `![[…]]` inclut au lieu de renvoyer ; `[[N-0012#^ancre]]` vise un paragraphe."""
    out = []
    for m in RE_LIEN.finditer(str(corps or "")):
        brut = m.group(1).strip()
        if ":" in brut:
            kind, _, ref = brut.partition(":")
            kind, ref = kind.strip().lower(), ref.strip()
        else:
            kind, ref = "note", brut
        out.append({"kind": kind, "ref": ref, "brut": brut, "inclus": m.group(0).startswith("!")})
    return out

def graphe(vivantes):
    """Qui cite qui, en un seul balayage : le faire par note coûterait un balayage par note affichée."""
    par_num = {n["num"]: n for n in vivantes}
    par_titre = {n["titre"].casefold(): n for n in vivantes}
    sortants, entrants, titres = {}, {}, {}
    for n in vivantes:
        titres[n["num"]] = n["titre"]
        sortants.setdefault(n["num"], [])
        for l in liens_de(n["corps"]):
            if l["kind"] != "note":
                continue
            ref = l["ref"].split("#")[0].strip()
            m = RE_NUM.match(ref)
            cible = par_num.get(int(m.group(1))) if m else par_titre.get(ref.casefold())
            if cible:
                sortants[n["num"]].append({"id": cible["ref"], "num": cible["num"], "ref": l["ref"], "mort": False, "inclus": l["inclus"]})
                if n["num"] not in entrants.setdefault(cible["num"], []):
                    entrants[cible["num"]].append(n["num"])
            else:
                sortants[n["num"]].append({"id": "", "num": None, "ref": l["ref"], "mort": True, "inclus": l["inclus"]})
    return sortants, entrants, titres

def point_graphe(entree):
    """Le point d'évolution `graphe` (contrat 1.0) : les notes vivantes en entrée, qui cite qui en sortie (liens sortants, entrants, titres) ; les clés sont les numéros de note, en texte."""
    sortants, entrants, titres = graphe(entree["vivantes"])
    return {"sortants": sortants, "entrants": entrants, "titres": titres}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_graphe(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de notes (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_graphe.json ; corpus doré dans contrats/CN_graphe.corpus.json (sorties de l'ancien code, données synthétiques).
