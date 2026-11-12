# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : Un nombre entier demandé par un appelant (l'écran, un agent) : vide → le défaut, hors bornes → ramené aux bornes, illisible → une erreur qui le dit (pas le « invalid literal » de Python) (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #6f683c
# HÔTE CN    : CN_module.py · entier @1.0
# RÔLE       : Un nombre entier demandé par un appelant (l'écran, un agent) : vide → le défaut, hors bornes → ramené aux bornes, illisible → une erreur qui le dit (pas le « invalid literal » de Python).
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=entier contrat=@1.0 version=EC0 empreinte=6f683c ▼▼▼

def entier(valeur, defaut: int, mini: int, maxi: int, nom: str = "valeur") -> int:
    """Un nombre entier demandé par un appelant (l'écran, un agent) : vide → le défaut, hors bornes → ramené aux bornes, illisible → une erreur qui le dit (pas le « invalid literal » de Python)."""
    if valeur in (None, "", 0):
        return defaut
    try:
        n = int(valeur)
    except (TypeError, ValueError):
        raise ValueError("%s : un nombre entier est attendu" % nom)
    return max(mini, min(n, maxi))

def point_entier(entree):
    """Le point d'évolution `entier` (contrat 1.0)."""
    return {"valeur": entier(entree["valeur"], entree["defaut"], entree["mini"], entree["maxi"], entree["nom"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_entier(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_entier.json ; corpus doré dans contrats/CN_entier.corpus.json (sorties de l'ancien code, données synthétiques).
