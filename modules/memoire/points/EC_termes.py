# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : les termes d'une question (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #1b71e3
# HÔTE CN    : CN_module.py · termes @1.0
# RÔLE       : extrait d'une question les mots qui comptent pour chercher dans la mémoire.
# MÉTHODE    : fonction pure : une expression régulière de mots (accents compris), les mots vides et les doublons écartés, au plus n termes dans l'ordre de la question.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=termes contrat=@1.0 version=EC0 empreinte=1b71e3 ▼▼▼
import re

STOP = frozenset((
    "le la les de du des un une et en il elle je tu ce que qui est par sur pour avec dans ou pas se te me on au ne son sa ses mon ma mes ton tes nos vos leur leurs ça cela ceci mais donc car "
    "ni or où quoi comment pourquoi quand est-ce qu'est-ce y a été être avoir fait faire peut peux tout tous toute toutes plus moins très bien the a an and or of to in on for with is are "
    "was were be this that it its as at by from dis moi peux-tu tu-peux stp svp merci bonjour salut").split())

def termes(question, n=8):
    vus, out = set(), []
    for t in re.findall(r"[a-zA-Zàâäéèêëïîôöùûüç0-9][a-zA-Zàâäéèêëïîôöùûüç0-9._-]{2,}", (question or "").lower()):
        t = t.strip("._-")
        if len(t) < 3 or t in STOP or t in vus:
            continue
        vus.add(t)
        out.append(t)
        if len(out) >= n:
            break
    return out

def point_termes(entree):
    """Le point d'évolution `termes` (contrat 1.0)."""
    return {"valeur": termes(entree["question"], entree["n"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_termes(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_termes.json ; corpus doré dans contrats/CN_termes.corpus.json (sorties de l'ancien code, données synthétiques).
