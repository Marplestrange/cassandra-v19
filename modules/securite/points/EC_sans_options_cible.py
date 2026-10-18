# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Securite : _sans_options_cible (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #e099fc
# HÔTE CN    : CN_module.py · sans_options_cible @1.0
# RÔLE       : _sans_options_cible.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=sans_options_cible contrat=@1.0 version=EC0 empreinte=e099fc ▼▼▼

_OPTIONS_CIBLE = ("--reject-with", "--log-prefix", "--log-level", "--to-destination", "--to-source", "--to-ports", "--set-mark", "--set-xmark")

def _sans_options_cible(j):
    out, saute = [], False
    for x in j:
        if saute:
            saute = False
            continue
        if x in _OPTIONS_CIBLE:
            saute = True
            continue
        if x in ("--log-uid", "--log-tcp-options", "--log-ip-options"):
            continue
        out.append(x)
    return out

def point_sans_options_cible(entree):
    """Le point d'évolution `sans_options_cible` (contrat 1.0)."""
    return {"valeur": _sans_options_cible(entree["j"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_sans_options_cible(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de securite (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_sans_options_cible.json ; corpus doré dans contrats/CN_sans_options_cible.corpus.json (sorties de l'ancien code, données synthétiques).
