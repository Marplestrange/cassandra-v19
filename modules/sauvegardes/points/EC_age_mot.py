# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sauvegardes : l'âge d'une sauvegarde en mots (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sauvegardes
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #0725a3
# HÔTE CN    : CN_module.py · age_mot @1.0
# RÔLE       : dit en mots l'âge de la dernière sauvegarde.
# MÉTHODE    : fonction pure : minutes sous une heure, heures sous quarante-huit heures, jours au-delà ; « jamais » quand il n'y en a pas.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=age_mot contrat=@1.0 version=EC0 empreinte=0725a3 ▼▼▼

def _age_mot(h):
    if h is None:
        return "jamais"
    if h < 1:
        return "%d min" % max(1, int(h * 60))
    if h < 48:
        return "%d h" % int(h)
    return "%d j" % int(h / 24)

def point_age_mot(entree):
    """Le point d'évolution `age_mot` (contrat 1.0)."""
    return {"valeur": _age_mot(entree["h"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_age_mot(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sauvegardes (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_age_mot.json ; corpus doré dans contrats/CN_age_mot.corpus.json (sorties de l'ancien code, données synthétiques).
