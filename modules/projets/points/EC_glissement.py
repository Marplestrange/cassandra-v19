# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Projets : le glissement d'un projet (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : projets
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #2d0a14
# HÔTE CN    : CN_module.py · glissement @1.0
# RÔLE       : dit de combien de jours chaque phase et chaque jalon a glissé depuis la référence du projet.
# MÉTHODE    : fonction pure : pour chaque phase et jalon qui a une date de référence et une date actuelle plus tardive, l'écart en jours ; le plus grand écart est rendu avec la date de référence.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=glissement contrat=@1.0 version=EC0 empreinte=2d0a14 ▼▼▼
from datetime import datetime

def jours_entre(a, b):
    try:
        return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days
    except ValueError:
        return 0

def glissement(p, phases, jalons):
    lignes = []
    for ph in phases:
        if ph["ref_fin"] and ph["fin"] and ph["fin"] > ph["ref_fin"]:
            lignes.append({"genre": "phase", "nom": ph["nom"], "jours": jours_entre(ph["ref_fin"], ph["fin"]), "prevu": ph["ref_fin"], "maintenant": ph["fin"]})
    for j in jalons:
        if j["ref_date"] and j["date"] and j["date"] > j["ref_date"]:
            lignes.append({"genre": "jalon", "nom": j["nom"], "jours": jours_entre(j["ref_date"], j["date"]), "prevu": j["ref_date"], "maintenant": j["date"]})
    return {"lignes": lignes, "max_jours": max([l["jours"] for l in lignes] or [0]), "reference": p["ref_date"]}

def point_glissement(entree):
    """Le point d'évolution `glissement` (contrat 1.0) : le projet, ses phases et ses jalons en entrée, le glissement par rapport à la référence en sortie."""
    return {"valeur": glissement(entree["p"], entree["phases"], entree["jalons"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_glissement(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de projets (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_glissement.json ; corpus doré dans contrats/CN_glissement.corpus.json (sorties de l'ancien code, données synthétiques).
