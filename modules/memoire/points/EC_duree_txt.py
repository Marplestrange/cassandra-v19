# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : duree_txt (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #000000
# HÔTE CN    : CN_module.py · duree_txt @1.0
# RÔLE       : duree_txt.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=duree_txt contrat=@1.0 version=EC0 empreinte=000000 ▼▼▼

def duree_txt(s):
    if s is None:
        return "date inconnue"
    s = int(s)
    if s < 60:
        return "%d s" % s
    if s < 3600:
        return "%d min" % (s // 60)
    if s < 86400:
        return "%d h" % (s // 3600)
    return "%d j" % (s // 86400)

def point_duree_txt(entree):
    """Le point d'évolution `duree_txt` (contrat 1.0)."""
    return {"valeur": duree_txt(entree["s"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_duree_txt(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_duree_txt.json ; corpus doré dans contrats/CN_duree_txt.corpus.json (sorties de l'ancien code, données synthétiques).
