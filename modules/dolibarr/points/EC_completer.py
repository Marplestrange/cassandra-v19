# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dolibarr : Ce que Dolibarr 24 exige à la CRÉATION et que l'appelant n'a pas à connaître : le code client ou fournisseur d'un tiers (« auto » : Dolibarr le numérote), (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dolibarr
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #9a5fbe
# HÔTE CN    : CN_module.py · completer @1.0
# RÔLE       : Ce que Dolibarr 24 exige à la CRÉATION et que l'appelant n'a pas à connaître : le code client ou fournisseur d'un tiers (« auto » : Dolibarr le numérote),.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=completer contrat=@1.0 version=EC0 empreinte=9a5fbe ▼▼▼

def _completer(objet, corps):
    """Ce que Dolibarr 24 exige à la CRÉATION et que l'appelant n'a pas à connaître : le code client ou fournisseur d'un tiers (« auto » : Dolibarr le numérote),
    la référence d'un projet (« auto » aussi). Vu sur le vrai Dolibarr : sans cela, HTTP 500 (ErrorCustomerCodeRequired) ou 400 (ref field missing)."""
    c = dict(corps)
    if objet == "tiers":
        if str(c.get("client", 0)) not in ("0", "", "None") and not c.get("code_client"):
            c["code_client"] = "auto"
        if str(c.get("fournisseur", 0)) not in ("0", "", "None") and not c.get("code_fournisseur"):
            c["code_fournisseur"] = "auto"
    elif objet == "projets" and not c.get("ref"):
        c["ref"] = "auto"
    return c

def point_completer(entree):
    """Le point d'évolution `completer` (contrat 1.0)."""
    return {"valeur": _completer(entree["objet"], entree["corps"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_completer(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de dolibarr (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_completer.json ; corpus doré dans contrats/CN_completer.corpus.json (sorties de l'ancien code, données synthétiques).
