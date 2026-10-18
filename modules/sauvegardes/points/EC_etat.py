# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sauvegardes : l'état d'une sauvegarde (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sauvegardes
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #e826a0
# HÔTE CN    : CN_module.py · etat @1.0
# RÔLE       : juge si la dernière sauvegarde est assez récente : ok sous le seuil, à surveiller jusqu'à trois fois le seuil, danger au-delà ou quand il n'y en a jamais eu.
# MÉTHODE    : fonction pure : trois paliers sur l'âge rapporté au seuil ; l'absence de sauvegarde est un danger, jamais un « ok ».
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=etat contrat=@1.0 version=EC0 empreinte=e826a0 ▼▼▼

def _etat(h, seuil_h=24.0):
    if h is None:
        return "danger"
    if h <= seuil_h:
        return "ok"
    if h <= seuil_h * 3:
        return "warn"
    return "danger"

def point_etat(entree):
    """Le point d'évolution `etat` (contrat 1.0)."""
    return {"valeur": _etat(entree["h"], entree["seuil_h"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_etat(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sauvegardes (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_etat.json ; corpus doré dans contrats/CN_etat.corpus.json (sorties de l'ancien code, données synthétiques).
