# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : les jetons d'un texte (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #4e92c0
# HÔTE CN    : CN_module.py · jetons @1.0
# RÔLE       : découpe un texte en jetons comparables : sans accents, sans mots vides, les mots tronqués à sept lettres.
# MÉTHODE    : fonction pure : minuscules sans accents, un mot court ou vide de sens est écarté, un mot alphabétique est tronqué à sept lettres ; le résultat est un ensemble.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=jetons contrat=@1.0 version=EC0 empreinte=4e92c0 ▼▼▼
import re
import unicodedata

MOTS_VIDES = frozenset("les des une est sur dans pour par pas que qui avec son ses aux ete cette sont plus tout fait elle ils lui mais donc car comme sans entre depuis apres avant leur leurs ont avoir etre fois".split())

def jetons(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()
    out = set()
    for w in re.findall(r"[a-z0-9](?:[a-z0-9._/:-]*[a-z0-9])?", t):
        if (len(w) < 4 and not w.isdigit()) or w in MOTS_VIDES:
            continue
        out.add(w[:7] if w.isalpha() else w)
    return out

def point_jetons(entree):
    """Le point d'évolution `jetons` (contrat 1.0)."""
    return {"valeur": sorted(jetons(entree["t"]))}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_jetons(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_jetons.json ; corpus doré dans contrats/CN_jetons.corpus.json (sorties de l'ancien code, données synthétiques).
