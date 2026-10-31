# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : quand proposer « auto » (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #000000
# HÔTE CN    : CN_propositions.py · proposer_promotion @1.0
# RÔLE       : décide si la carte de confiance propose de passer un outil de « raconter » à « auto » : assez de validations de suite, hors période d'essai, sans refus récent.
# MÉTHODE    : fonction pure : propose si validations >= seuil, et ni essai ni refus récent ; la raison dit ce qui manque.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=proposer_promotion contrat=@1.0 version=EC0 empreinte=000000 ▼▼▼
def proposer_promotion(validations, seuil, essai, refus_recent):
    manque = max(0, int(seuil) - int(validations))
    if refus_recent:
        return {"propose": False, "raison": "un refus récent : on laisse l'outil raconté", "manque": manque}
    if essai:
        return {"propose": False, "raison": "l'outil est encore en période d'essai", "manque": manque}
    if manque > 0:
        return {"propose": False, "raison": "il manque %d validation(s) de suite" % manque, "manque": manque}
    return {"propose": True, "raison": "%d validations de suite, hors essai, sans refus récent" % int(validations), "manque": 0}

def point_proposer_promotion(entree):
    """Le point d'évolution `proposer_promotion` (contrat 1.0)."""
    return {"valeur": proposer_promotion(entree["validations"], entree["seuil"], entree["essai"], entree["refus_recent"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_proposer_promotion(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_proposer_promotion.json ; corpus doré dans contrats/CN_proposer_promotion.corpus.json (sorties de la référence, données synthétiques).
