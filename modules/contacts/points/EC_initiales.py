# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : forme abrégée d'un nom (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #c87264
# HÔTE CN    : CN_module.py · initiales @1.0
# RÔLE       : reconnaît qu'un nom abrégé est la forme courte d'un nom complet, pour proposer un rapprochement de fiches.
# MÉTHODE    : fonction pure : le dernier mot doit être identique, les précédents se correspondent lettre à lettre, au moins une initiale.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=initiales contrat=@1.0 version=EC0 empreinte=c87264 ▼▼▼
import re
import unicodedata

FORMES = ("sarl", "sas", "sasu", "sa", "eurl", "sci", "scop", "scic", "snc", "gmbh", "ltd", "limited", "inc", "llc", "bv", "srl", "spa", "ag",
          "et fils", "and sons", "et cie", "and co", "group", "groupe")

def aplatir(s):
    t = unicodedata.normalize("NFD", str(s or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())

def norm_nom(s):
    """Le nom, comparable : aplati, débarrassé de sa forme juridique. Un nom sans aucune lettre garde la signature de ses symboles."""
    t = aplatir(s)
    if not t:
        brut = " ".join(str(s or "").split())
        return ("sym:" + brut.lower()) if brut else ""
    for f in FORMES:
        t = re.sub(r"(^|\s)%s(\s|$)" % re.escape(f), " ", t)
    return " ".join(t.split())

def initiales(a, b):
    """« J. Danet » est-il la forme abrégée de « Julie Danet » ? Le DERNIER mot doit être identique et les précédents se correspondre lettre à lettre."""
    x, y = norm_nom(a).split(), norm_nom(b).split()
    if len(x) < 2 or len(y) < 2 or len(x) != len(y) or x[-1] != y[-1]:
        return False
    abrege = False
    for m, n in zip(x[:-1], y[:-1]):
        if m == n:
            continue
        if (len(m) == 1 and n.startswith(m)) or (len(n) == 1 and m.startswith(n)):
            abrege = True
            continue
        return False
    return abrege

def point_initiales(entree):
    """Le point d'évolution `initiales` (contrat 1.0)."""
    return {"valeur": initiales(entree["a"], entree["b"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_initiales(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_initiales.json ; corpus doré dans contrats/CN_initiales.corpus.json (sorties de l'ancien code, données synthétiques).
