# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie : Une commande shell découpée en segments ; None si elle n'est pas analysable (l'appelant la traite alors avec prudence) (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #36ef55
# HÔTE CN    : CN_module.py · segments @1.0
# RÔLE       : Une commande shell découpée en segments ; None si elle n'est pas analysable (l'appelant la traite alors avec prudence).
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=segments contrat=@1.0 version=EC0 empreinte=36ef55 ▼▼▼
import shlex

SEPARATEURS = {";", "|", "||", "&&", "&", "\n"}

def segments(cmd):
    """Une commande shell découpée en segments ; None si elle n'est pas analysable (l'appelant la traite alors avec prudence)."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    segs, cur = [], []
    for t in tokens:
        if t in SEPARATEURS:
            segs.append(cur)
            cur = []
        else:
            cur.append(t)
    segs.append(cur)
    return [s for s in segs if s]

def point_segments(entree):
    """Le point d'évolution `segments` (contrat 1.0)."""
    return {"valeur": segments(entree["cmd"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_segments(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de planifie (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_segments.json ; corpus doré dans contrats/CN_segments.corpus.json (sorties de l'ancien code, données synthétiques).
