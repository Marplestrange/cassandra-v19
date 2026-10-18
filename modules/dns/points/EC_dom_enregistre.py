# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dns : domaine à renouveler (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dns
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #bcc499
# HÔTE CN    : CN_module.py · dom_enregistre @1.0
# RÔLE       : retrouve, depuis un nom d'hôte, le domaine enregistré (celui qu'on renouvelle).
# MÉTHODE    : fonction pure : les deux derniers libellés, ou les trois quand le second est un niveau public (co, com, org, net, gov, ac) d'un pays à deux lettres.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=dom_enregistre contrat=@1.0 version=EC0 empreinte=bcc499 ▼▼▼

def dom_enregistre(domaine):
    """Le domaine qu'on RENOUVELLE : « app.exemple.org » -> « exemple.org » ; « x.co.uk » -> « x.co.uk »."""
    p = [x for x in str(domaine or "").lower().strip(".").split(".") if x]
    if len(p) < 2:
        return ""
    if len(p) >= 3 and len(p[-1]) == 2 and p[-2] in ("co", "com", "org", "net", "gov", "ac"):
        return ".".join(p[-3:])
    return ".".join(p[-2:])

def point_dom_enregistre(entree):
    """Le point d'évolution `dom_enregistre` (contrat 1.0)."""
    return {"valeur": dom_enregistre(entree["domaine"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_dom_enregistre(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de dns (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_dom_enregistre.json ; corpus doré dans contrats/CN_dom_enregistre.corpus.json (sorties de l'ancien code, données synthétiques).
