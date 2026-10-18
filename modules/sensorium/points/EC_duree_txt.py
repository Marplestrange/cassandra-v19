# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : une durée en mots (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #c42edb
# HÔTE CN    : CN_module.py · duree_txt @1.0
# RÔLE       : dit en mots l'uptime d'une machine ou l'âge d'une mesure.
# MÉTHODE    : fonction pure : jours et heures à partir d'un jour, heures et minutes en deçà ; « ? » quand la valeur n'est pas un nombre.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=duree_txt contrat=@1.0 version=EC0 empreinte=c42edb ▼▼▼

def _duree_txt(sec) -> str:
    try:
        sec = int(sec)
    except Exception:
        return "?"
    j, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    return ("%d j %d h" % (j, h)) if j else ("%d h %d min" % (h, r // 60))

def point_duree_txt(entree):
    """Le point d'évolution `duree_txt` (contrat 1.0)."""
    return {"valeur": _duree_txt(entree["sec"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_duree_txt(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_duree_txt.json ; corpus doré dans contrats/CN_duree_txt.corpus.json (sorties de l'ancien code, données synthétiques).
