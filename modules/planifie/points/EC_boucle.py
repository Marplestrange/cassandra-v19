# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie : les tâches qui s'attendent (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #02e2ae
# HÔTE CN    : CN_module.py · boucle @1.0
# RÔLE       : détecte un cycle d'attentes entre tâches planifiées avant de l'enregistrer.
# MÉTHODE    : fonction pure : on suit la chaîne des attentes depuis la tâche visée ; un retour à elle-même est un cycle ; au-delà de douze maillons, on conclut à un cycle par prudence.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=boucle contrat=@1.0 version=EC0 empreinte=02e2ae ▼▼▼

def boucle(ref, apres, suivants, profondeur=0):
    """Deux tâches qui s'attendent l'une l'autre ne partiraient jamais, et rien ne le dirait. `suivants` : ref -> ref qu'elle attend."""
    if profondeur > 12:
        return True
    s = suivants.get(apres) or ""
    if not s:
        return False
    return True if s == ref else boucle(ref, s, suivants, profondeur + 1)

def point_boucle(entree):
    """Le point d'évolution `boucle` (contrat 1.0)."""
    return {"valeur": boucle(entree["ref"], entree["apres"], entree["suivants"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_boucle(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de planifie (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_boucle.json ; corpus doré dans contrats/CN_boucle.corpus.json (sorties de l'ancien code, données synthétiques).
