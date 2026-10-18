# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Flotte : une durée en mots (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : flotte
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #11c79f
# HÔTE CN    : CN_module.py · duree @1.0
# RÔLE       : dit en mots depuis combien de temps une machine est dans son état.
# MÉTHODE    : fonction pure : « moins d'une minute », puis minutes, heures et minutes, jours et heures.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=duree contrat=@1.0 version=EC0 empreinte=11c79f ▼▼▼

def duree(m):
    m = int(m or 0)
    if m < 1:
        return "moins d'une minute"
    if m < 60:
        return "%d min" % m
    if m < 1440:
        return "%d h %02d" % (m // 60, m % 60)
    return "%d j %d h" % (m // 1440, (m % 1440) // 60)

def point_duree(entree):
    """Le point d'évolution `duree` (contrat 1.0)."""
    return {"valeur": duree(entree["m"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_duree(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de flotte (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_duree.json ; corpus doré dans contrats/CN_duree.corpus.json (sorties de l'ancien code, données synthétiques).
