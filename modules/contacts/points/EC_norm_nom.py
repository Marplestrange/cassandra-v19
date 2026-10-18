# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : Le nom, comparable : aplati, débarrassé de sa forme juridique. Un nom sans aucune lettre garde la signature de ses symboles (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.2)  #ec5d6d
# HÔTE CN    : CN_module.py · norm_nom @1.0
# RÔLE       : Le nom, comparable : aplati, débarrassé de sa forme juridique. Un nom sans aucune lettre garde la signature de ses symboles.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=norm_nom contrat=@1.0 version=EC0 empreinte=ec5d6d ▼▼▼
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

def point_norm_nom(entree):
    """Le point d'évolution `norm_nom` (contrat 1.0)."""
    return {"valeur": norm_nom(entree["s"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_norm_nom(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_norm_nom.json ; corpus doré dans contrats/CN_norm_nom.corpus.json (sorties de l'ancien code, données synthétiques).
